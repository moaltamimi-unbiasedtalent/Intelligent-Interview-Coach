"""02B: explicit embedding resolution, hosted fail-closed vs development warn, no silent fallback, no secrets. Offline; no provider is ever called."""

from __future__ import annotations

import json

import pytest
from pydantic import SecretStr

from src.application.errors import ConfigurationError
from src.copilot import constants
from src.copilot.config import CopilotConfig
from src.copilot.embeddings import (
    EmbeddingConfigurationError, EmbeddingProviderError, LocalHashEmbedder, OpenAIEmbedder, build_embedder, embedding_status,
    resolve_embedding_plan,
)

SECRET = "sk-test-secret-value-never-in-output"
HOSTED = ("staging", "production", "unknown", "prod-eu", "Production ")


def cfg(provider="auto", key=SECRET, **kw) -> CopilotConfig:
    return CopilotConfig(embedding_provider=provider, embedding_api_key=SecretStr(key) if key else None, **kw)


class FakeClient:
    """Stands in for langchain_openai.OpenAIEmbeddings; records calls; never touches a network."""
    dims = 1536
    fail = False

    def __init__(self, **kw):
        self.kw = kw
        self.calls = 0

    def embed_documents(self, texts):
        self.calls += 1
        if self.fail:
            raise RuntimeError(f"upstream 401 for key {SECRET}")
        return [[0.1] * self.dims for _ in texts]

    def embed_query(self, text):
        self.calls += 1
        if self.fail:
            raise RuntimeError(f"upstream 401 for key {SECRET}")
        return [0.1] * self.dims


# ------------------------------------------------------------------ resolution matrix
@pytest.mark.parametrize("env", HOSTED)
def test_hosted_refuses_the_hash_embedder_whether_explicit_or_by_missing_credentials(env):
    explicit = resolve_embedding_plan(cfg("local", key=None), environment=env)
    assert not explicit.approved and "hash_embedder_not_allowed" in explicit.problems and explicit.hosted
    assert "semantic_credentials_missing" not in explicit.problems                      # chosen on purpose, not a fallback
    fallback = resolve_embedding_plan(cfg("auto", key=None), environment=env)
    assert {"hash_embedder_not_allowed", "semantic_credentials_missing"} <= set(fallback.problems)
    for c, kind in ((cfg("local", key=None), "local"), (cfg("auto", key=None), "auto")):
        with pytest.raises(EmbeddingConfigurationError) as e:
            build_embedder(c, environment=env)
        assert "hash_embedder_not_allowed" in e.value.codes and "provider" in e.value.fields


@pytest.mark.parametrize("env", ("development", "dev", "local", "test", ""))
def test_development_stays_permissive_but_is_visibly_labelled(env):
    p = resolve_embedding_plan(cfg("auto", key=None), environment=env)
    assert p.approved and not p.hosted and p.provider == "local" and p.quality_mode == "OFFLINE LEXICAL"
    assert "development only" in p.label and "NOT production quality" in p.label
    assert {"lexical_hash_embedder_development_only", "semantic_credentials_missing_fallback_to_lexical"} <= set(p.warnings)
    assert isinstance(build_embedder(cfg("auto", key=None), environment=env), LocalHashEmbedder)
    st = embedding_status(cfg("auto", key=None), environment=env)
    assert st["degraded"] is True and st["quality_mode"] == "OFFLINE LEXICAL" and "development only" in st["label"]
    # an EXPLICIT local choice in development is not a degradation
    assert embedding_status(cfg("local", key=None), environment=env)["degraded"] is False


def test_hosted_semantic_configuration_resolves_with_recorded_identity():
    p = resolve_embedding_plan(cfg("openai"), environment="production")
    assert p.approved and p.semantic and p.provider == "openai" and p.model == constants.DEFAULT_EMBEDDING_MODEL
    assert p.version == constants.OPENAI_EMBEDDING_VERSION and p.dimensions == 1536
    assert p.identity().compatibility_hash() is not None
    e = build_embedder(cfg("openai"), embeddings_cls=FakeClient, environment="production")
    assert isinstance(e, OpenAIEmbedder) and e.identity() == p.identity()


def test_auto_with_a_dedicated_key_is_semantic_and_chat_key_alone_is_not():
    assert resolve_embedding_plan(cfg("auto"), environment="production").provider == "openai"
    chat_only = CopilotConfig(embedding_provider="auto", api_key=SecretStr(SECRET))
    assert resolve_embedding_plan(chat_only, environment="production").provider == "local"          # unchanged rule: no chat-key fallback


def test_explicit_openai_without_a_key_is_an_error_in_every_environment():
    for env in ("development", "production"):
        with pytest.raises(EmbeddingConfigurationError) as e:
            build_embedder(cfg("openai", key=None), embeddings_cls=FakeClient, environment=env)
        assert e.value.codes == ["semantic_credentials_missing"] and e.value.fields == ("credentials",)
        assert isinstance(e.value, ValueError)                                                     # existing callers catching ValueError still work


def test_dimensions_and_version_are_explicit_configuration():
    big = resolve_embedding_plan(cfg("openai", embedding_model="text-embedding-3-large"), environment="production")
    assert big.dimensions == 3072
    unknown = cfg("openai", embedding_model="vendor-private-model")
    p = resolve_embedding_plan(unknown, environment="production")
    assert "embedding_dimensions_unknown" in p.problems and "dimensions" in p.problem_fields               # hosted never guesses
    with pytest.raises(EmbeddingConfigurationError):
        build_embedder(unknown, embeddings_cls=FakeClient, environment="production")
    dev = resolve_embedding_plan(unknown, environment="development")
    assert dev.approved and "embedding_dimensions_assumed" in dev.warnings
    ok = resolve_embedding_plan(cfg("openai", embedding_model="vendor-private-model", embedding_dimensions=768, embedding_version="2026-10"),
                                environment="production")
    assert ok.approved and ok.dimensions == 768 and ok.version == "2026-10"
    assert ok.identity().compatibility_hash() != resolve_embedding_plan(cfg("openai", embedding_model="vendor-private-model", embedding_dimensions=768,
                                                                            embedding_version="2026-11"), environment="production").identity().compatibility_hash()


def test_unknown_provider_name_is_refused_when_hosted_only():
    assert "embedding_provider_unknown" in resolve_embedding_plan(cfg("cohere"), environment="production").problems
    assert resolve_embedding_plan(cfg("cohere", key=None), environment="development").approved


# ------------------------------------------------------------------ no silent fallback on provider error
def test_provider_error_raises_a_typed_secret_free_error_and_never_falls_back_to_hash():
    class Failing(FakeClient):
        fail = True

    e = build_embedder(cfg("openai"), embeddings_cls=Failing, environment="production")
    for call in (lambda: e.embed_query("q"), lambda: e.embed_documents(["a", "b"])):
        with pytest.raises(EmbeddingProviderError) as exc:
            call()
        assert exc.value.code == "provider_error" and SECRET not in str(exc.value) and "401" not in str(exc.value)
        assert exc.value.__cause__ is None and exc.value.__suppress_context__                       # the provider message is not chained either
    assert isinstance(e, OpenAIEmbedder)                                                            # still the semantic embedder: no swap happened


def test_unusable_vectors_are_refused_not_stored():
    class Wrong(FakeClient):
        dims = 7

    e = build_embedder(cfg("openai"), embeddings_cls=Wrong, environment="production")
    with pytest.raises(EmbeddingProviderError) as exc:
        e.embed_query("q")
    assert exc.value.code == "dimension_mismatch"

    class Short(FakeClient):
        def embed_documents(self, texts):
            return [[0.1] * 1536]

    with pytest.raises(EmbeddingProviderError) as exc2:
        build_embedder(cfg("openai"), embeddings_cls=Short, environment="production").embed_documents(["a", "b"])
    assert exc2.value.code == "unexpected_response"


# ------------------------------------------------------------------ no secrets anywhere
def test_no_secret_in_status_resolution_errors_or_describe():
    c = cfg("openai", embedding_base_url="https://embeddings.internal.example/v1")
    outputs = [json.dumps(embedding_status(c, environment="production")), json.dumps(resolve_embedding_plan(c, environment="production").to_safe_dict()),
               json.dumps(build_embedder(c, embeddings_cls=FakeClient, environment="production").describe())]
    for bad in (cfg("local", key=SECRET), cfg("auto", key=None)):
        with pytest.raises(EmbeddingConfigurationError) as e:
            build_embedder(bad, environment="production")
        outputs += [str(e.value), repr(e.value), json.dumps(e.value.codes), json.dumps(list(e.value.fields))]
    joined = "\n".join(outputs)
    assert SECRET not in joined
    assert SECRET not in repr(c)                                 # SecretStr masks the key in the config repr


def test_factory_turns_a_hosted_refusal_into_the_safe_503_configuration_error(monkeypatch):
    from src.application import factories

    monkeypatch.setenv("API_ENV", "production")
    with pytest.raises(ConfigurationError) as e:
        factories.build_vector_store(cfg("auto", key=None))
    assert "hash_embedder_not_allowed" in str(e.value) and SECRET not in str(e.value)


def test_status_keeps_its_existing_keys_and_adds_the_new_ones():
    st = embedding_status(cfg("auto", key=None), environment="development")
    assert {"provider", "configured_provider", "model", "base_url", "quality_mode"} <= set(st)
    assert {"version", "dimensions", "degraded", "label", "environment", "approved_for_environment", "problems"} <= set(st)
    assert st["model"] == "local-hash-v1"
