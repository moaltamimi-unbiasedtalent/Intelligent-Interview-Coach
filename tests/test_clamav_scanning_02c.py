"""02C: real ClamAV (clamd INSTREAM) scanning, fail closed, for candidate documents and governed knowledge.

Offline and deterministic: a FAKE clamd TCP server on 127.0.0.1 (ephemeral port) is the only "scanner". No real clamd, no docker, no outside network.
"""

from __future__ import annotations

import os
import socket
import tempfile
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

os.environ.setdefault("DOCUMENT_STORAGE_DIR", tempfile.mkdtemp(prefix="ask4mo_doc_test_02c_"))

from src.copilot.embeddings import LocalHashEmbedder
from src.copilot.vectorstore import InMemoryVectorStore
from src.documents import file_security as fs
from src.documents.file_security import (
    ClamAvScanner, ClamdClient, FakeScanner, FileRejected, FileScanUnavailable, FileTooLarge, NullScanner, ScanResult, ScanStatus,
    enforce_scan, parse_clamd_reply, parse_signature_age_days,
)
from src.jobs.service import JobService
from src.jobs.worker import Worker
from src.knowledge_admin import alerts as KA
from src.knowledge_admin.runtime import KnowledgeRuntime
from src.knowledge_admin.service import KnowledgeAdminService
from src.persistence import AdminNotification, KnowledgeSourceVersion as V
from tests._fake_clamd import FakeClamd, eicar_bytes
from tests.test_admin_foundation_w10_1 import Env

API = "/api/v1"
DOC = ("Digital product managers prioritise a roadmap using customer evidence. A product manager defines outcomes, "
       "works with engineering, and measures adoption.\n\nInterview preparation for product roles covers prioritisation frameworks.")
META = dict(language="en", authority_level=2, publisher="Example Framework Body", provenance_note="Published public framework; downloaded 2026-10-01.",
            licence_class="public_official")


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def client(srv, **kw) -> ClamdClient:
    kw.setdefault("connect_timeout", 1.0)
    kw.setdefault("scan_timeout", 5.0)
    return ClamdClient("127.0.0.1", srv.port if hasattr(srv, "port") else srv, **kw)


# ------------------------------------------------------------------ protocol client
def test_clean_and_infected_through_the_real_client():
    with FakeClamd() as srv:
        c = client(srv)
        assert c.instream(b"hello world").status is ScanStatus.CLEAN
        r = c.instream(b"prefix " + eicar_bytes())
        assert r.status is ScanStatus.INFECTED and r.signature == "Win.Test.EICAR_HDB-1"
        assert srv.commands[0] == b"zINSTREAM\x00"


def test_stream_is_length_prefixed_chunked_and_zero_terminated():
    with FakeClamd() as srv:
        c = client(srv, chunk_bytes=1000)
        assert c.instream(b"a" * 4500).status is ScanStatus.CLEAN
        assert srv.chunks_seen == [1000, 1000, 1000, 1000, 500] and srv.received == [4500]


def test_empty_stream_is_scanned_not_skipped():
    with FakeClamd() as srv:
        assert client(srv).instream(b"").status is ScanStatus.CLEAN
        assert srv.received == [0]


def test_ping_version_and_health():
    with FakeClamd() as srv:
        c = client(srv)
        assert c.ping() is True and c.version().startswith("ClamAV 1.0.1")
        assert srv.commands[0] == b"zPING\x00"


def test_connection_refused_is_unavailable():
    c = client(free_port())
    assert c.instream(b"x").status is ScanStatus.UNAVAILABLE
    assert c.ping() is False and c.version() is None


def test_silent_server_times_out_within_the_deadline():
    import time
    with FakeClamd("timeout") as srv:
        c = client(srv, scan_timeout=0.4)
        t0 = time.monotonic()
        assert c.instream(b"x").status is ScanStatus.TIMEOUT
        assert time.monotonic() - t0 < 2.0


def test_slow_server_is_bounded_by_the_total_deadline_but_a_patient_client_succeeds():
    with FakeClamd("slow") as srv:
        assert client(srv, scan_timeout=0.4).instream(b"x").status is ScanStatus.TIMEOUT
    with FakeClamd("slow") as srv:
        assert client(srv, scan_timeout=6.0).instream(b"x").status is ScanStatus.CLEAN


def test_partial_reads_are_reassembled():
    with FakeClamd("partial") as srv:
        c = client(srv)
        assert c.instream(b"x").status is ScanStatus.CLEAN
        assert c.instream(eicar_bytes()).status is ScanStatus.INFECTED


@pytest.mark.parametrize("mode", ["malformed", "error", "empty", "multiline", "closed_early"])
def test_malformed_error_empty_and_truncated_replies_are_errors_never_clean(mode):
    with FakeClamd(mode) as srv:
        assert client(srv).instream(b"x").status in (ScanStatus.ERROR, ScanStatus.UNAVAILABLE)


def test_over_the_local_limit_is_too_large_and_never_streamed():
    with FakeClamd() as srv:
        assert client(srv, max_stream_bytes=100).instream(b"x" * 101).status is ScanStatus.TOO_LARGE
        assert srv.commands == []                               # nothing was sent


def test_server_side_size_limit_is_too_large():
    with FakeClamd("size_limit", max_stream=2000) as srv:
        assert client(srv, chunk_bytes=500).instream(b"x" * 5000).status is ScanStatus.TOO_LARGE


@pytest.mark.parametrize("raw,status,sig", [
    (b"stream: OK\x00", ScanStatus.CLEAN, None),
    (b"stream: OK\n", ScanStatus.CLEAN, None),
    (b"stream: Win.Test.EICAR_HDB-1 FOUND\x00", ScanStatus.INFECTED, "Win.Test.EICAR_HDB-1"),
    (b"stream: Bad Name; rm -rf / FOUND\x00", ScanStatus.INFECTED, "unnamed-signature"),
    (b"stream: " + b"A" * 150 + b" FOUND\x00", ScanStatus.INFECTED, "unnamed-signature"),
    (b"INSTREAM size limit exceeded. ERROR\x00", ScanStatus.TOO_LARGE, None),
    (b"anything. ERROR\x00", ScanStatus.ERROR, None),
    (b"", ScanStatus.ERROR, None), (b"\x00", ScanStatus.ERROR, None), (b"stream: banana", ScanStatus.ERROR, None),
    (b"stream: OK stream: x FOUND", ScanStatus.INFECTED, "unnamed-signature"), (b"\xff\xfe\x00", ScanStatus.ERROR, None),
])
def test_reply_parsing_is_strict_and_signature_is_bounded_and_safe(raw, status, sig):
    r = parse_clamd_reply(raw)
    assert r.status is status and r.signature == sig


def test_signature_age_parsing():
    now = datetime(2026, 10, 22, tzinfo=timezone.utc)
    assert parse_signature_age_days("ClamAV 1.0.1/27000/Mon Oct 19 08:00:00 2026", now=now) == 2
    assert parse_signature_age_days("ClamAV 1.0.1", now=now) is None
    assert parse_signature_age_days("ClamAV 1.0.1/1/garbage", now=now) is None


def test_health_reports_fresh_and_stale_signatures():
    fresh = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%a %b %d %H:%M:%S %Y")
    stale = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%a %b %d %H:%M:%S %Y")
    with FakeClamd(version=f"ClamAV 1.0.1/27000/{fresh}") as srv:
        h = ClamAvScanner("127.0.0.1", srv.port).health()
        assert h["reachable"] and h["signatures"] == "fresh" and h["version"] == "ClamAV 1.0.1"
    with FakeClamd(version=f"ClamAV 1.0.1/27000/{stale}") as srv:
        h = ClamAvScanner("127.0.0.1", srv.port).health()
        assert h["signatures"] == "stale" and h["signature_age_days"] >= 29
    h = ClamAvScanner("127.0.0.1", free_port()).health()
    assert h == {"reachable": False, "version": None, "signature_age_days": None, "signatures": "unknown"}


# ------------------------------------------------------------------ scanner + enforce_scan
def test_typed_results_never_carry_content_or_paths():
    with FakeClamd() as srv:
        sc = ClamAvScanner("127.0.0.1", srv.port)
        r = sc.scan(b"SECRET-CONTENT " + eicar_bytes(), "/private/path/cv.pdf")
        assert r.status == "infected" and r.clean is False and r.scanner == "clamav"
        text = repr(r)
        assert "SECRET-CONTENT" not in text and "/private/path" not in text and "cv.pdf" not in text
        ok = sc.scan(b"fine", "cv.pdf")
        assert ok.clean and ok.status == "clean" and ok.signature is None


def test_scanresult_is_internally_consistent():
    assert ScanResult(clean=True, scanner="x").status == "clean" and ScanResult(clean=False, scanner="x").status == "infected"
    with pytest.raises(ValueError):
        ScanResult(clean=True, scanner="x", status="infected")
    with pytest.raises(ValueError):
        ScanResult(clean=False, scanner="x", status="clean")


def test_enforce_scan_maps_every_outcome_fail_closed(monkeypatch):
    with FakeClamd() as srv:
        sc = ClamAvScanner("127.0.0.1", srv.port, max_stream_bytes=100)
        assert enforce_scan(b"clean", "a.txt", scanner=sc, required=True).clean
        with pytest.raises(FileRejected) as e:
            enforce_scan(eicar_bytes(), "a.txt", scanner=sc, required=True)
        assert not isinstance(e.value, FileTooLarge) and e.value.status == "infected" and e.value.signature
        with pytest.raises(FileTooLarge):
            enforce_scan(b"x" * 101, "a.txt", scanner=sc, required=True)
    down = ClamAvScanner("127.0.0.1", free_port())
    with pytest.raises(FileScanUnavailable):
        enforce_scan(b"x", "a.txt", scanner=down, required=True)
    with pytest.raises(FileScanUnavailable):
        enforce_scan(b"x", "a.txt", scanner=down, required=False)            # even when optional: a scanner that cannot scan never passes
    with FakeClamd("timeout") as srv:
        with pytest.raises(FileScanUnavailable) as e2:
            enforce_scan(b"x", "a.txt", scanner=ClamAvScanner("127.0.0.1", srv.port, scan_timeout=0.3), required=True)
        assert e2.value.status == "timeout"
    for mode in ("malformed", "error", "empty"):
        with FakeClamd(mode) as srv:
            with pytest.raises(FileScanUnavailable):
                enforce_scan(b"x", "a.txt", scanner=ClamAvScanner("127.0.0.1", srv.port), required=True)


def test_enforce_scan_still_refuses_null_when_required_and_never_claims_clean_from_it():
    with pytest.raises(FileScanUnavailable):
        enforce_scan(b"x", "a", scanner=NullScanner(), required=True)
    assert enforce_scan(b"x", "a", scanner=NullScanner(), required=False).scanner == "null"


def test_fake_scanner_is_a_development_simulation_refused_when_hosted(monkeypatch):
    monkeypatch.delenv("API_ENV", raising=False)
    assert enforce_scan(b"x", "a", scanner=FakeScanner(), required=True).clean
    for env in ("staging", "production"):
        monkeypatch.setenv("API_ENV", env)
        with pytest.raises(FileScanUnavailable):
            enforce_scan(b"x", "a", scanner=FakeScanner(), required=True)
        with pytest.raises(FileScanUnavailable):
            enforce_scan(b"x", "a", scanner=FakeScanner(), required=False)
        with pytest.raises(FileScanUnavailable):
            enforce_scan(b"x", "a", scanner=NullScanner(), required=False)
        assert fs.scan_required() is True                                       # hosted: required regardless of the flag


def test_build_file_scanner_reads_bounded_settings(monkeypatch):
    monkeypatch.setenv("FILE_SCAN_PROVIDER", "clamav")
    monkeypatch.setenv("CLAMAV_HOST", "scanner.internal")
    monkeypatch.setenv("CLAMAV_PORT", "not-a-number")
    sc = fs.build_file_scanner()
    assert isinstance(sc, ClamAvScanner) and sc._client._port == 3310 and sc._client._host == "scanner.internal"
    monkeypatch.setenv("FILE_SCAN_PROVIDER", "fake")
    assert isinstance(fs.build_file_scanner(), FakeScanner)
    monkeypatch.delenv("FILE_SCAN_PROVIDER")
    assert isinstance(fs.build_file_scanner(), NullScanner)


def test_no_connection_is_opened_at_import_or_construction():
    sc = ClamAvScanner("203.0.113.1", 3310)          # TEST-NET-1: constructing must not touch the network
    assert sc.name == "clamav"


# ------------------------------------------------------------------ candidate documents through the real routes
@pytest.fixture()
def users():
    from tests.test_documents_api import _two_users
    c, a, b, repo = _two_users()
    yield c, a, b, repo
    c.__exit__(None, None, None)


def _doc_post(c, tok, data=b"Jane Doe\nSenior Engineer at Acme\n- Reduced latency by 40%\n", name="cv.txt"):
    from tests._auth_factories import cookies_for
    return c.post(f"{API}/documents", files={"file": (name, data, "text/plain")}, data={"category": "cv"}, cookies=cookies_for(tok))


def _scan_env(monkeypatch, port, **extra):
    monkeypatch.setenv("FILE_SCAN_PROVIDER", "clamav")
    monkeypatch.setenv("CLAMAV_HOST", "127.0.0.1")
    monkeypatch.setenv("CLAMAV_PORT", str(port))
    monkeypatch.setenv("MALWARE_SCAN_REQUIRED", "true")
    for k, v in extra.items():
        monkeypatch.setenv(k, str(v))


def _alerts(repo):
    with repo.session_factory() as s:
        return {r.dedupe_key: r.state for r in s.scalars(select(AdminNotification)).all()}


def test_candidate_upload_clean_is_accepted_and_scanned_for_real(users, monkeypatch):
    c, a, b, repo = users
    with FakeClamd() as srv:
        _scan_env(monkeypatch, srv.port)
        r = _doc_post(c, a)
        assert r.status_code == 201
        assert srv.received and b"zINSTREAM\x00" in srv.commands


def test_candidate_upload_infected_is_422_not_stored_and_not_an_outage(users, monkeypatch):
    from tests._auth_factories import cookies_for
    c, a, b, repo = users
    with FakeClamd() as srv:
        _scan_env(monkeypatch, srv.port)
        r = _doc_post(c, a, data=b"cv text " + eicar_bytes())
        assert r.status_code == 422 and r.json()["error"]["code"] == "scan_infected"
        assert "Win.Test" not in r.text and "EICAR" not in r.text                  # no signature or content leaks to the candidate
        assert c.get(f"{API}/documents", cookies=cookies_for(a)).json()["documents"] == []
        assert "scanner_unavailable" not in _alerts(repo)                            # an infection is not a scanner outage


def test_candidate_upload_scanner_down_is_503_fail_closed_and_alerts(users, monkeypatch):
    from tests._auth_factories import cookies_for
    c, a, b, repo = users
    _scan_env(monkeypatch, free_port())
    r = _doc_post(c, a)
    assert r.status_code == 503 and r.json()["error"]["code"] == "scan_unavailable"
    assert c.get(f"{API}/documents", cookies=cookies_for(a)).json()["documents"] == []
    assert _alerts(repo).get("scanner_unavailable") == "active"
    with FakeClamd() as srv:                                                         # the scanner comes back: the next upload works and resolves the alert
        _scan_env(monkeypatch, srv.port)
        assert _doc_post(c, a).status_code == 201
    assert _alerts(repo).get("scanner_unavailable") == "resolved"


def test_candidate_upload_scanner_timeout_and_error_are_503(users, monkeypatch):
    c, a, b, repo = users
    with FakeClamd("timeout") as srv:
        _scan_env(monkeypatch, srv.port, CLAMAV_SCAN_TIMEOUT_SECONDS="0.4")
        assert _doc_post(c, a).status_code == 503
    with FakeClamd("error") as srv:
        _scan_env(monkeypatch, srv.port)
        assert _doc_post(c, a).status_code == 503
    with FakeClamd("malformed") as srv:
        _scan_env(monkeypatch, srv.port)
        assert _doc_post(c, a).status_code == 503


def test_candidate_upload_over_scan_limit_is_413_and_replace_is_scanned_too(users, monkeypatch):
    from tests._auth_factories import cookies_for
    c, a, b, repo = users
    with FakeClamd() as srv:
        _scan_env(monkeypatch, srv.port)
        did = _doc_post(c, a).json()["id"]
        r = c.post(f"{API}/documents/{did}/replace", files={"file": ("cv2.txt", b"new " + eicar_bytes(), "text/plain")}, cookies=cookies_for(a))
        assert r.status_code == 422                                                  # replace goes through the same scan
        monkeypatch.setenv("CLAMAV_MAX_STREAM_BYTES", "50")
        big = _doc_post(c, a, data=b"y" * 200)
        assert big.status_code == 413 and big.json()["error"]["code"] == "scan_too_large"


def test_candidate_upload_hosted_with_fake_provider_is_refused(users, monkeypatch):
    c, a, b, repo = users
    monkeypatch.setenv("API_ENV", "staging")
    monkeypatch.setenv("FILE_SCAN_PROVIDER", "fake")
    assert _doc_post(c, a).status_code == 503


# ------------------------------------------------------------------ governed knowledge through the real routes
class Gov:
    def __init__(self, env, tmp_path):
        self.env = env
        self.sf = env.repo.session_factory
        from src.documents.storage import LocalDocumentStore
        self.store = InMemoryVectorStore(LocalHashEmbedder())
        self.runtime = KnowledgeRuntime(session_factory=self.sf, doc_store=LocalDocumentStore(str(tmp_path / "kb_uploads")),
                                        scanner=fs.build_file_scanner(), vector_store_factory=lambda: self.store)
        self.worker = Worker(JobService(self.sf), services=SimpleNamespace(knowledge=self.runtime))
        _, self.kb = env.user("knowledge_admin")

    def upload(self, data=DOC.encode(), name="framework.txt"):
        r = self.env.c.post(f"{API}/admin/knowledge/sources", cookies=self.kb, data={"title": "Framework", **{k: str(v) for k, v in {**META, "authority_level": 2}.items()}},
                            files={"file": (name, data, "text/plain")})
        assert r.status_code == 201, r.text
        return r.json()["version_public_id"]

    def drain(self):
        for _ in range(20):
            if self.worker.run_once() == "idle":
                break

    def detail(self, v):
        r = self.env.c.get(f"{API}/admin/knowledge/versions/{v}", cookies=self.kb)
        return r.json()


@pytest.fixture()
def gov(tmp_path, monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_STORAGE_DIR", str(tmp_path / "kb_uploads"))
    e = Env()
    yield lambda: Gov(e, tmp_path)
    e.close()


def test_governed_clean_passes_with_a_real_scan_record(gov, monkeypatch):
    with FakeClamd() as srv:
        _scan_env(monkeypatch, srv.port)
        g = gov()
        v = g.upload()
        g.drain()
        d = g.detail(v)
        assert d["state"] == "review_required" and d["scan_status"] == "scan_passed" and srv.received
        with g.sf() as s:
            assert s.scalar(select(V.scanner_name).where(V.public_id == v)) == "clamav"
        ap = g.env.c.post(f"{API}/admin/knowledge/versions/{v}/approve", cookies=g.env.user("platform_admin")[1])
        assert ap.status_code == 200 and ap.json()["state"] == "approved"            # the real scan record satisfies the approval gate


def test_governed_infected_is_held_never_parsed_indexed_or_served(gov, monkeypatch):
    with FakeClamd() as srv:
        _scan_env(monkeypatch, srv.port)
        g = gov()
        v = g.upload(data=b"harmless " + eicar_bytes())
        g.drain()
        d = g.detail(v)
        assert d["state"] == "failed" and d["scan_status"] == "scan_failed" and d["failure_category"] == "scan_failed" and d["preview"] is None
        assert g.store.count() == 0
        assert "scanner_unavailable" not in _alerts(g.env.repo)
        ap = g.env.c.post(f"{API}/admin/knowledge/versions/{v}/approve", cookies=g.env.user("platform_admin")[1])
        assert ap.status_code == 409


def test_governed_scanner_outage_is_distinct_from_infection_alerts_and_blocks_approval(gov, monkeypatch):
    _scan_env(monkeypatch, free_port())
    g = gov()
    v = g.upload()
    g.drain()
    d = g.detail(v)
    assert d["state"] == "failed" and d["scan_status"] == "scan_unavailable" and d["failure_category"] == "scan_unavailable" and d["preview"] is None
    assert g.store.count() == 0
    assert _alerts(g.env.repo).get("scanner_unavailable") == "active"
    ap = g.env.c.post(f"{API}/admin/knowledge/versions/{v}/approve", cookies=g.env.user("platform_admin")[1])
    assert ap.status_code == 409
    with FakeClamd() as srv:                                                          # scanner restored: an explicit reprocess scans for real and clears the alert
        _scan_env(monkeypatch, srv.port)
        r = g.env.c.post(f"{API}/admin/knowledge/versions/{v}/reprocess", cookies=g.kb)
        assert r.status_code in (200, 202), r.text
        g.runtime.scanner = fs.build_file_scanner()
        g.drain()
        assert g.detail(v)["scan_status"] == "scan_passed"
    assert _alerts(g.env.repo).get("scanner_unavailable") == "resolved"


def test_governed_timeout_and_over_limit_hold_the_file(gov, monkeypatch):
    with FakeClamd("timeout") as srv:
        _scan_env(monkeypatch, srv.port, CLAMAV_SCAN_TIMEOUT_SECONDS="0.4")
        g = gov()
        v = g.upload()
        g.drain()
        assert g.detail(v)["scan_status"] == "scan_unavailable"
    with FakeClamd() as srv:
        _scan_env(monkeypatch, srv.port, CLAMAV_MAX_STREAM_BYTES="20")
        g.runtime.scanner = fs.build_file_scanner()
        v2 = g.upload(data=b"z" * 400, name="two.txt")
        g.drain()
        assert g.detail(v2)["scan_status"] == "scan_failed" and g.store.count() == 0


# ------------------------------------------------------------------ approval gate and hosted fake-scanner records (K9 residual)
def _v(**kw):
    base = dict(scan_status="scan_passed", scanner_name="clamav", publisher="P", provenance_note="n", licence_class="public_official", language="en",
                authority_level=2, extracted_chars=100, state="review_required")
    return SimpleNamespace(**{**base, **kw})


def test_blockers_require_a_passed_real_scan(monkeypatch):
    monkeypatch.delenv("API_ENV", raising=False)
    assert not any("malware" in b for b in KnowledgeAdminService.blockers(_v()))
    for st in ("not_scanned", "scan_failed", "scan_unavailable"):
        assert any("malware" in b for b in KnowledgeAdminService.blockers(_v(scan_status=st)))
    assert any("real scanner" in b for b in KnowledgeAdminService.blockers(_v(scanner_name="null")))


def test_hosted_blockers_reject_fake_and_unrecorded_scanner_records(monkeypatch):
    monkeypatch.setenv("API_ENV", "production")
    for name in ("fake", "null", None, ""):
        assert any("real scanner" in b or "malware" in b for b in KnowledgeAdminService.blockers(_v(scanner_name=name)))
    assert not any("malware" in b or "real scanner" in b for b in KnowledgeAdminService.blockers(_v(scanner_name="clamav")))
    monkeypatch.setenv("API_ENV", "development")
    assert not any("real scanner" in b for b in KnowledgeAdminService.blockers(_v(scanner_name="fake")))


def test_hosted_registry_with_fake_scanner_records_is_detected_and_reported(tmp_path, monkeypatch):
    from src.knowledge_admin.environment import count_untrusted_scan_records
    from tests._knowledge_env_02a import DOC as D, META as M, Process
    p = Process(tmp_path / "dev", environment="development")
    svc = KnowledgeAdminService(p.sf, doc_store=p.docs, jobs=p.jobs, clock=p.clock)
    assert count_untrusted_scan_records(p.sf) == 0
    svc.create_source(title="T", filename="a.txt", data=D.encode(), actor_user_id=None, **M)
    for _ in range(10):
        if p.worker.run_once() == "idle":
            break
    with p.sf() as s:
        assert s.scalar(select(V.scanner_name)) == "fake"
    assert count_untrusted_scan_records(p.sf) == 1                      # the fake scanner's record is counted (it is only trusted in development)


def test_ready_reports_untrusted_scan_records_only_when_present(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from src.api.main import create_app
    from src.application import hosted_readiness as hr
    from src.documents.storage import LocalDocumentStore
    from tests._knowledge_env_02a import DOC as D, META as M
    monkeypatch.setattr(hr, "is_hosted", lambda env=None: True)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ready.db'}")          # own database: never pollute the shared test database
    monkeypatch.setenv("COPILOT_DATA_DIR", str(tmp_path / "kb"))
    with TestClient(create_app()) as c:
        assert "scan_records" not in c.get("/api/v1/ready").json()["dependencies"]
        repo = c.app.state.resources["repository"]
        store = LocalDocumentStore(str(tmp_path / "kbu"))
        svc = KnowledgeAdminService(repo.session_factory, doc_store=store, jobs=JobService(repo.session_factory))
        svc.create_source(title="T", filename="a.txt", data=D.encode(), actor_user_id=None, **M)
        rt = KnowledgeRuntime(session_factory=repo.session_factory, doc_store=store, scanner=FakeScanner(),
                              vector_store_factory=lambda: InMemoryVectorStore(LocalHashEmbedder()))
        w = Worker(JobService(repo.session_factory), services=SimpleNamespace(knowledge=rt))
        for _ in range(10):
            if w.run_once() == "idle":
                break
        assert c.get("/api/v1/ready").json()["dependencies"]["scan_records"] == "untrusted"


def test_fake_scanner_is_still_rejected_by_the_hosted_config_guard(monkeypatch):
    from src.api.env_validation import validate_runtime_config
    monkeypatch.setenv("FILE_SCAN_PROVIDER", "fake")
    rep = validate_runtime_config("production")
    assert any("FILE_SCAN_PROVIDER=fake" in c for c in rep.critical)


# ------------------------------------------------------------------ readiness
def test_ready_reports_scanner_outage_and_signature_freshness(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from src.api.main import create_app
    from src.application import hosted_readiness as hr
    stale = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%a %b %d %H:%M:%S %Y")
    monkeypatch.setattr(hr, "is_hosted", lambda env=None: True)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ready.db'}")          # own database: never pollute the shared test database
    monkeypatch.setenv("COPILOT_DATA_DIR", str(tmp_path / "kb"))
    with TestClient(create_app()) as c:
        _scan_env(monkeypatch, free_port())
        r = c.get("/api/v1/ready")
        assert r.status_code == 200
        assert r.json()["dependencies"]["scanner"] == "unreachable" and "scanner_signatures" not in r.json()["dependencies"]
        repo = c.app.state.resources["repository"]
        assert _alerts(repo).get("scanner_unavailable") == "active"
        with FakeClamd(version=f"ClamAV 1.0.1/27000/{stale}") as srv:
            _scan_env(monkeypatch, srv.port)
            dep = c.get("/api/v1/ready").json()["dependencies"]
            assert dep["scanner"] == "reachable" and dep["scanner_signatures"] == "stale"
        a = _alerts(repo)
        assert a.get("scanner_unavailable") == "resolved" and a.get("scanner_signatures_stale") == "active"


def test_alert_helper_is_idempotent_and_never_raises(tmp_path):
    from src.persistence import init_db, make_engine, make_session_factory
    eng = make_engine(f"sqlite:///{tmp_path / 'a.db'}")
    init_db(eng)
    sf = make_session_factory(eng)
    KA.observe_scanner(sf, available=False)
    KA.observe_scanner(sf, available=False)
    with sf() as s:
        rows = s.scalars(select(AdminNotification)).all()
        assert len(rows) == 1 and rows[0].category == "job_failed" and rows[0].source_id == "malware_scanner"
    KA.observe_scanner(sf, available=True)
    KA.observe_scanner(lambda: (_ for _ in ()).throw(RuntimeError("db down")), available=False)     # must not raise
