"""02B completion: the OpenRouter embedding provider. Fake transport only (httpx.MockTransport); a fixture fails any real socket connect.

Covers request shape, dedupe and cache, batching bounds, strict response validation (never partial or zero vectors), bounded retries, the 05C governor
chokepoint (a real governor over a temp ledger: spend control and accounting are the governor's), fail-closed configuration, the manifest identity and
no-mixing guarantees, the controlled rebuild, the dimensions parameter and the offline model-catalogue check. No live OpenRouter call exists here.
"""

from __future__ import annotations

import hashlib
import json
import re
import socket
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from src.copilot import constants
from src.copilot import index_manifest as IM
from src.copilot.config import CopilotConfig
from src.copilot.embedding_catalogue import check_model_in_listing, facts_for
from src.copilot.embeddings import (EmbeddingConfigurationError, EmbeddingProviderError, LocalHashEmbedder, build_embedder, embedding_status,
                                    resolve_embedding_plan)
from src.copilot.index_manifest import IndexIncompatibleError
from src.copilot.models import DocumentChunk
from src.copilot.openrouter_embeddings import OpenRouterEmbedder
from src.copilot.vectorstore import ChromaStore
from src.knowledge_admin import policy as P
from src.knowledge_admin.embedding_rebuild import rebuild_into_new_index
from src.llm.budget import config as C
from src.llm.budget import governor as G
from src.persistence import AiBudgetEntry, Base, make_engine, make_session_factory
from tests._knowledge_env_02a import Process, release_chroma
from tests.test_ai_budget_governor_05c import make_gov, raw_config

KEY = "sk-or-v1-SENTINEL-EMBED-KEY-0123456789"
MODEL = "provider/embed"                     # priced in tests.test_ai_budget_governor_05c.raw_config; NOT in the catalogue, so dimensions come from config
DIMS = 8
APPROVAL = {"ASK4MO_ALLOW_PAID_EMBEDDINGS": "1", "ASK4MO_EMBEDDING_BUDGET_MARKER": "OD-BUDGET:test-fixture-only", "ASK4MO_EMBEDDING_MAX_CALLS": "50"}
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _isolation(monkeypatch):
    for k in ("CI", "GITHUB_ACTIONS", C.MODE_ENV, C.CLASS_ENV, C.MARKER_ENV, C.KILL_ENV, C.CONFIG_PATH_ENV, "API_ENV", "OPENROUTER_API_KEY", "OPENROUTER_BASE_URL"):
        monkeypatch.delenv(k, raising=False)

    def refuse(*a, **k):
        raise AssertionError("a real network connection was attempted")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    yield
    G.uninstall()
    release_chroma()


@pytest.fixture()
def sf(tmp_path):
    eng = make_engine(f"sqlite:///{tmp_path / 'ledger.db'}")
    Base.metadata.create_all(eng)
    yield make_session_factory(eng)
    eng.dispose()


def cfg(model=MODEL, dims=DIMS, key=KEY, **kw) -> CopilotConfig:
    return CopilotConfig(embedding_provider="openrouter", embedding_model=model, embedding_dimensions=dims, api_key=SecretStr(key) if key else None, **kw)


def vec(text: str, dims: int) -> list[float]:
    h = hashlib.sha256(text.encode()).digest()
    return [((h[i % 32] + i) % 17) / 17.0 + 0.01 for i in range(dims)]


class Fake:
    """A fake OpenRouter embeddings endpoint. ``mutate`` may alter the response body; ``status`` forces an HTTP status; ``raise_`` raises a transport error."""

    def __init__(self, dims=DIMS, *, mutate=None, status=200, raise_=None, usage=True, raw=None):
        self.dims, self.mutate, self.status, self.raise_, self.usage, self.raw = dims, mutate, status, raise_, usage, raw
        self.requests: list[httpx.Request] = []

    def bodies(self):
        return [json.loads(r.content) for r in self.requests]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.raise_ is not None:
            exc = self.raise_(request) if callable(self.raise_) else self.raise_
            if exc is not None:
                raise exc
        if self.status != 200:
            return httpx.Response(self.status, json={"error": {"code": self.status, "message": f"upstream detail {KEY}"}})
        if self.raw is not None:
            return httpx.Response(200, content=self.raw)
        inputs = json.loads(request.content)["input"]
        body = {"id": "embd-1", "object": "list", "model": MODEL,
                "data": [{"object": "embedding", "embedding": vec(t, self.dims), "index": i} for i, t in enumerate(inputs)]}
        if self.usage:
            body["usage"] = {"prompt_tokens": sum(max(1, len(t) // 4) for t in inputs), "total_tokens": sum(max(1, len(t) // 4) for t in inputs)}
        if self.mutate:
            self.mutate(body)
        return httpx.Response(200, json=body)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self))


def emb(fake: Fake, config=None, **kw) -> OpenRouterEmbedder:
    kw.setdefault("require_governor", False)          # parsing/bounds tests; the governor tests below leave the default (required)
    kw.setdefault("sleep", lambda s: None)
    return OpenRouterEmbedder(config or cfg(dims=fake.dims), client=fake.client(), **kw)


def codes(exc) -> str:
    return exc.value.code


# ================================================================================================ request shape, dedupe, cache, batching
def test_request_shape_and_key_never_leaks():
    f = Fake()
    e = emb(f)
    out = e.embed_documents(["alpha"])
    r = f.requests[0]
    assert r.method == "POST" and str(r.url) == "https://openrouter.ai/api/v1/embeddings"
    assert r.headers["authorization"] == f"Bearer {KEY}"
    assert f.bodies()[0] == {"model": MODEL, "input": ["alpha"], "encoding_format": "float"}        # no dimensions param for a non-catalogue model
    assert out == [vec("alpha", DIMS)]
    assert KEY not in repr(e) and KEY not in json.dumps(e.describe()) and KEY not in json.dumps(e.identity().to_dict())


def test_identical_texts_are_sent_once_and_cached_within_the_embedder():
    f = Fake()
    e = emb(f)
    out = e.embed_documents(["a", "b", "a", "a"])
    assert f.bodies()[0]["input"] == ["a", "b"] and len(f.requests) == 1                          # deduped inside the batch
    assert out == [vec("a", DIMS), vec("b", DIMS), vec("a", DIMS), vec("a", DIMS)]
    out2 = e.embed_documents(["b", "a"])
    assert len(f.requests) == 1 and out2 == [vec("b", DIMS), vec("a", DIMS)]                       # served from the cache: no second paid call
    assert e.embed_query("a") == vec("a", DIMS) and len(f.requests) == 1
    out[0][0] = 999.0
    assert e.embed_documents(["a"])[0][0] != 999.0                                                  # callers get copies


def test_batching_is_bounded_by_count_and_by_the_token_estimate(monkeypatch):
    f = Fake()
    texts = [f"text number {i}" for i in range(130)]
    e = emb(f)
    out = e.embed_documents(texts)
    sizes = [len(b["input"]) for b in f.bodies()]
    assert sizes == [64, 64, 2] and out == [vec(t, DIMS) for t in texts]
    monkeypatch.setattr(constants, "OPENROUTER_EMBED_MAX_BATCH_TOKENS", 60)
    f2 = Fake()
    emb(f2).embed_documents([("w" * 30) + str(i) for i in range(10)])
    assert len(f2.requests) > 1 and all(json.dumps(b["input"]) and (len(json.dumps(b["input"])) + 2) // 3 <= 60 for b in f2.bodies())


def test_an_input_above_the_models_context_or_batch_bound_is_refused_before_any_request():
    f = Fake(dims=1024)
    e = emb(f, cfg("intfloat/multilingual-e5-large", dims=None))                                   # catalogue: context 512 tokens
    with pytest.raises(EmbeddingProviderError) as x:
        e.embed_documents(["x" * 3000])
    assert codes(x) == "input_too_large" and f.requests == []


def test_empty_input_is_refused_never_embedded_as_a_zero_vector():
    f = Fake()
    for bad in ("", "   "):
        with pytest.raises(EmbeddingProviderError) as x:
            emb(f).embed_documents(["fine", bad])
        assert codes(x) == "empty_input"
    assert f.requests == [] and emb(f).embed_documents([]) == []


# ================================================================================================ strict response validation
def _set(path):
    def mut(body):
        path(body)
    return mut


BAD = {
    "fewer_vectors": lambda b: b["data"].pop(),
    "more_vectors": lambda b: b["data"].append(dict(b["data"][0], index=9)),
    "short_vector": lambda b: b["data"][0]["embedding"].pop(),
    "long_vector": lambda b: b["data"][1]["embedding"].append(0.5),
    "string_element": lambda b: b["data"][0]["embedding"].__setitem__(0, "0.5"),
    "bool_element": lambda b: b["data"][0]["embedding"].__setitem__(0, True),
    "null_element": lambda b: b["data"][0]["embedding"].__setitem__(0, None),
    "base64_embedding": lambda b: b["data"][0].__setitem__("embedding", "AAAA"),
    "missing_embedding": lambda b: b["data"][0].pop("embedding"),
    "duplicate_index": lambda b: b["data"][1].__setitem__("index", 0),
    "index_out_of_range": lambda b: b["data"][1].__setitem__("index", 5),
    "usage_not_object": lambda b: b.__setitem__("usage", "free"),
    "data_not_list": lambda b: b.__setitem__("data", {"0": 1}),
    "error_envelope": lambda b: b.__setitem__("error", {"code": 500}),
    "item_not_object": lambda b: b["data"].__setitem__(0, [1, 2]),
}


@pytest.mark.parametrize("name", sorted(BAD))
def test_a_malformed_200_raises_and_never_returns_partial_vectors(name):
    f = Fake(mutate=BAD[name])
    e = emb(f)
    with pytest.raises(EmbeddingProviderError) as x:
        e.embed_documents(["one", "two"])
    assert codes(x) in ("unexpected_response", "dimension_mismatch") and KEY not in str(x.value)
    assert e._cache == {}                                                                          # nothing partial is remembered either


@pytest.mark.parametrize("raw", [b"not json", b"[]", b"null", b'{"data": null}', b'{"data":[{"embedding":[NaN,0,0,0,0,0,0,0],"index":0},{"embedding":[0,0,0,0,0,0,0,0],"index":1}]}',
                                 b'{"data":[{"embedding":[Infinity,0,0,0,0,0,0,0],"index":0},{"embedding":[0,0,0,0,0,0,0,0],"index":1}]}'])
def test_unparseable_non_finite_or_wrong_typed_bodies_are_refused(raw):
    with pytest.raises(EmbeddingProviderError) as x:
        emb(Fake(raw=raw)).embed_documents(["one", "two"])
    assert codes(x) == "unexpected_response"


def test_usage_is_optional_and_out_of_order_indexes_are_reassembled():
    def shuffle(b):
        b["data"].reverse()
    f = Fake(usage=False, mutate=shuffle)
    e = emb(f)
    out = e.embed_documents(["first", "second", "third"])
    assert out == [vec("first", DIMS), vec("second", DIMS), vec("third", DIMS)]
    assert e.responses_without_usage == 1 and e.prompt_tokens == 0                                  # unknown usage is never counted as 0 tokens used


def test_a_failing_later_batch_fails_the_whole_call_and_caches_nothing():
    def second_bad(request):
        return None
    f = Fake()
    calls = {"n": 0}
    base = f.__call__

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 2:
            return httpx.Response(200, json={"data": []})
        return base(request)
    e = OpenRouterEmbedder(cfg(), client=httpx.Client(transport=httpx.MockTransport(handler)), require_governor=False)
    with pytest.raises(EmbeddingProviderError):
        e.embed_documents([f"t{i}" for i in range(70)])
    assert e._cache == {}


@pytest.mark.parametrize("status,code", [(401, "provider_auth"), (403, "provider_auth"), (402, "provider_credits"), (413, "payload_too_large"), (429, "rate_limited"),
                                         (400, "provider_rejected"), (500, "provider_unavailable"), (503, "provider_unavailable")])
def test_http_failures_map_to_fixed_codes_with_no_retry_and_no_provider_text(status, code):
    f = Fake(status=status)
    with pytest.raises(EmbeddingProviderError) as x:
        emb(f).embed_documents(["a"])
    assert codes(x) == code and len(f.requests) == 1 and KEY not in str(x.value) and "upstream detail" not in str(x.value)


# ================================================================================================ bounded retries
def test_connect_errors_are_retried_a_bounded_number_of_times():
    n = {"i": 0}

    def flaky(request):
        n["i"] += 1
        return httpx.ConnectError("refused", request=request) if n["i"] == 1 else None
    sleeps = []
    f = Fake(raise_=flaky)
    e = emb(f, sleep=sleeps.append)
    assert e.embed_documents(["a"]) == [vec("a", DIMS)] and len(f.requests) == 2 and len(sleeps) == 1
    f2 = Fake(raise_=lambda r: httpx.ConnectError("refused", request=r))
    with pytest.raises(EmbeddingProviderError) as x:
        emb(f2, max_retries=9).embed_documents(["a"])
    assert codes(x) == "network" and len(f2.requests) == 3                                          # the retry bound is capped at 2 extra attempts


@pytest.mark.parametrize("exc,code", [(httpx.ReadTimeout("slow"), "timeout"), (httpx.ReadError("reset"), "network"), (httpx.RemoteProtocolError("x"), "network")])
def test_unknown_outcome_transport_errors_are_never_re_sent(exc, code):
    f = Fake(raise_=lambda r: type(exc)(str(exc), request=r) if not isinstance(exc, httpx.RemoteProtocolError) else httpx.RemoteProtocolError("x", request=r))
    with pytest.raises(EmbeddingProviderError) as x:
        emb(f).embed_documents(["a"])
    assert codes(x) == code and len(f.requests) == 1


# ================================================================================================ the 05C governor chokepoint
def governed(sf, **kw):
    return G.install(make_gov(sf, **kw))


def test_without_an_installed_governor_the_embedder_refuses_before_any_request():
    f = Fake()
    e = OpenRouterEmbedder(cfg(), client=f.client())                                               # require_governor defaults to True
    with pytest.raises(EmbeddingProviderError) as x:
        e.embed_documents(["a"])
    assert codes(x) == "budget_governor_not_installed" and f.requests == []


def test_a_closed_governor_is_a_typed_refusal_with_its_reason():
    G.install(G.BudgetGovernor.closed("marker_missing"))
    f = Fake()
    with pytest.raises(EmbeddingProviderError) as x:
        OpenRouterEmbedder(cfg(), client=f.client()).embed_documents(["a"])
    assert codes(x) == "budget_refused" and x.value.reason == "marker_missing" and f.requests == []


def test_calls_go_through_the_governor_which_reserves_settles_and_records_truthful_usage(sf):
    governed(sf)
    f = Fake()
    e = OpenRouterEmbedder(cfg(), client=f.client())
    out = e.embed_documents(["alpha beta gamma", "delta"])
    assert out == [vec("alpha beta gamma", DIMS), vec("delta", DIMS)]
    with sf() as s:
        row = s.execute(select(AiBudgetEntry)).scalar_one()
    assert (row.category, row.endpoint, row.model, row.state) == ("embedding", "embeddings", MODEL, "settled")
    assert row.input_tokens == e.prompt_tokens == 4 + 1 and row.output_tokens == 0 and row.committed_micro_usd > 0 and row.latency_ms is not None
    assert "alpha" not in json.dumps({c.name: getattr(row, c.name) for c in AiBudgetEntry.__table__.columns}, default=str)     # no text in the ledger


def test_a_response_without_usage_is_held_as_unknown_not_zero_and_not_re_sent(sf):
    gov = governed(sf)
    f = Fake(usage=False)
    e = OpenRouterEmbedder(cfg(), client=f.client())
    assert e.embed_documents(["same text"]) == [vec("same text", DIMS)]
    with sf() as s:
        row = s.execute(select(AiBudgetEntry)).scalar_one()
    assert row.state == "unknown" and row.input_tokens is None and row.reserved_micro_usd > 0       # tokens unknown (NULL, never 0); worst case stays reserved
    e2 = OpenRouterEmbedder(cfg(), client=Fake().client())                                          # a fresh embedder (no cache) re-sending the same input
    with pytest.raises(EmbeddingProviderError) as x:
        e2.embed_documents(["same text"])
    assert codes(x) == "budget_refused" and gov.refusals                                             # the governor refuses an identical unknown-outcome request


@pytest.mark.parametrize("model,reason", [("provider/not-priced", "model_not_priced")])
def test_an_unpriced_model_is_refused_by_the_governor(sf, model, reason):
    governed(sf)
    f = Fake()
    with pytest.raises(EmbeddingProviderError) as x:
        OpenRouterEmbedder(cfg(model=model), client=f.client()).embed_documents(["a"])
    assert codes(x) == "budget_refused" and x.value.reason == reason and f.requests == []


def test_the_embedding_category_ceiling_stops_spend(sf):
    raw = raw_config()
    raw["classes"]["development"]["categories"]["embedding"] = {"hard_cap_usd": "0.0001", "stop_usd": "0.00005"}
    raw["pricing"]["models"][MODEL] = {"prompt": "0.001", "completion": "0"}
    governed(sf, raw=raw)
    f = Fake()
    with pytest.raises(EmbeddingProviderError) as x:
        OpenRouterEmbedder(cfg(), client=f.client()).embed_documents(["a" * 90])
    assert codes(x) == "budget_refused" and f.requests == []


def test_the_governors_per_request_input_limit_lowers_the_batch_bound(sf):
    governed(sf)                                                                                    # max_input_tokens = 2000 in raw_config
    f = Fake()
    texts = ["w" * 1500 + str(i) for i in range(6)]                                                  # ~500 estimated tokens each
    OpenRouterEmbedder(cfg(), client=f.client()).embed_documents(texts)
    assert len(f.requests) >= 2 and all(len(b["input"]) <= 3 for b in f.bodies())
    with pytest.raises(EmbeddingProviderError) as x:
        OpenRouterEmbedder(cfg(), client=Fake().client()).embed_documents(["z" * 7000])
    assert codes(x) == "input_too_large"


def test_the_module_adds_no_second_spend_control_and_no_bypass():
    src = (ROOT / "src/copilot/openrouter_embeddings.py").read_text(encoding="utf-8")
    assert "httpx.Client" in src and "ledger" not in src.lower() and "reserve" not in src and "BudgetGovernor(" not in src
    assert "AsyncClient" not in src and "urllib.request" not in src and "requests." not in src and "http.client" not in src and "socket" not in src
    assert "follow_redirects" not in src.replace("follow_redirects stays False", "")                 # never follows a redirect with the key


# ================================================================================================ configuration (fail closed, no hard-coded ids)
def test_model_id_comes_from_configuration_only():
    for path in ("src/copilot/openrouter_embeddings.py", "src/copilot/embeddings.py", "src/copilot/config.py", "src/copilot/constants.py"):
        text = (ROOT / path).read_text(encoding="utf-8")
        assert not re.search(r"(openai|baai|qwen|intfloat|voyageai|google|mistralai)/[a-z0-9.\-]*embed", text, re.I), path
    cat = (ROOT / "src/copilot/embedding_catalogue.py").read_text(encoding="utf-8")
    assert "NOT a model choice" in cat and "EXPECTATIONS, NOT MEASUREMENTS" in cat


@pytest.mark.parametrize("env", ("development", "staging", "production", "unknown"))
@pytest.mark.parametrize("make,code", [
    (lambda: cfg(model="text-embedding-3-small"), "embedding_model_not_configured"),
    (lambda: CopilotConfig(embedding_provider="openrouter"), "embedding_model_not_configured"),         # the OpenAI-style default is not an OpenRouter id
    (lambda: cfg(key=None), "semantic_credentials_missing"),
    (lambda: cfg(base_url="https://api.openai.com/v1"), "embedding_base_url_invalid"),
    (lambda: cfg(base_url="http://openrouter.ai/api/v1"), "embedding_base_url_invalid"),
    (lambda: cfg(base_url="https://openrouter.ai.evil.example/api/v1"), "embedding_base_url_invalid"),
    (lambda: cfg(dims=None), "embedding_dimensions_unknown"),
    (lambda: cfg("baai/bge-m3", dims=512), "embedding_dimensions_unsupported"),
    (lambda: cfg("openai/text-embedding-3-small", dims=2048), "embedding_dimensions_exceed_native"),
])
def test_unsafe_openrouter_configuration_is_refused_in_every_environment_without_fallback(env, make, code):
    config = make()
    plan = resolve_embedding_plan(config, environment=env)
    assert not plan.approved and code in plan.problems and plan.provider == "openrouter"
    with pytest.raises(EmbeddingConfigurationError) as x:
        build_embedder(config, environment=env)
    assert code in x.value.codes and KEY not in str(x.value)
    with pytest.raises(EmbeddingConfigurationError):
        OpenRouterEmbedder(config)                                                                  # the class itself refuses too


def test_a_valid_configuration_builds_the_provider_and_status_is_truthful():
    config = cfg()
    for env in ("development", "production"):
        plan = resolve_embedding_plan(config, environment=env)
        assert plan.approved and plan.semantic and plan.identity().to_dict() == {"provider": "openrouter", "model": MODEL, "version": constants.OPENROUTER_EMBEDDING_VERSION,
                                                                                  "dimensions": DIMS}
        assert isinstance(build_embedder(config, environment=env), OpenRouterEmbedder)
    st = embedding_status(config, environment="production")
    assert st["provider"] == "openrouter" and st["approved_for_environment"] and st["base_url"] == constants.OPENROUTER_BASE_URL and KEY not in json.dumps(st)
    assert resolve_embedding_plan(cfg(embedding_version="my-1"), environment="staging").version == "my-1"


def test_hosted_hash_refusal_and_existing_providers_are_unchanged():
    for env in ("staging", "production"):
        with pytest.raises(EmbeddingConfigurationError) as x:
            build_embedder(CopilotConfig(embedding_provider="local"), environment=env)
        assert "hash_embedder_not_allowed" in x.value.codes
    assert isinstance(build_embedder(CopilotConfig(embedding_provider="local"), environment="development"), LocalHashEmbedder)
    assert "embedding_provider_unknown" in resolve_embedding_plan(CopilotConfig(embedding_provider="openrouterx"), environment="production").problems


# ================================================================================================ dimensions parameter
def test_the_dimensions_parameter_is_sent_only_for_a_supporting_model_and_recorded_in_the_identity():
    f = Fake(dims=256)
    e = emb(f, cfg("openai/text-embedding-3-small", dims=256))
    assert e.identity().dimensions == 256 and e.embed_documents(["a"]) == [vec("a", 256)]
    assert f.bodies()[0]["dimensions"] == 256 and f.bodies()[0]["model"] == "openai/text-embedding-3-small"
    f2 = Fake(dims=1536)
    e2 = emb(f2, cfg("openai/text-embedding-3-small", dims=None))
    assert e2.embed_documents(["a"]) == [vec("a", 1536)]
    assert e2.identity().dimensions == 1536 and "dimensions" not in f2.bodies()[0]                  # native size: parameter omitted
    f3 = Fake(dims=1024)
    emb(f3, cfg("baai/bge-m3", dims=1024)).embed_documents(["a"])
    assert "dimensions" not in f3.bodies()[0]                                                       # a model that does not support it never receives it


def test_a_dimension_mismatch_between_declared_and_returned_is_refused():
    f = Fake(dims=1536)                                                                              # the endpoint ignored `dimensions` and returned native size
    e = emb(f, cfg("openai/text-embedding-3-small", dims=256))
    with pytest.raises(EmbeddingProviderError) as x:
        e.embed_documents(["a"])
    assert codes(x) == "dimension_mismatch"
    f2 = Fake(dims=512)                                                                              # an unknown model that returns something else than declared
    with pytest.raises(EmbeddingProviderError) as x:
        emb(f2, cfg(dims=DIMS)).embed_documents(["a"])
    assert codes(x) == "dimension_mismatch"


# ================================================================================================ index manifest identity and no mixing
def chunks(n=3, prefix="c"):
    return [DocumentChunk(chunk_id=f"{prefix}{i}", doc_id=f"d{i}", text=f"Roadmap prioritisation with customer evidence number {i}.") for i in range(n)]


def test_manifest_records_the_openrouter_identity_and_a_model_change_is_incompatible(tmp_path):
    idx = str(tmp_path / "idx")
    a = emb(Fake(), cfg(MODEL))
    ChromaStore(a, persist_dir=idx, collection_name="coll").add_chunks(chunks())
    m = ChromaStore(a, persist_dir=idx, collection_name="coll").index_manifest()
    assert (m.provider, m.model, m.version, m.dimensions) == ("openrouter", MODEL, constants.OPENROUTER_EMBEDDING_VERSION, DIMS) and m.degraded is False
    same = ChromaStore(emb(Fake(), cfg(MODEL)), persist_dir=idx, collection_name="coll")
    assert same.index_status(environment="production").state == IM.OK
    for variant, field in [(dict(model="provider/other-embed"), "model"), (dict(embedding_version="openrouter-2"), "version"), (dict(dims=16), "dimensions")]:
        v = dict(variant)
        other_cfg = cfg(v.pop("model", MODEL), dims=v.pop("dims", DIMS), **v)
        other = ChromaStore(emb(Fake(dims=other_cfg.embedding_dimensions), other_cfg), persist_dir=idx, collection_name="coll")
        st = other.index_status(environment="production")
        assert st.state == IM.MISMATCH and st.refuse and st.fields == (field,)
        with pytest.raises(IndexIncompatibleError):
            other.query("roadmap", top_k=2)
        with pytest.raises(IndexIncompatibleError):
            other.add_chunks(chunks(1, prefix="n"))                                                 # vectors of two models are never mixed
        assert other.count() == 3
    swapped_provider = ChromaStore(emb(Fake(), cfg(MODEL)), persist_dir=idx, collection_name="coll")
    swapped_provider.embedder.provider = "openai"                                                   # same model id under another provider is a different embedding space
    assert swapped_provider.index_status(environment="production").fields == ("provider",)


def test_a_refused_index_makes_no_provider_request(tmp_path):
    idx = str(tmp_path / "idx")
    ChromaStore(emb(Fake(), cfg(MODEL)), persist_dir=idx, collection_name="coll").add_chunks(chunks())
    f = Fake()
    other = ChromaStore(emb(f, cfg("provider/other-embed")), persist_dir=idx, collection_name="coll")
    with pytest.raises(IndexIncompatibleError):
        other.query("roadmap", top_k=1)
    assert f.requests == []                                                                          # refused BEFORE the paid embedding call


def test_controlled_rebuild_into_a_new_index_with_the_openrouter_provider(tmp_path, sf):
    p = Process(tmp_path / "env", environment="development", embedding="local")
    try:
        p.to_active()
        old_count, old_manifest = p.store.count(), p.store.index_manifest()
        governed(sf)
        f = Fake()
        embedder = OpenRouterEmbedder(cfg(), client=f.client())
        target = tmp_path / "rebuilt"
        dry = rebuild_into_new_index(p.sf, p.docs, target_dir=target, embedder=embedder, confirm_embedder=f"openrouter:{MODEL}", execute=False, env=APPROVAL)
        assert dry.ok and not dry.executed and not target.exists() and f.requests == []             # dry-run default: nothing sent, nothing written
        unconfirmed = rebuild_into_new_index(p.sf, p.docs, target_dir=target, embedder=embedder, execute=True, env=APPROVAL)
        assert "embedder_not_confirmed" in unconfirmed.codes and f.requests == []
        no_approval = rebuild_into_new_index(p.sf, p.docs, target_dir=target, embedder=embedder, confirm_embedder=f"openrouter:{MODEL}", execute=True, env={})
        assert not no_approval.ok and "paid_flag_missing" in no_approval.codes and f.requests == []
        rep = rebuild_into_new_index(p.sf, p.docs, target_dir=target, embedder=embedder, active_index_dir=p.root / "chroma",
                                     confirm_embedder=f"openrouter:{MODEL}", execute=True, env=APPROVAL)
        assert rep.ok and rep.executed and rep.counts["chunks_built"] == old_count and rep.index["manifest"]["provider"] == "openrouter"
        assert rep.index["manifest"]["model"] == MODEL and KEY not in json.dumps(rep.to_dict()) and str(tmp_path) not in json.dumps(rep.to_dict())
        new = ChromaStore(OpenRouterEmbedder(cfg(), client=Fake().client()), persist_dir=str(target), collection_name=P.COLLECTION)
        assert new.count() == old_count and new.index_status(environment="production").state == IM.OK
        assert p.store.count() == old_count and p.store.index_manifest() == old_manifest             # rollback = keep the old index: it was not touched
        with sf() as s:
            assert s.execute(select(AiBudgetEntry.category)).scalars().all() and set(s.execute(select(AiBudgetEntry.category)).scalars().all()) == {"embedding"}
    finally:
        p.close()


# ================================================================================================ offline catalogue check
LISTING = {"models": [{"id": "openai/text-embedding-3-small", "embeddings_capable": True}, {"id": "openai/chat-x", "embeddings_capable": False}]}
RAW = {"data": [{"id": "baai/bge-m3", "architecture": {"output_modalities": ["embeddings"]}}, {"id": "vendor/chat", "architecture": {"modality": "text->text"}}]}


def test_catalogue_check_reads_a_recorded_listing_only():
    ok = check_model_in_listing("openai/text-embedding-3-small", LISTING)
    assert ok["ok"] and ok["code"] == "ok" and ok["native_dimensions"] == 1536 and ok["context_tokens"] == 8192
    assert check_model_in_listing("openai/chat-x", LISTING)["code"] == "not_an_embeddings_model"
    assert check_model_in_listing("nope/none", LISTING)["code"] == "model_not_listed"
    assert check_model_in_listing("baai/bge-m3", RAW)["ok"] and check_model_in_listing("vendor/chat", RAW)["code"] == "not_an_embeddings_model"
    assert check_model_in_listing("vendor/chat", RAW, embeddings_listing=True)["ok"]
    for junk in (None, [], {"data": "x"}, {"models": [1, {"no": "id"}]}):
        assert check_model_in_listing("a/b", junk)["code"] == "listing_unreadable"
    assert facts_for("unknown/model") is None


def test_catalogue_script_exit_codes_and_no_network(tmp_path, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_embedding_model", ROOT / "scripts/check_embedding_model.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    good, bad = tmp_path / "l.json", tmp_path / "bad.json"
    good.write_text(json.dumps(LISTING), encoding="utf-8")
    bad.write_text("{nope", encoding="utf-8")
    assert mod.main(["--listing", str(good), "--model", "openai/text-embedding-3-small"]) == 0
    assert mod.main(["--listing", str(good), "--model", "openai/chat-x"]) == 1
    assert mod.main(["--listing", str(bad), "--model", "a/b"]) == 2
    assert mod.main(["--listing", str(tmp_path / "missing.json"), "--model", "a/b"]) == 2
    src = (ROOT / "scripts/check_embedding_model.py").read_text(encoding="utf-8")
    assert "httpx" not in src and "requests" not in src and "socket" not in src
    capsys.readouterr()
