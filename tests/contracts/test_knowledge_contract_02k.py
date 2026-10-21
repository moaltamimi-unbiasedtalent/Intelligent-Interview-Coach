"""02K conformance suite: the knowledge runtime / index manifest / scanner CONTRACT.

Packages 02A, 02B and 02C must keep this suite green. Pure and offline: no provider, no network, no database write.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.documents.file_security import (
    EICAR, FakeScanner, FileRejected, FileScanUnavailable, NullScanner, ScanResult, enforce_scan)
from src.knowledge_admin import contracts as C
from src.knowledge_admin.contracts import (
    CompatibilityReport, EmbedderIdentity, IndexManifestV2, LegacyScannerAdapter, RuntimeIdentity, ScannerProtocol, ScanOutcome,
    ScanVerdict, build_runtime_identity, compute_compatibility_hash, data_root_identity, database_fingerprint, embedder_matches,
    identities_compatible, parse_build_metadata, parse_index_record, scan_accepted)

PASSWORD = "s3cr3tP@ss-w0rd"
USER = "ask4mo_svc"
URL_A = f"postgresql+psycopg2://{USER}:{PASSWORD}@db.internal:5432/ask4mo?sslmode=require&password={PASSWORD}"
URL_B = "postgresql://other_user:another-secret@db.internal:5432/ask4mo"
SECRETS = (PASSWORD, USER, "another-secret", "other_user", "sslmode", "sk-live-", "/Users/", "/Volumes/")


def _assert_clean(obj) -> None:
    text = json.dumps(obj.to_dict() if hasattr(obj, "to_dict") else obj, sort_keys=True)
    for s in SECRETS:
        assert s not in text, f"secret-like token {s!r} leaked"


class _Store:
    def __init__(self, n): self.n = n
    def count(self): return self.n


class _Broken:
    def count(self): raise RuntimeError(f"cannot open {PASSWORD}")


def _config(url=URL_A, provider="local"):
    return SimpleNamespace(database_url=url, embedding_provider=provider, embedding_model="text-embedding-3-small",
                           embedding_base_url="https://api.openai.com/v1", embedding_api_key=None)


def _identity(url=URL_A, provider="local", root="/data/a", stores=None):
    return build_runtime_identity(_config(url, provider), data_root=root, stores=stores or {"governed_knowledge": _Store(3)},
                                  job_stats={"workers": {"seen_recently": 1, "last_seen_at": "2026-01-01T00:00:00+00:00",
                                                         "stale_after_seconds": 60, "items": [1]}})


# ------------------------------------------------------------- runtime identity
def test_schema_version_is_declared_everywhere():
    assert C.SCHEMA_VERSION == 1
    assert _identity().schema_version == 1 and IndexManifestV2().schema_version == 1
    assert CompatibilityReport(True).schema_version == 1 and ScanOutcome(ScanVerdict.CLEAN, "x").schema_version == 1


def test_identity_round_trips_and_is_frozen():
    ident = _identity()
    assert RuntimeIdentity.from_dict(json.loads(json.dumps(ident.to_dict()))) == ident
    with pytest.raises(Exception):
        ident.schema_version = 2  # type: ignore[misc]


def test_identity_contains_no_secret_or_path():
    ident = _identity()
    _assert_clean(ident)
    assert ident.database.kind == "postgresql"
    assert ident.collections[0].collection_id == "governed_knowledge" and ident.collections[0].chunk_count == 3
    assert ident.worker.status == "available"


def test_fingerprint_is_stable_and_credential_independent():
    a = database_fingerprint(URL_A)
    assert a == database_fingerprint(URL_A)
    assert a.fingerprint == database_fingerprint("postgresql://x:y@DB.internal:5432/ask4mo").fingerprint   # creds, driver, query, host case
    assert a.fingerprint != database_fingerprint("postgresql://x:y@db.internal:5432/other").fingerprint
    assert a.fingerprint != database_fingerprint("postgresql://x:y@db2.internal:5432/ask4mo").fingerprint
    assert PASSWORD not in json.dumps(a.to_dict())
    assert len(a.fingerprint) == 64


@pytest.mark.parametrize("bad", [None, "", "   ", "not a url at all"])
def test_fingerprint_tolerates_missing_or_garbage(bad):
    ident = database_fingerprint(bad)
    assert ident.kind is None or isinstance(ident.kind, str)
    _assert_clean(ident)


def test_data_root_identity_hides_the_path():
    r = data_root_identity("/Volumes/secret-disk/data")
    _assert_clean(r)
    assert r.label == "knowledge-data-root" and len(r.short_hash) == 12
    assert r == data_root_identity("/Volumes/secret-disk/data") and r != data_root_identity("/other")
    assert data_root_identity(None).short_hash is None


def test_unreadable_store_is_unknown_not_an_error_and_leaks_nothing():
    ident = _identity(stores={"governed_knowledge": _Broken()})
    assert ident.collections[0].chunk_count is None
    _assert_clean(ident)


def test_embedding_degradation_is_reported():
    local = _identity(provider="local").embedding
    assert (local.provider, local.degraded) == ("local", False)
    fallback = _identity(provider="auto").embedding          # auto without a dedicated key falls back to the local embedder
    assert fallback.provider == "local" and fallback.degraded and fallback.degradation_reason == "fallback_to_local_embedder"


def test_builder_tolerates_partial_config_and_no_workers():
    ident = build_runtime_identity(SimpleNamespace(), None)
    assert ident.database.kind is None and ident.worker.status == "unknown" and ident.embedding.provider is None
    _assert_clean(ident)


def test_api_worker_identity_comparison():
    api = _identity()
    same_other_creds = _identity(url=URL_A.replace(PASSWORD, "rotated-password"))
    assert identities_compatible(api, same_other_creds).compatible
    r = identities_compatible(api, _identity(url=URL_B.replace("other_user:another-secret", "u:p").replace("ask4mo", "different")))
    assert not r.compatible and any(m.field == "database.fingerprint" for m in r.mismatches)
    r = identities_compatible(api, _identity(root="/data/b"))
    assert [m.field for m in r.mismatches] == ["data_root.short_hash"]
    r = identities_compatible(api, _identity(stores={"other": _Store(1)}))
    assert [m.field for m in r.mismatches] == ["collections"]
    r = identities_compatible(api, _identity(provider="auto"))
    assert r.compatible                                              # both resolve to local: same provider/model/dimensions
    # chunk counts and heartbeats are time-varying and never a mismatch
    assert identities_compatible(api, _identity(stores={"governed_knowledge": _Store(99)})).compatible
    _assert_clean(r)


def test_unknown_identity_is_never_a_match_and_never_raises():
    empty = build_runtime_identity(SimpleNamespace(), None)
    r = identities_compatible(empty, empty)
    assert not r.compatible and {"database.kind", "database.fingerprint"} <= {m.field for m in r.mismatches}
    base = _identity()
    other_version = C.RuntimeIdentity(base.database, base.data_root, base.collections, base.embedding, schema_version=2)
    assert any(m.field == "schema_version" for m in identities_compatible(_identity(), other_version).mismatches)


# ------------------------------------------------------------- manifest
def test_compatibility_hash_is_deterministic_and_sensitive():
    h = compute_compatibility_hash("openai", "text-embedding-3-small", "1", 1536)
    assert h == compute_compatibility_hash("openai", "text-embedding-3-small", "1", 1536) and len(h) == 64
    assert h != compute_compatibility_hash("local", "text-embedding-3-small", "1", 1536)
    assert h != compute_compatibility_hash("openai", "other", "1", 1536)
    assert h != compute_compatibility_hash("openai", "text-embedding-3-small", "2", 1536)
    assert h != compute_compatibility_hash("openai", "text-embedding-3-small", "1", 512)
    assert compute_compatibility_hash("openai", None, "1", 1536) is None       # unknown stays unknown, never invented


def _manifest(**kw):
    base = dict(provider="openai", model="text-embedding-3-small", version="1", dimensions=1536, vector_metric="cosine",
                collection_id="governed_knowledge", checksum="ab" * 32, built_at="2026-01-01T00:00:00+00:00",
                source_checksums=(("v2", "cd" * 32), ("v1", "ef" * 32)), source_version_ids=("v1", "v2"))
    base.update(kw)
    return IndexManifestV2.create(**base)


def test_manifest_round_trip_and_hash_cannot_be_forged():
    m = _manifest()
    assert m.compatibility_hash == compute_compatibility_hash("openai", "text-embedding-3-small", "1", 1536)
    assert m.source_checksums[0][0] == "v1"                      # sorted for determinism
    assert IndexManifestV2.from_dict(json.loads(json.dumps(m.to_dict(), sort_keys=True))) == m
    forged = dict(m.to_dict(), compatibility_hash="0" * 64, model="other")
    assert IndexManifestV2.from_dict(forged).compatibility_hash != "0" * 64
    _assert_clean(m)


def test_embedder_match_and_mismatch_detection():
    m = _manifest()
    ok = embedder_matches(m, EmbedderIdentity("openai", "text-embedding-3-small", "1", 1536))
    assert ok.compatible and not ok.mismatched_fields
    bad = embedder_matches(m, EmbedderIdentity("local", "local-hash-v1", "1", 512))
    assert not bad.compatible and bad.mismatched_fields == ("provider", "model", "dimensions")
    assert embedder_matches(m, EmbedderIdentity("openai", "text-embedding-3-small", "1", 3072)).mismatched_fields == ("dimensions",)
    unknown = embedder_matches(m, EmbedderIdentity("openai", "text-embedding-3-small", None, 1536))
    assert not unknown.compatible and unknown.unknown_fields == ("version",)
    assert embedder_matches(_manifest(degraded=True, degradation_reason="x"), EmbedderIdentity("openai", "text-embedding-3-small", "1", 1536)).manifest_degraded


def test_legacy_build_metadata_is_tolerated_without_inventing():
    legacy = {"runtime_pipeline_version": "rt-1", "built_at": "2025-05-05T10:00:00Z", "git_commit": "abc", "unexpected": {"x": 1}}
    m = parse_build_metadata(legacy)
    assert m.built_at == "2025-05-05T10:00:00Z"
    assert (m.provider, m.model, m.version, m.dimensions, m.compatibility_hash, m.checksum) == (None,) * 6
    assert not embedder_matches(m, EmbedderIdentity("openai", "m", "1", 3)).compatible
    for junk in (None, {}, [], "text", {"source_versions": 5}, {"embedding": "x"}, {"embedding": {"dimensions": "abc"}}):
        parse_build_metadata(junk)                                # never raises
    assert parse_build_metadata({"source_versions": {"b": "1", "a": "2"}}).source_version_ids == ("a", "b")
    full = parse_build_metadata({"built_at": "t", "embedding": {"provider": "local", "model": "local-hash-v1", "version": "1",
                                                                "dimensions": 512, "metric": "cosine"}})
    assert full.compatibility_hash == compute_compatibility_hash("local", "local-hash-v1", "1", 512)
    assert legacy == {"runtime_pipeline_version": "rt-1", "built_at": "2025-05-05T10:00:00Z", "git_commit": "abc", "unexpected": {"x": 1}}


def test_governed_index_record_is_parsed_read_only():
    rec = SimpleNamespace(collection="governed_knowledge", embedder="LocalHashEmbedder", chunk_count=4, state="built",
                          built_at=__import__("datetime").datetime(2026, 1, 2, tzinfo=__import__("datetime").timezone.utc))
    m = parse_index_record(rec, "ver_1")
    assert m.collection_id == "governed_knowledge" and m.embedder_label == "LocalHashEmbedder" and m.source_version_ids == ("ver_1",)
    assert m.provider is None and m.dimensions is None and m.compatibility_hash is None
    assert m.built_at.startswith("2026-01-02")
    assert parse_index_record({"collection": "c", "built_at": None}).built_at is None
    parse_index_record(SimpleNamespace())                          # tolerates a missing everything


def test_manifest_has_no_secret_even_with_hostile_input():
    m = parse_build_metadata({"built_at": "t", "embedding": {"provider": "openai", "model": "m"}})
    _assert_clean(m)


# ------------------------------------------------------------- scanner
def test_adapter_conforms_to_protocol_and_maps_verdicts():
    fake = LegacyScannerAdapter(FakeScanner())
    assert isinstance(fake, ScannerProtocol)
    assert fake.scan(b"hello", "a.txt").verdict is ScanVerdict.CLEAN and fake.scan(b"hello", "a.txt").real_scan
    assert fake.scan(EICAR, "a.txt").verdict is ScanVerdict.INFECTED
    null = LegacyScannerAdapter(NullScanner()).scan(b"x", "a.txt")
    assert null.verdict is ScanVerdict.CLEAN and null.real_scan is False   # a no-op scanner never claims a real scan


class _Down:
    name = "down"
    def available(self): return False
    def scan(self, data, filename): raise FileScanUnavailable("down")


class _Raises:
    name = "raises"
    def available(self): return True
    def scan(self, data, filename): raise FileScanUnavailable("boom")


def test_unavailable_scanner_is_a_verdict_not_an_exception():
    assert LegacyScannerAdapter(_Down()).scan(b"x", "f").verdict is ScanVerdict.UNAVAILABLE
    assert LegacyScannerAdapter(_Raises()).scan(b"x", "f").verdict is ScanVerdict.UNAVAILABLE


@pytest.mark.parametrize("legacy,data", [(FakeScanner(), b"clean"), (FakeScanner(), EICAR), (NullScanner(), b"clean"),
                                         (_Down(), b"x"), (_Raises(), b"x")])
@pytest.mark.parametrize("required", [True, False])
def test_fail_closed_rule_matches_enforce_scan(legacy, data, required):
    """``scan_accepted`` must agree with the existing ``enforce_scan`` for every scanner/required combination."""
    try:
        enforce_scan(data, "f.txt", scanner=legacy, required=required)
        expected = True
    except (FileRejected, FileScanUnavailable):
        expected = False
    assert scan_accepted(LegacyScannerAdapter(legacy).scan(data, "f.txt"), required=required) is expected


def test_fail_closed_rule_direct():
    assert not scan_accepted(ScanOutcome(ScanVerdict.UNAVAILABLE, "x"), required=True)
    assert not scan_accepted(ScanOutcome(ScanVerdict.UNAVAILABLE, "x"), required=False)
    assert not scan_accepted(ScanOutcome(ScanVerdict.CLEAN, "null", real_scan=False), required=True)
    assert not scan_accepted(ScanOutcome(ScanVerdict.INFECTED, "x", real_scan=True), required=False)
    assert scan_accepted(ScanOutcome(ScanVerdict.CLEAN, "clamav", real_scan=True), required=True)
    assert ScanOutcome(ScanVerdict.CLEAN, "x").to_dict()["verdict"] == "clean"


def test_legacy_scanner_module_is_unchanged():
    r = FakeScanner().scan(b"a", "f")
    assert r == ScanResult(clean=True, scanner="fake", detail="no signatures matched")
