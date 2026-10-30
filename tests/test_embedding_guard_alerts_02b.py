"""02B: guard findings, serving refusal, the incompatible-embedding alert producer (raise / dedupe / resolve), job refusal and the operator rebuild
path. Offline: real Chroma on a temp directory, offline stand-in embedders, no provider call."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy import select

from src.copilot import index_manifest as IM
from src.copilot.embeddings import LocalHashEmbedder
from src.copilot.index_manifest import IndexIncompatibleError
from src.copilot.vectorstore import ChromaStore
from src.knowledge_admin import alerts as KA
from src.knowledge_admin import policy as P
from src.knowledge_admin.embedding_rebuild import plan_rebuild, rebuild_into_new_index
from src.knowledge_admin.environment import KnowledgeServingRefused
from src.persistence import AdminNotification, KnowledgeSourceVersion as V
from tests._knowledge_env_02a import DOC2, Process, hosted_temp
from tests.test_index_manifest_02b import Fake

APPROVAL = {"ASK4MO_ALLOW_PAID_EMBEDDINGS": "1", "ASK4MO_EMBEDDING_BUDGET_MARKER": "OD-BUDGET:test-fixture-only", "ASK4MO_EMBEDDING_MAX_CALLS": "50"}


def alert_states(p: Process) -> dict:
    with p.sf() as s:
        return {r.category: (r.state, r.occurrence_count) for r in s.scalars(select(AdminNotification)).all()}


def swap(p: Process, embedder) -> ChromaStore:
    """Another process/config opens the SAME persistent index with a different embedder."""
    other = ChromaStore(embedder, persist_dir=str(p.root / "chroma"), collection_name=P.COLLECTION)
    p.store = other
    p.retriever.store = other
    return other


def codes(report) -> list[str]:
    return [f.code for f in report.blocking]


# ------------------------------------------------------------------ guard: hosted
def test_hosted_healthy_index_is_checked_and_compatible(tmp_path, monkeypatch):
    hosted_temp(monkeypatch)
    p = Process(tmp_path / "env", environment="staging", alerts=True)
    try:
        p.worker.run_once()
        p.to_active()
        r = p.guard.check(fresh=True)
        assert r.serving_allowed and r.embedding_checked and r.embedding_fields == ()
        assert not [f for f in r.findings if f.code in ("embedder_not_approved", "index_embedder_mismatch", "index_manifest_unproven")]
        assert KA.EMBEDDING_MISMATCH not in alert_states(p)
        assert p.evidence()                                                                      # and governed retrieval serves
    finally:
        p.close()


@pytest.mark.parametrize("variant,field", [(dict(model="other-model"), "model"), (dict(version="test-2"), "version"),
                                           (dict(dimensions=256), "dimensions"), (dict(provider="cohere"), "provider")])
def test_hosted_incompatible_embedder_blocks_serving_names_the_field_and_alert_lifecycle_runs(tmp_path, monkeypatch, variant, field):
    hosted_temp(monkeypatch)
    p = Process(tmp_path / "env", environment="staging", alerts=True)
    try:
        p.worker.run_once()
        p.to_active()
        good = p.store
        swap(p, Fake(**variant))
        r = p.guard.check(fresh=True)
        mm = [f for f in r.findings if f.code == "index_embedder_mismatch"]
        assert mm and mm[0].fields == (field,) and not r.serving_allowed
        assert r.embedding_fields == (field,)
        with pytest.raises(KnowledgeServingRefused) as e:
            p.retriever.retrieve("roadmap customer evidence")                                   # refused, never an empty list
        assert "index_embedder_mismatch" in e.value.codes
        # alert: raised once, deduplicated across repeated evaluations, one row with the stable dedupe key
        p.guard.check(fresh=True)
        p.guard.check(fresh=True)
        assert alert_states(p)[KA.EMBEDDING_MISMATCH] == ("active", 1)
        with p.sf() as s:
            rows = s.scalars(select(AdminNotification).where(AdminNotification.category == KA.EMBEDDING_MISMATCH)).all()
        assert len(rows) == 1 and rows[0].dedupe_key == KA.EMBEDDING_MISMATCH and rows[0].source_type == "knowledge"
        blob = " ".join(str(v) for v in (rows[0].title, rows[0].source_id, rows[0].dedupe_key))
        assert "other-model" not in blob and str(tmp_path) not in blob
        # the compatible embedder returns: the alert auto-resolves and the same row reopens on recurrence
        p.store = p.retriever.store = good
        assert p.guard.check(fresh=True).serving_allowed
        assert alert_states(p)[KA.EMBEDDING_MISMATCH][0] == "resolved"
        swap(p, Fake(**variant))
        p.guard.check(fresh=True)
        assert alert_states(p)[KA.EMBEDDING_MISMATCH][0] == "active"
    finally:
        p.close()


def test_hosted_hash_embedder_blocks_serving(tmp_path, monkeypatch):
    hosted_temp(monkeypatch)
    p = Process(tmp_path / "env", environment="staging", embedding="local", alerts=True)
    try:
        p.worker.run_once()
        r = p.guard.check(fresh=True)                                                            # config says local, the store runs the hash embedder
        f = [x for x in r.findings if x.code == "embedder_not_approved"]
        assert f and "provider" in f[0].fields and not r.serving_allowed
        assert alert_states(p)[KA.EMBEDDING_MISMATCH][0] == "active"
        with pytest.raises(KnowledgeServingRefused):
            p.retriever.retrieve("anything")
    finally:
        p.close()


def test_hosted_missing_manifest_is_unproven_and_blocks(tmp_path, monkeypatch):
    hosted_temp(monkeypatch)
    p = Process(tmp_path / "env", environment="staging")
    try:
        p.worker.run_once()
        p.to_active()
        IM.manifest_file(p.root / "chroma", P.COLLECTION).unlink()
        r = p.guard.check(fresh=True)
        f = [x for x in r.findings if x.code == "index_manifest_unproven"]
        assert f and f[0].fields == ("manifest",) and not r.serving_allowed
    finally:
        p.close()


def _assert_safe_embedding_mismatch_report(report, *, private_path: str) -> None:
    """Validate every field before exempting only the operational timestamp from the dimension check."""
    assert isinstance(report, dict)
    assert set(report) == {"environment", "enforced", "mode", "serving_allowed", "checked_at", "findings", "embedding_check"}
    assert report["environment"] == "staging"
    assert report["enforced"] is True and report["mode"] == "enforced"
    assert report["serving_allowed"] is False
    timestamp = report["checked_at"]
    assert isinstance(timestamp, str)
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise AssertionError("invalid checked_at timestamp") from exc
    assert parsed.tzinfo is not None and parsed.utcoffset() is not None
    findings = report["findings"]
    assert isinstance(findings, list)
    for finding in findings:
        assert isinstance(finding, dict) and set(finding) == {"code", "severity", "message", "fields"}
        assert all(isinstance(finding[key], str) for key in ("code", "severity", "message"))
        assert isinstance(finding["fields"], list) and all(isinstance(field, str) for field in finding["fields"])
    mismatch = [finding for finding in findings if finding["code"] == "index_embedder_mismatch"]
    assert len(mismatch) == 1
    assert mismatch[0]["severity"] == "block" and set(mismatch[0]["fields"]) == {"model", "dimensions"}
    embedding = report["embedding_check"]
    assert isinstance(embedding, dict) and set(embedding) == {"checked", "differing_fields"}
    assert embedding["checked"] is True
    assert isinstance(embedding["differing_fields"], list)
    assert set(embedding["differing_fields"]) == {"model", "dimensions"}
    full = json.dumps(report)
    for leaked in ("leaky-model-name", "fake-semantic-test", private_path, "test-key-not-real", "postgresql"):
        assert leaked not in full, leaked
    without_timestamp = {key: value for key, value in report.items() if key != "checked_at"}
    assert "256" not in json.dumps(without_timestamp)


def test_guard_report_names_fields_without_leaking_configuration(tmp_path, monkeypatch):
    hosted_temp(monkeypatch)
    p = Process(tmp_path / "env", environment="staging")
    try:
        p.worker.run_once()
        p.to_active()
        swap(p, Fake(model="leaky-model-name", dimensions=256))
        report = p.guard.check(fresh=True)
        assert not report.serving_allowed
        _assert_safe_embedding_mismatch_report(report.to_dict(), private_path=str(tmp_path))
    finally:
        p.close()


@pytest.fixture
def safe_mismatch_report():
    from src.knowledge_admin.environment import Finding, GuardReport, MESSAGES

    return GuardReport(environment="staging", enforced=True, checked_at="2026-10-30T17:29:38.256320+00:00",
                       findings=(Finding("index_embedder_mismatch", "block", MESSAGES["index_embedder_mismatch"],
                                         ("model", "dimensions")),),
                       embedding_checked=True, embedding_fields=("model", "dimensions")).to_dict()


def test_guard_report_accepts_valid_timestamp_with_dimension_digits(safe_mismatch_report):
    assert "256" in safe_mismatch_report["checked_at"]
    _assert_safe_embedding_mismatch_report(safe_mismatch_report, private_path="/synthetic-private-path")


@pytest.mark.parametrize("mutation", ["number_field", "string_field", "nested_field", "nested_embedding_field", "model", "version",
                                      "path", "key", "database", "dimension_message", "invalid_timestamp", "naive_timestamp",
                                      "missing_finding", "wrong_severity", "missing_field", "serving_allowed"])
def test_guard_report_assertion_rejects_leaks_and_invalid_state(safe_mismatch_report, mutation):
    report = safe_mismatch_report
    finding = report["findings"][0]
    values = {"model": "leaky-model-name", "version": "fake-semantic-test", "path": "/synthetic-private-path",
              "key": "test-key-not-real", "database": "postgresql", "dimension_message": "256"}
    if mutation == "number_field":
        report["dimension"] = 256
    elif mutation == "string_field":
        report["dimension"] = "256"
    elif mutation == "nested_field":
        finding["extra"] = {"secret": "leaky-model-name"}
    elif mutation == "nested_embedding_field":
        report["embedding_check"]["extra"] = {"dimension": 256}
    elif mutation in values:
        finding["message"] += " " + values[mutation]
    elif mutation == "invalid_timestamp":
        report["checked_at"] = "not-a-timestamp-256"
    elif mutation == "naive_timestamp":
        report["checked_at"] = "2026-10-30T17:29:38.256320"
    elif mutation == "missing_finding":
        report["findings"] = []
    elif mutation == "wrong_severity":
        finding["severity"] = "warn"
    elif mutation == "missing_field":
        finding["fields"] = ["model"]
    else:
        report["serving_allowed"] = True
    with pytest.raises(AssertionError):
        _assert_safe_embedding_mismatch_report(report, private_path="/synthetic-private-path")


# ------------------------------------------------------------------ guard: development warns, store still refuses a provable mismatch
def test_development_reports_a_mismatch_but_guard_does_not_enforce_and_the_store_still_refuses(tmp_path):
    p = Process(tmp_path / "env", environment="development", embedding="local")
    try:
        p.to_active()
        assert p.guard.check(fresh=True).embedding_fields == ()
        swap(p, Fake(model="other-model"))
        r = p.guard.check(fresh=True)
        assert [f.code for f in r.findings if f.code == "index_embedder_mismatch"] and r.serving_allowed and not r.enforced      # visible, not enforced
        with pytest.raises(IndexIncompatibleError) as e:
            p.retriever.retrieve("roadmap customer evidence")                                   # the store never answers from an incomparable index
        assert set(e.value.fields) == {"provider", "model", "version"}   # built by the hash embedder, now an openai-labelled one (same 512 dimensions)
        assert alert_states(p)[KA.EMBEDDING_MISMATCH][0] == "active"                              # the query-time producer raised the alert
    finally:
        p.close()


def test_development_legacy_index_without_manifest_and_hash_embedder_stay_quiet(tmp_path):
    p = Process(tmp_path / "env", environment="development", embedding="local")
    try:
        p.to_active()
        IM.manifest_file(p.root / "chroma", P.COLLECTION).unlink()
        r = p.guard.check(fresh=True)
        assert not [f for f in r.findings if f.code in ("embedder_not_approved", "index_manifest_unproven", "index_embedder_mismatch")]
        assert p.evidence()                                                                      # still serves, permissive
    finally:
        p.close()


# ------------------------------------------------------------------ alert producer (unit)
def test_alert_producer_raise_dedupe_resolve_and_never_raises(tmp_path):
    p = Process(tmp_path / "env")
    try:
        KA.observe_embedding_incompatibility(p.sf, ["model"])
        KA.observe_embedding_incompatibility(p.sf, ["model", "dimensions"])
        assert alert_states(p)[KA.EMBEDDING_MISMATCH] == ("active", 1)
        KA.observe_embedding_incompatibility(p.sf, [])
        assert alert_states(p)[KA.EMBEDDING_MISMATCH][0] == "resolved"

        class Report:
            environment, findings, embedding_checked, embedding_fields = "staging", (), True, ("provider",)

        assert KA.EMBEDDING_MISMATCH in KA.observe_guard_report(p.sf, Report())
        Report.embedding_fields = ()
        assert KA.observe_guard_report(p.sf, Report()) == []
        assert alert_states(p)[KA.EMBEDDING_MISMATCH][0] == "resolved"
        assert KA.observe_guard_report(lambda: (_ for _ in ()).throw(RuntimeError("db down")), Report()) == []
    finally:
        p.close()


# ------------------------------------------------------------------ jobs refuse to mix embedders
def test_reindex_job_refuses_an_incompatible_index_and_raises_the_alert(tmp_path):
    p = Process(tmp_path / "env", environment="development", embedding="local")
    try:
        r = p.to_active()
        before = p.store.count()
        swap(p, Fake(model="other-model"))
        p.svc.request_reindex(r["version_public_id"], actor_user_id=1)
        p.drain()
        with p.sf() as s:
            from src.persistence import Job
            job = s.scalars(select(Job).where(Job.job_type == P.JOB_REINDEX)).all()[-1]
        assert job.state == "failed"
        assert p.store.count() == before and p.store.index_manifest().model == "local-hash-v1"        # nothing was mixed in, nothing rebuilt
        assert alert_states(p)[KA.EMBEDDING_MISMATCH][0] == "active"
        assert p.state(r["version_public_id"]) == "active"                                         # the version state is untouched
    finally:
        p.close()


def test_index_job_with_an_incompatible_index_fails_the_version_with_a_fixed_category(tmp_path):
    p = Process(tmp_path / "env", environment="development", embedding="local")
    try:
        p.to_active()
        swap(p, Fake(model="other-model"))
        r2 = p.to_review(title="Second", name="second.txt", data=DOC2.encode())
        p.index_version(r2["version_public_id"])
        detail = p.svc.version_detail(r2["version_public_id"])
        assert detail["state"] == "failed" and detail["failure_category"] == "index_incompatible"
        assert alert_states(p)[KA.EMBEDDING_MISMATCH][0] == "active"
    finally:
        p.close()


# ------------------------------------------------------------------ the operator rebuild path (never automatic, never destructive)
def build_incompatible(tmp_path):
    p = Process(tmp_path / "env", environment="development", embedding="local")
    r = p.to_active()
    return p, r


def test_plan_reports_the_incompatibility_and_estimates_calls_without_embedding(tmp_path):
    p, _ = build_incompatible(tmp_path)
    try:
        swap(p, Fake(model="other-model"))
        plan = plan_rebuild(p.sf, p.store, environment="production")
        assert plan["rebuild_needed"] and set(plan["active_index"]["differing_fields"]) == {"provider", "model", "version"}
        assert plan["versions_to_rebuild"] == 1 and plan["estimate"]["embedding_calls"] >= 1 and "cost_class" in plan["estimate"]
        assert str(tmp_path) not in json.dumps(plan)
    finally:
        p.close()


def test_rebuild_dry_run_writes_nothing_and_apply_requires_every_precondition(tmp_path):
    p, _ = build_incompatible(tmp_path)
    try:
        target = tmp_path / "rebuilt"
        new_emb = Fake(model="approved-model")
        dry = rebuild_into_new_index(p.sf, p.docs, target_dir=target, embedder=new_emb, confirm_embedder="openai:approved-model", execute=False, env=APPROVAL)
        assert dry.ok and not dry.executed and not target.exists()
        no_confirm = rebuild_into_new_index(p.sf, p.docs, target_dir=target, embedder=new_emb, execute=True, env=APPROVAL)
        assert not no_confirm.ok and "embedder_not_confirmed" in no_confirm.codes and not target.exists()
        wrong = rebuild_into_new_index(p.sf, p.docs, target_dir=target, embedder=new_emb, confirm_embedder="openai:other", execute=True, env=APPROVAL)
        assert "embedder_not_confirmed" in wrong.codes
        no_budget = rebuild_into_new_index(p.sf, p.docs, target_dir=target, embedder=new_emb, confirm_embedder="openai:approved-model", execute=True, env={})
        assert not no_budget.ok and {"paid_flag_missing", "budget_marker_missing", "max_calls_missing"} <= set(no_budget.codes) and not target.exists()
        active = rebuild_into_new_index(p.sf, p.docs, target_dir=p.root / "chroma", embedder=new_emb, active_index_dir=p.root / "chroma",
                                        confirm_embedder="openai:approved-model", execute=True, env=APPROVAL)
        assert "target_is_active_index" in active.codes and "target_not_empty" in active.codes
        (tmp_path / "full").mkdir()
        (tmp_path / "full" / "x").write_text("x")
        assert "target_not_empty" in rebuild_into_new_index(p.sf, p.docs, target_dir=tmp_path / "full", embedder=new_emb, confirm_embedder="openai:approved-model",
                                                            execute=True, env=APPROVAL).codes
        hosted_hash = rebuild_into_new_index(p.sf, p.docs, target_dir=target, embedder=LocalHashEmbedder(), environment="production", execute=True)
        assert "hash_embedder_not_allowed" in hosted_hash.codes and not target.exists()
    finally:
        p.close()


def test_rebuild_builds_a_new_verified_index_with_the_existing_reindex_handler_and_leaves_the_old_one_alone(tmp_path):
    p, r = build_incompatible(tmp_path)
    try:
        old_count, old_manifest = p.store.count(), p.store.index_manifest()
        target = tmp_path / "rebuilt"
        rep = rebuild_into_new_index(p.sf, p.docs, target_dir=target, embedder=Fake(model="approved-model"), active_index_dir=p.root / "chroma",
                                     confirm_embedder="openai:approved-model", execute=True, env=APPROVAL)
        assert rep.ok and rep.executed and rep.counts["chunks_built"] == rep.counts["chunks_expected"] == old_count and rep.counts["versions_failed"] == 0
        assert rep.index["state"] == IM.OK and rep.index["manifest"]["model"] == "approved-model"
        assert str(tmp_path) not in json.dumps(rep.to_dict())
        new = ChromaStore(Fake(model="approved-model"), persist_dir=str(target), collection_name=P.COLLECTION)
        assert new.count() == old_count and new.index_status(environment="production").state == IM.OK
        assert p.store.count() == old_count and p.store.index_manifest() == old_manifest        # the active index was not touched
        with pytest.raises(IndexIncompatibleError):
            swap(p, Fake(model="approved-model")).query("roadmap", top_k=1)                    # and it is still incompatible until the operator switches
    finally:
        p.close()


def test_rebuild_is_bounded_by_the_approved_call_ceiling(tmp_path):
    p, r = build_incompatible(tmp_path)
    try:
        p.index_version(p.to_review(title="Second", name="second.txt", data=DOC2.encode())["version_public_id"])
        with p.sf() as s:
            assert len(s.scalars(select(V).where(V.state.in_(("active", "indexed")))).all()) == 2
        rep = rebuild_into_new_index(p.sf, p.docs, target_dir=tmp_path / "rebuilt", embedder=Fake(model="approved-model"),
                                     confirm_embedder="openai:approved-model", execute=True, env={**APPROVAL, "ASK4MO_EMBEDDING_MAX_CALLS": "1"})
        assert not rep.ok and "version_rebuild_failed" in rep.codes and rep.counts["versions_failed"] == 1                 # the ceiling stopped the second version
    finally:
        p.close()


def test_free_local_rebuild_in_development_needs_no_confirmation_or_budget(tmp_path):
    p, _ = build_incompatible(tmp_path)
    try:
        swap(p, Fake(model="other-model"))
        rep = rebuild_into_new_index(p.sf, p.docs, target_dir=tmp_path / "rebuilt", embedder=LocalHashEmbedder(), environment="development", execute=True, env={})
        assert rep.ok and rep.counts["chunks_built"] == rep.counts["chunks_expected"] and rep.index["manifest"]["degraded"] is True    # labelled degraded
    finally:
        p.close()
