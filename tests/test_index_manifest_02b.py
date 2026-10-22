"""02B: persisted index manifests, the compatibility matrix, query-time refusal and the no-mixing write guard. Offline; real Chroma on a temp directory."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.copilot import index_manifest as IM
from src.copilot.embeddings import LocalHashEmbedder
from src.copilot.index_manifest import IndexIncompatibleError
from src.copilot.models import DocumentChunk
from src.copilot.retrieval.hybrid import HybridRetriever
from src.copilot.retrieval.keyword import KeywordRetriever
from src.copilot.retrieval.vector import VectorRetriever
from src.copilot.vectorstore import ChromaStore, InMemoryVectorStore
from src.knowledge_admin.contracts import EmbedderIdentity, IndexManifestV2
from tests._knowledge_env_02a import FakeSemanticEmbedder, release_chroma

LIVE = EmbedderIdentity("openai", "m-1", "v-1", 8)


def manifest(**over) -> IndexManifestV2:
    base = dict(provider="openai", model="m-1", version="v-1", dimensions=8, collection_id="c")
    return IndexManifestV2.create(**{**base, **over})


class Fake(FakeSemanticEmbedder):
    """Semantic-labelled offline embedder with a configurable identity."""

    def __init__(self, model="fake-semantic-test", version="test-1", dimensions=512, provider="openai"):
        super().__init__()
        self.model, self.version, self.provider = model, version, provider
        self.dimensions = dimensions
        self._h = LocalHashEmbedder(dimensions)


def chunks(n=3, prefix="c"):
    return [DocumentChunk(chunk_id=f"{prefix}{i}", doc_id=f"d{i}", text=f"Roadmap prioritisation with customer evidence number {i}.") for i in range(n)]


# ------------------------------------------------------------------ compatibility matrix (pure)
def test_matrix_match():
    s = IM.evaluate_index(manifest(), LIVE, count=5, hosted=True)
    assert s.state == IM.OK and not s.refuse and s.compatible and s.fields == ()


@pytest.mark.parametrize("field,value", [("provider", "other"), ("model", "m-2"), ("version", "v-2"), ("dimensions", 16)])
@pytest.mark.parametrize("hosted", (True, False))
def test_matrix_each_mismatched_field_is_refused_in_every_environment_and_named(field, value, hosted):
    s = IM.evaluate_index(manifest(**{field: value}), LIVE, count=5, hosted=hosted)
    assert s.state == IM.MISMATCH and s.refuse and s.fields == (field,)
    assert not s.compatible
    with pytest.raises(IndexIncompatibleError) as e:
        IM.raise_if_refused(s)
    assert e.value.fields == (field,) and e.value.codes == [IM.MISMATCH]
    assert "m-2" not in str(e.value) and "v-2" not in str(e.value)                      # names the field, never the value
    assert json.dumps(s.to_safe_dict()).count("differing_fields") == 1


def test_matrix_several_mismatches_are_all_named():
    s = IM.evaluate_index(manifest(model="x", dimensions=1), LIVE, count=2, hosted=False)
    assert s.state == IM.MISMATCH and set(s.fields) == {"model", "dimensions"}


@pytest.mark.parametrize("field", ["provider", "model", "version", "dimensions"])
def test_matrix_unknown_is_never_a_match_refused_hosted_warned_in_development(field):
    unknown_manifest = IM.evaluate_index(manifest(**{field: None}), LIVE, count=5, hosted=True)
    assert unknown_manifest.state == IM.UNKNOWN_FIELDS and unknown_manifest.refuse and unknown_manifest.fields == (field,)
    dev = IM.evaluate_index(manifest(**{field: None}), LIVE, count=5, hosted=False)
    assert dev.state == IM.UNKNOWN_FIELDS and not dev.refuse and not dev.compatible        # not OK, merely not refused
    live_unknown = EmbedderIdentity(**{**LIVE.to_dict(), field: None})
    assert IM.evaluate_index(manifest(), live_unknown, count=5, hosted=True).fields == (field,)


def test_matrix_missing_unreadable_and_degraded_manifests():
    assert IM.evaluate_index(None, LIVE, count=5, hosted=True).refuse and IM.evaluate_index(None, LIVE, count=5, hosted=True).state == IM.NO_MANIFEST
    assert not IM.evaluate_index(None, LIVE, count=5, hosted=False).refuse
    assert IM.evaluate_index(None, LIVE, count=5, hosted=True, unreadable=True).state == IM.UNREADABLE
    assert IM.evaluate_index(None, LIVE, count=0, hosted=True).state == IM.EMPTY                  # nothing to mismatch yet
    deg = manifest(degraded=True, degradation_reason=IM.LEXICAL_DEGRADATION)
    assert IM.evaluate_index(deg, LIVE, count=5, hosted=True).state == IM.DEGRADED_INDEX
    assert IM.evaluate_index(deg, LIVE, count=5, hosted=False).state == IM.OK


def test_matrix_the_hash_embedder_is_refused_when_hosted_regardless_of_the_index():
    h = LocalHashEmbedder().identity()
    s = IM.evaluate_index(manifest(provider="local", model=h.model, version=h.version, dimensions=h.dimensions), h, count=5, hosted=True)
    assert s.state == IM.HASH_HOSTED and s.refuse
    assert IM.evaluate_index(None, h, count=0, hosted=True).state == IM.HASH_HOSTED                # even an empty hosted collection
    assert not IM.evaluate_index(manifest(provider="local", model=h.model, version=h.version, dimensions=h.dimensions), h, count=5, hosted=False).refuse


# ------------------------------------------------------------------ persistence (Chroma sidecar and in-memory)
def stores(tmp_path):
    return {"memory": lambda emb: InMemoryVectorStore(emb, collection_name="coll"),
            "chroma": lambda emb: ChromaStore(emb, persist_dir=str(tmp_path / "idx"), collection_name="coll")}


@pytest.mark.parametrize("kind", ["memory", "chroma"])
def test_every_collection_persists_a_manifest_with_provider_model_version_dimensions_and_hash(tmp_path, kind):
    try:
        store = stores(tmp_path)[kind](Fake())
        assert store.index_manifest() is None
        store.add_chunks(chunks())
        m = store.index_manifest()
        assert (m.provider, m.model, m.version, m.dimensions) == ("openai", "fake-semantic-test", "test-1", 512)
        assert m.compatibility_hash == EmbedderIdentity("openai", "fake-semantic-test", "test-1", 512).compatibility_hash()
        assert m.collection_id == "coll" and m.vector_metric == "cosine" and m.checksum and m.built_at and not m.degraded
        assert store.index_status(environment="production").state == IM.OK
        before = m.checksum
        store.add_chunks(chunks(2, prefix="z"))
        assert store.index_manifest().checksum != before                                    # the checksum follows the content
        mid = store.index_manifest().checksum
        assert store.delete_where({"doc_id": "d0"}) == 2          # c0 and z0 share doc d0
        assert store.index_manifest().checksum != mid and store.index_manifest().model == "fake-semantic-test"      # a deletion keeps the manifest truthful
    finally:
        release_chroma()


def test_a_hash_built_index_is_labelled_degraded_in_its_manifest(tmp_path):
    store = InMemoryVectorStore(LocalHashEmbedder(), collection_name="coll")
    store.add_chunks(chunks())
    m = store.index_manifest()
    assert m.degraded and m.degradation_reason == IM.LEXICAL_DEGRADATION and m.provider == "local"
    assert store.index_status(environment="development").state == IM.OK
    assert store.index_status(environment="production").state == IM.HASH_HOSTED


def test_chroma_manifest_survives_reopen_and_travels_with_the_index_directory(tmp_path):
    try:
        ChromaStore(Fake(), persist_dir=str(tmp_path / "idx"), collection_name="coll").add_chunks(chunks())
        reopened = ChromaStore(Fake(), persist_dir=str(tmp_path / "idx"), collection_name="coll")
        assert reopened.index_status(environment="production").state == IM.OK
        f = IM.manifest_file(tmp_path / "idx", "coll")
        assert f.exists() and f.is_relative_to(tmp_path / "idx")                              # inside the index directory, so a backup copies it
        assert "knowledge-manifests" in str(f)
    finally:
        release_chroma()


def test_reset_removes_the_manifest_and_a_new_embedder_may_then_build(tmp_path):
    try:
        store = ChromaStore(Fake(), persist_dir=str(tmp_path / "idx"), collection_name="coll")
        store.add_chunks(chunks())
        store.reset()
        assert store.index_manifest() is None
        other = ChromaStore(Fake(model="other"), persist_dir=str(tmp_path / "idx"), collection_name="coll")
        other.add_chunks(chunks())
        assert other.index_manifest().model == "other"
    finally:
        release_chroma()


# ------------------------------------------------------------------ query refusal and the no-mixing write guard
@pytest.mark.parametrize("field,variant", [("model", dict(model="other-model")), ("version", dict(version="test-2")),
                                           ("provider", dict(provider="cohere")), ("dimensions", dict(dimensions=256))])
def test_query_and_write_with_an_incompatible_embedder_are_refused_naming_the_field(tmp_path, field, variant):
    try:
        ChromaStore(Fake(), persist_dir=str(tmp_path / "idx"), collection_name="coll").add_chunks(chunks())
        other = ChromaStore(Fake(**variant), persist_dir=str(tmp_path / "idx"), collection_name="coll")
        with pytest.raises(IndexIncompatibleError) as e:
            other.query("roadmap", top_k=3)
        assert e.value.fields == (field,)
        with pytest.raises(IndexIncompatibleError):
            other.add_chunks(chunks(1, prefix="n"))                                             # vectors of two embedders are never mixed
        assert other.count() == 3
    finally:
        release_chroma()


def test_refusal_happens_before_any_embedding_call(tmp_path):
    class Counting(Fake):
        calls = 0

        def embed_query(self, text):
            Counting.calls += 1
            return super().embed_query(text)

        def embed_documents(self, texts):
            Counting.calls += 1
            return super().embed_documents(texts)

    store = InMemoryVectorStore(Fake(), collection_name="coll")
    store.add_chunks(chunks())
    store.embedder = Counting(model="other")
    with pytest.raises(IndexIncompatibleError):
        store.query("q", top_k=2)
    with pytest.raises(IndexIncompatibleError):
        store.add_chunks(chunks(1, prefix="n"))
    assert Counting.calls == 0                                                                  # a refused request never spends a paid embedding call


def test_incompatible_index_is_degraded_not_an_empty_result_in_the_hybrid_retriever():
    store = InMemoryVectorStore(Fake(), collection_name="coll")
    store.add_chunks(chunks())
    store.embedder = Fake(model="other")
    hybrid = HybridRetriever(VectorRetriever(store), KeywordRetriever.from_store(store))
    result = hybrid.search("roadmap prioritisation customer evidence", top_k=3)
    assert "vector" in result.degraded                                                          # the vector channel is reported degraded
    assert result.vector == []                                                                  # and is NOT silently presented as "no matching vectors"
    with pytest.raises(IndexIncompatibleError):
        VectorRetriever(store).retrieve("roadmap", top_k=3)                                     # the direct path raises instead of returning []


def test_legacy_index_without_manifest_hosted_refuses_development_serves_and_stays_unproven(tmp_path, monkeypatch):
    store = InMemoryVectorStore(Fake(), collection_name="coll")
    store.add_chunks(chunks())
    store._manifest = None                                                                       # a pre-02B index: vectors exist, no manifest
    monkeypatch.setenv("API_ENV", "production")
    with pytest.raises(IndexIncompatibleError) as e:
        store.query("roadmap", top_k=2)
    assert e.value.codes == [IM.NO_MANIFEST] and e.value.fields == ("manifest",)
    with pytest.raises(IndexIncompatibleError):
        store.add_chunks(chunks(1, prefix="n"))
    monkeypatch.setenv("API_ENV", "development")
    assert store.query("roadmap", top_k=2)                                                      # development keeps working
    store.add_chunks(chunks(1, prefix="n"))
    assert store.index_manifest() is None                                                       # and an unknown embedder is never invented into a manifest


def test_hosted_store_with_the_hash_embedder_refuses_query_and_write(monkeypatch):
    store = InMemoryVectorStore(LocalHashEmbedder(), collection_name="coll")
    monkeypatch.setenv("API_ENV", "staging")
    with pytest.raises(IndexIncompatibleError) as e:
        store.add_chunks(chunks())
    assert e.value.codes == [IM.HASH_HOSTED]
    with pytest.raises(IndexIncompatibleError):
        store.query("q", top_k=1)


def test_a_corrupt_manifest_is_unprovable_never_invented(tmp_path, monkeypatch):
    try:
        store = ChromaStore(Fake(), persist_dir=str(tmp_path / "idx"), collection_name="coll")
        store.add_chunks(chunks())
        Path(IM.manifest_file(tmp_path / "idx", "coll")).write_text("{not json", encoding="utf-8")
        assert store.index_status(environment="production").state == IM.UNREADABLE
        monkeypatch.setenv("API_ENV", "production")
        with pytest.raises(IndexIncompatibleError):
            store.query("roadmap", top_k=1)
        assert store.index_status(environment="development").refuse is False
    finally:
        release_chroma()


def test_safe_dict_and_errors_carry_no_path_secret_or_vector(tmp_path):
    try:
        store = ChromaStore(Fake(), persist_dir=str(tmp_path / "idx"), collection_name="coll")
        store.add_chunks(chunks())
        dump = json.dumps(store.index_status(environment="production").to_safe_dict())
        assert str(tmp_path) not in dump and "knowledge-manifests" not in dump and "Roadmap" not in dump and "embedding" not in dump.replace("embedder", "")
        other = ChromaStore(Fake(model="leaky-model-name"), persist_dir=str(tmp_path / "idx"), collection_name="coll")
        with pytest.raises(IndexIncompatibleError) as e:
            other.query("q", top_k=1)
        assert "leaky-model-name" not in str(e.value) and str(tmp_path) not in str(e.value)
    finally:
        release_chroma()


def test_manifest_write_is_atomic_and_leaves_no_temporary_file(tmp_path):
    path = IM.manifest_file(tmp_path, "coll")
    IM.write_manifest(path, manifest())
    IM.write_manifest(path, manifest(model="m-2"))
    assert IM.read_manifest(path).model == "m-2"
    assert [p.name for p in path.parent.iterdir()] == [path.name]
