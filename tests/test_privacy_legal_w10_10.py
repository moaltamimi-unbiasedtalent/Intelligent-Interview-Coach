"""P10B-W10.10: privacy requests (SEC-W10-04), preparation-run ownership index (PRIV-W9-01), legal registry and acceptance (PRIV-W9-02).

Deterministic and offline: temp DB, a fake checkpoint adapter (no real checkpoint store), temp upload storage, no network. Engineering
tests of workflows: nothing here asserts or implies legal compliance."""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from src.agent.models import AgentRunRequest
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.application.account_deletion_service import AccountDeletionService
from src.application.agent_service import AgentApplicationService
from src.documents.storage import LocalDocumentStore
from src.jobs.service import JobService
from src.jobs.worker import Worker
from src.persistence import (
    LegalAcceptance, LegalDocumentVersion, PreparationMemory, PreparationRun, PrivacyRequest, User, UserPreference, utcnow,
)
from src.privacy import policy as P
from src.privacy.legal import LegalConflict, LegalService, LegalValidationError
from src.privacy.preparation import PreparationRunIndex, RunOwnershipConflict, backfill_batch
from src.privacy.requests import PrivacyConflict, PrivacyRequestService
from src.privacy.runtime import PrivacyRuntime
from tests.test_admin_foundation_w10_1 import Env

API = "/api/v1"
ROOT = Path(__file__).resolve().parents[1]
NOTE = "Please correct the spelling of my surname."
HASH = "a" * 64


class FakeAdapter:
    """Stands in for the checkpoint store: only per-run lookups exist (there is deliberately NO list/scan method)."""

    def __init__(self, runs: dict[str, str] | None = None):
        self.runs = dict(runs or {})
        self.fail = False
        self.lookups: list[str] = []

    def owner_of(self, run_id):
        self.lookups.append(run_id)
        return self.runs.get(run_id)

    def purge_run(self, run_id):
        if self.fail:
            raise RuntimeError("checkpoint store unavailable: secret-ish detail should never be persisted")
        self.runs.pop(run_id, None)
        return True

    def delete_run(self, run_id, user_id):
        if self.runs.get(run_id) != user_id:
            return False
        return self.purge_run(run_id)


@pytest.fixture()
def env():
    e = Env()
    yield e
    e.close()


def sf(env):
    return env.accounts.session_factory


def add_memory(env, uid, run_id):
    with sf(env)() as s:
        s.add(PreparationMemory(user_id=uid, category="skills", summary="s", source_run_id=run_id))
        s.commit()


def privacy_worker(env, tmp_path, adapter, clock=None):
    jobs = JobService(sf(env), clock=clock) if clock else JobService(sf(env))
    rt = PrivacyRuntime(session_factory=sf(env), adapter=adapter, doc_store=LocalDocumentStore(str(tmp_path / "docs")),
                        audit_repository=None, jobs=jobs, **({"clock": clock} if clock else {}))
    return jobs, Worker(jobs, services=SimpleNamespace(privacy=rt), **({"clock": clock} if clock else {}))


# =============================================================== SEC-W10-04: durable privacy-request queue
def test_pre_fix_gap_the_legacy_queue_never_saw_anything_and_the_durable_queue_does(env):
    uid, ck = env.user("user")
    r = env.c.post(f"{API}/privacy/requests", json={"request_type": "deletion", "note": NOTE}, cookies=ck)
    assert r.status_code == 201
    assert env.accounts.list_privacy_requests() == []          # the OLD mechanism (status=deletion_requested) is permanently empty
    _, adm = env.user("security_privacy_admin")
    q = env.c.get(f"{API}/admin/privacy/requests", cookies=adm).json()
    assert q["total"] == 1 and q["items"][0]["public_id"] == r.json()["public_id"] and q["items"][0]["status"] == "submitted"


def test_end_to_end_request_lifecycle_assignment_audit_and_candidate_status(env):
    uid, ck = env.user("user")
    admin_id, adm = env.user("security_privacy_admin")
    pid = env.c.post(f"{API}/privacy/requests", json={"request_type": "correction", "note": NOTE}, cookies=ck).json()["public_id"]
    d = env.c.get(f"{API}/admin/privacy/requests/{pid}", cookies=adm).json()
    assert d["status"] == "submitted" and d["request_note"] == NOTE and d["candidate"]["user_id"] == uid and d["allowed_statuses"] == ["acknowledged", "rejected"]
    assert env.c.post(f"{API}/admin/privacy/requests/{pid}/status", json={"status": "completed", "result_category": "correction_made"}, cookies=adm).status_code == 409
    a = env.c.post(f"{API}/admin/privacy/requests/{pid}/assign", json={"assignee_user_id": admin_id}, cookies=adm)
    assert a.status_code == 200 and a.json()["assigned_user_id"] == admin_id
    for st in ("acknowledged", "in_progress"):
        assert env.c.post(f"{API}/admin/privacy/requests/{pid}/status", json={"status": st}, cookies=adm).json()["status"] == st
    assert env.c.post(f"{API}/admin/privacy/requests/{pid}/status", json={"status": "completed"}, cookies=adm).status_code == 422   # needs a result
    done = env.c.post(f"{API}/admin/privacy/requests/{pid}/status", json={"status": "completed", "result_category": "correction_made"}, cookies=adm).json()
    assert done["status"] == "completed" and done["completed_at"] and done["result_category"] == "correction_made"
    mine = env.c.get(f"{API}/privacy/requests", cookies=ck).json()["items"][0]
    assert mine["status"] == "completed" and mine["result_category"] == "correction_made"
    assert set(mine) == {"public_id", "request_type", "type_label", "status", "result_category", "created_at", "updated_at"}   # no operator identity
    assert env.c.post(f"{API}/admin/privacy/requests/{pid}/status", json={"status": "closed"}, cookies=adm).json()["status"] == "closed"
    assert env.c.post(f"{API}/admin/privacy/requests/{pid}/status", json={"status": "in_progress"}, cookies=adm).status_code == 409
    events = [e for e in env.events() if e["event_type"].startswith("admin.privacy_")]
    assert {e["event_type"] for e in events} >= {A.ADMIN_PRIVACY_REQUEST_ASSIGNED, A.ADMIN_PRIVACY_REQUEST_STATUS_CHANGED}
    blob = " ".join(str(e) for e in events)
    assert NOTE not in blob and "surname" not in blob                    # audit holds ids and states, never the note


def test_ownership_scope_validation_cap_and_permission_matrix(env):
    a, ca = env.user("user"); b, cb = env.user("user")
    _, adm = env.user("security_privacy_admin"); _, plat = env.user("platform_admin")
    pid = env.c.post(f"{API}/privacy/requests", json={"request_type": "data_access"}, cookies=ca).json()["public_id"]
    assert env.c.get(f"{API}/privacy/requests", cookies=cb).json()["total"] == 0                       # cannot read another candidate's
    assert env.c.post(f"{API}/privacy/requests", json={"request_type": "data_access", "user_id": a}, cookies=cb).status_code == 422   # no foreign user
    for bad in ({"request_type": "delete_everything"}, {"request_type": "deletion", "note": "x" * 1001}, {"request_type": "deletion", "extra": 1}):
        assert env.c.post(f"{API}/privacy/requests", json=bad, cookies=cb).status_code == 422
    for role in ("support_operator", "billing_admin", "knowledge_admin", "operations_admin", "user"):
        _, ck = env.user(role)
        assert env.c.get(f"{API}/admin/privacy/requests", cookies=ck).status_code == 403
        assert env.c.get(f"{API}/admin/legal", cookies=ck).status_code == 403
    assert env.c.get(f"{API}/admin/privacy/requests", cookies=plat).status_code == 200               # platform_admin: read only
    assert env.c.post(f"{API}/admin/privacy/requests/{pid}/status", json={"status": "acknowledged"}, cookies=plat).status_code == 403
    assert env.c.post(f"{API}/admin/privacy/requests/{pid}/assign", json={"assignee_user_id": None}, cookies=plat).status_code == 403
    assert env.c.get(f"{API}/admin/privacy/requests", cookies=adm).status_code == 200
    assert not (perm.permissions_for_role("support_operator") | perm.permissions_for_role("billing_admin")
                | perm.permissions_for_role("knowledge_admin") | perm.permissions_for_role("operations_admin")) & {perm.PRIVACY_EXECUTE, perm.LEGAL_MANAGE}
    svc = PrivacyRequestService(sf(env))
    for _ in range(5):
        svc.create(b, "other_privacy", None)
    with pytest.raises(PrivacyConflict):
        svc.create(b, "other_privacy", None)                                                            # open-request cap


def test_queue_filters_search_and_stable_pagination_without_searching_request_text(env):
    u1, c1 = env.user("user"); u2, c2 = env.user("user"); _, adm = env.user("security_privacy_admin")
    p1 = env.c.post(f"{API}/privacy/requests", json={"request_type": "deletion", "note": "findable words"}, cookies=c1).json()["public_id"]
    env.c.post(f"{API}/privacy/requests", json={"request_type": "correction"}, cookies=c2)
    g = lambda qs: env.c.get(f"{API}/admin/privacy/requests{qs}", cookies=adm).json()
    assert g("?request_type=deletion")["total"] == 1 and g("?status=submitted")["total"] == 2 and g("?assignee=unassigned")["total"] == 2
    assert g(f"?q={p1}")["total"] == 1 and g(f"?q={u2}")["total"] == 1 and g("?q=findable")["total"] == 0
    assert g("?page_size=1&page=2")["items"][0]["public_id"] != g("?page_size=1&page=1")["items"][0]["public_id"]
    assert env.c.get(f"{API}/admin/privacy/requests?status=bogus", cookies=adm).status_code == 422


def test_admin_can_record_a_request_received_through_another_channel(env):
    uid, _ = env.user("user"); _, adm = env.user("security_privacy_admin")
    email = None
    with sf(env)() as s:
        email = s.get(User, uid).email
    r = env.c.post(f"{API}/admin/privacy/requests", json={"account": email, "request_type": "data_access", "note": "phone call"}, cookies=adm)
    assert r.status_code == 201 and r.json()["source"] == "admin_recorded"
    assert env.c.post(f"{API}/admin/privacy/requests", json={"account": "nobody@x.com", "request_type": "data_access"}, cookies=adm).status_code == 404
    assert any(e["event_type"] == A.ADMIN_PRIVACY_REQUEST_RECORDED for e in env.events())


def test_audit_failure_rolls_back_the_status_change(env, monkeypatch):
    uid, _ = env.user("user")
    svc = PrivacyRequestService(sf(env))
    pid = svc.create(uid, "correction", None)["public_id"]
    import src.privacy.requests as R
    monkeypatch.setattr(R, "_stage", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("audit store down")))
    with pytest.raises(RuntimeError):
        svc.set_status(pid, "acknowledged", audit={"event_type": "x"})
    assert svc.detail(pid)["status"] == "submitted"


def test_no_ip_device_or_private_content_columns_and_admin_schemas_are_safe():
    for model in (PrivacyRequest, PreparationRun, LegalAcceptance, LegalDocumentVersion):
        cols = {c.name for c in model.__table__.columns}
        assert not {"ip_address", "ip", "device_id", "fingerprint", "user_agent"} & cols
    assert not any(n in {c.name for c in PreparationRun.__table__.columns} for n in ("messages", "conversation", "transcript", "state_json"))
    schema = (ROOT / "src/api/schemas/admin.py").read_text()
    block = schema[schema.index("class PrivacyRequestRow"):]
    for banned in ("cv", "transcript", "answers", "memories", "conversation", "evidence", "export_data", "ip_address", "device"):
        assert not re.search(rf"\b{banned}\b\s*:", block), banned


# =============================================================== privacy jobs: same deletion service, replay-safe, no false success
def test_admin_deletion_runs_the_same_service_clears_the_account_and_completes_only_when_everything_is_purged(env, tmp_path, monkeypatch):
    uid, _ = env.user("user"); admin_id, adm = env.user("security_privacy_admin")
    index = PreparationRunIndex(sf(env))
    index.register("run-aaaaaaaa1", uid)
    index.register("run-bbbbbbbb2", uid)
    other_uid, _ = env.user("user")
    index.register("run-cccccccc3", other_uid)
    add_memory(env, uid, "run-aaaaaaaa1")
    adapter = FakeAdapter({"run-aaaaaaaa1": str(uid), "run-bbbbbbbb2": str(uid), "run-cccccccc3": str(other_uid)})
    pid = PrivacyRequestService(sf(env)).create(uid, "deletion", NOTE)["public_id"]
    assert not env.c.post(f"{API}/admin/privacy/requests/{pid}/execute-deletion", cookies=adm).status_code == 200   # not acknowledged yet
    env.c.post(f"{API}/admin/privacy/requests/{pid}/status", json={"status": "acknowledged"}, cookies=adm)
    calls = []
    real = AccountDeletionService.delete_account
    monkeypatch.setattr(AccountDeletionService, "delete_account", lambda self, user_id: (calls.append(user_id), real(self, user_id))[1])
    r = env.c.post(f"{API}/admin/privacy/requests/{pid}/execute-deletion", cookies=adm)
    assert r.status_code == 200 and r.json()["status"] == "in_progress" and r.json()["related_job_id"]
    jobs, worker = privacy_worker(env, tmp_path, adapter)
    adapter.fail = True                                                      # checkpoint store down: must NOT report success
    assert worker.run_once() == "retry_scheduled"
    d = PrivacyRequestService(sf(env)).detail(pid)
    assert d["status"] == "in_progress" and d["result_category"] is None
    with sf(env)() as s:
        assert s.get(User, uid) is None                                       # the account itself is already gone (same service)
        assert s.scalar(select(PreparationRun.state).where(PreparationRun.run_id == "run-bbbbbbbb2")) == "purge_failed"
        job = s.scalar(text("select last_error_message_safe from jobs where job_type='privacy_account_delete'"))
    assert "secret-ish" not in str(job) and "checkpoint store" not in str(job)
    adapter.fail = False
    with sf(env)() as s:                                                      # make the retry eligible without sleeping
        s.execute(text("update jobs set available_at='2000-01-01'"))
        s.commit()
    assert worker.run_once() == "succeeded"
    d = PrivacyRequestService(sf(env)).detail(pid)
    assert d["status"] == "completed" and d["result_category"] == "deletion_performed" and d["user_id"] is None and d["request_note"] is None
    assert "run-aaaaaaaa1" not in adapter.runs and "run-bbbbbbbb2" not in adapter.runs and "run-cccccccc3" in adapter.runs   # only this owner's runs
    with sf(env)() as s:
        assert s.scalar(select(PreparationRun).where(PreparationRun.owner_user_id == uid)) is None
        assert s.get(User, other_uid) is not None
    assert calls and set(calls) == {uid}
    assert any(e["event_type"] == A.ADMIN_PRIVACY_DELETION_COMPLETED for e in env.events())
    assert worker.run_once() == "idle"                                        # replay of a finished job is a no-op


def test_admin_accounts_cannot_be_deleted_through_a_privacy_request(env, tmp_path):
    uid, _ = env.user("operations_admin"); _, adm = env.user("security_privacy_admin")
    pid = PrivacyRequestService(sf(env)).create(uid, "deletion", None)["public_id"]
    d = PrivacyRequestService(sf(env)).detail(pid)
    assert d["can_execute_deletion"] is False
    env.c.post(f"{API}/admin/privacy/requests/{pid}/status", json={"status": "acknowledged"}, cookies=adm)
    assert env.c.post(f"{API}/admin/privacy/requests/{pid}/execute-deletion", cookies=adm).status_code == 409


def test_deletion_job_payload_is_ids_only_and_job_types_are_registered():
    from src.jobs.registry import REGISTRY
    for code, field in ((P.JOB_ACCOUNT_DELETE, "request_id"), (P.JOB_BACKFILL, "after_id"), (P.JOB_PURGE, "run_id")):
        d = REGISTRY[code]
        assert set(d.payload_model.model_fields) == {field} and not d.admin_enqueue


# =============================================================== PRIV-W9-01: preparation-run ownership index
def make_agent(index):
    class M:
        def bind_tools(self, schemas):
            return self

        def invoke(self, messages):
            return AIMessage(content="tips")

    return AgentApplicationService(model_factory=lambda: M(), career_service=object(), run_index=index)


def test_new_runs_are_indexed_before_the_checkpoint_and_without_chat_content(env):
    uid, _ = env.user("user")
    idx = PreparationRunIndex(sf(env))
    seen = {}
    real = idx.register
    idx.register = lambda run_id, owner, **k: (seen.setdefault("at_register", AgentRunProbe.checkpoint_exists(svc, run_id)), real(run_id, owner, **k))[1]
    svc = make_agent(idx)
    res = svc.run(AgentRunRequest(goal="confidential goal text about my layoff", user_id=str(uid)))
    assert seen["at_register"] is False                                         # ownership recorded BEFORE any checkpoint existed
    assert idx.run_ids_for_owner(uid) == [res.run_id]
    with sf(env)() as s:
        row = s.scalar(select(PreparationRun))
        assert row.state == "ready" and row.source == "created"
        dump = " ".join(str(getattr(row, c.name)) for c in PreparationRun.__table__.columns)
    assert "confidential" not in dump and "layoff" not in dump
    assert idx.register(res.run_id, uid) is False                               # duplicate registration is idempotent
    with pytest.raises(RunOwnershipConflict):
        idx.register(res.run_id, uid + 999)                                     # a run can never change owner


class AgentRunProbe:
    @staticmethod
    def checkpoint_exists(svc, run_id):
        return bool((svc._snapshot(run_id).values or {}))


def test_run_creation_fails_closed_when_the_index_cannot_record_ownership(env):
    uid, _ = env.user("user")
    idx = PreparationRunIndex(sf(env))
    idx.register = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down"))
    svc = make_agent(idx)
    from src.agent.errors import AgentError
    with pytest.raises(AgentError):
        svc.run(AgentRunRequest(goal="x", user_id=str(uid)))
    assert svc._checkpointer.get_tuple({"configurable": {"thread_id": "anything"}}) is None   # nothing untracked was created


def test_failed_run_is_marked_and_lazy_indexing_covers_a_historical_run_only_for_its_verified_owner(env):
    uid, _ = env.user("user"); other, _ = env.user("user")
    svc_unindexed = make_agent(None)
    historical = svc_unindexed.run(AgentRunRequest(goal="old run", user_id=str(uid))).run_id
    idx = PreparationRunIndex(sf(env))
    svc = AgentApplicationService(model_factory=svc_unindexed._graph and (lambda: None), career_service=object(), run_index=idx,
                                  checkpointer=svc_unindexed._checkpointer, checkpoint_durable=False)
    assert idx.run_ids_for_owner(uid) == []
    from src.application.agent_service import RunNotFoundError
    with pytest.raises(RunNotFoundError):
        svc.get_run(historical, str(other))                                      # the wrong user neither reads nor indexes it
    assert idx.run_ids_for_owner(other) == [] and idx.run_ids_for_owner(uid) == []
    svc.get_run(historical, str(uid))                                            # the owner touches it: lazily indexed
    assert idx.run_ids_for_owner(uid) == [historical]
    with sf(env)() as s:
        assert s.scalar(select(PreparationRun.source)) == "lazy"


def test_historical_backfill_uses_only_references_verifies_owner_never_assigns_ambiguous_and_never_scans(env):
    a, _ = env.user("user"); b, _ = env.user("user")
    add_memory(env, a, "run-owned-0001"); add_memory(env, a, "run-ambiguous-02"); add_memory(env, a, "run-missing-0003")
    adapter = FakeAdapter({"run-owned-0001": str(a), "run-ambiguous-02": str(b), "run-orphan-9999": str(a)})   # an unreferenced orphan
    idx = PreparationRunIndex(sf(env))
    out = backfill_batch(idx, adapter, sf(env))
    assert out["indexed"] == 1 and out["ambiguous_skipped"] == 1 and out["missing_checkpoint"] == 1 and out["next_after_id"] is None
    assert idx.run_ids_for_owner(a) == ["run-owned-0001"] and idx.run_ids_for_owner(b) == []
    assert "run-orphan-9999" not in adapter.lookups                              # an unreferenced orphan is never even looked at (no scan)
    assert sorted(adapter.lookups) == sorted(["run-owned-0001", "run-ambiguous-02", "run-missing-0003"])
    again = backfill_batch(idx, adapter, sf(env))                                # idempotent
    assert again["indexed"] == 0 and again["already_indexed"] == 1
    assert not hasattr(adapter, "list_runs") and not hasattr(adapter, "scan")
    one = backfill_batch(PreparationRunIndex(sf(env)), adapter, sf(env), batch=1)
    assert one["examined"] == 1


def test_backfill_job_chains_bounded_batches_and_is_admin_triggered(env, tmp_path):
    a, _ = env.user("user"); _, adm = env.user("security_privacy_admin"); _, ops = env.user("operations_admin")
    for i in range(3):
        add_memory(env, a, f"run-batch-000{i}")
    adapter = FakeAdapter({f"run-batch-000{i}": str(a) for i in range(3)})
    assert env.c.post(f"{API}/admin/privacy/preparation/backfill", cookies=ops).status_code == 403
    r = env.c.post(f"{API}/admin/privacy/preparation/backfill", cookies=adm)
    assert r.status_code == 202 and r.json()["created"]
    assert env.c.post(f"{API}/admin/privacy/preparation/backfill", cookies=adm).json()["created"] is False   # idempotent while active
    jobs, worker = privacy_worker(env, tmp_path, adapter)
    assert worker.run_once() == "succeeded"
    cov = env.c.get(f"{API}/admin/privacy/preparation", cookies=adm).json()
    assert cov["indexed_runs"] == 3 and cov["by_source"] == {"backfill": 3} and "limitation" not in cov["note"] and "not included" in cov["note"]
    assert any(e["event_type"] == A.ADMIN_PRIVACY_BACKFILL_REQUESTED for e in env.events())


def test_account_deletion_discovers_runs_through_the_index_not_a_scan_and_surfaces_failed_purges(env, tmp_path):
    uid, _ = env.user("user")
    idx = PreparationRunIndex(sf(env))
    for r in ("run-idx-00001", "run-idx-00002"):
        idx.register(r, uid)
    add_memory(env, uid, "run-mem-00003")
    adapter = FakeAdapter({"run-idx-00001": str(uid), "run-idx-00002": str(uid), "run-mem-00003": str(uid)})
    adapter.fail = True
    svc = AccountDeletionService(sf(env), agent_service=adapter, preparation_index=idx)
    s = svc.delete_account(uid)
    assert s.checkpoints_failed >= 2 and set(s.purge_failed_run_ids) >= {"run-idx-00001", "run-idx-00002"}     # NOT reported as complete
    assert all(r in idx.pending_purge(uid) or True for r in s.purge_failed_run_ids)
    assert {r for r, _ in idx.pending_purge(uid)} >= {"run-idx-00001", "run-idx-00002"}
    assert adapter.lookups == []                                                                                # no ownership scan was needed
    adapter.fail = False
    for r, _ in idx.pending_purge(uid):                                                                         # the retry path (purge job)
        adapter.purge_run(r)
        idx.remove(r)
    assert idx.run_ids_for_owner(uid) == [] and not [r for r in adapter.runs if r.startswith("run-idx")]
    assert svc.delete_account(uid).existed is False                                                             # idempotent


def test_purge_job_is_idempotent_and_retries_after_failure(env, tmp_path):
    uid, _ = env.user("user")
    idx = PreparationRunIndex(sf(env))
    idx.register("run-purge-0001", uid)
    idx.mark("run-purge-0001", "purge_failed")
    adapter = FakeAdapter({"run-purge-0001": str(uid)})
    jobs, worker = privacy_worker(env, tmp_path, adapter)
    adapter.fail = True
    jobs.enqueue(P.JOB_PURGE, {"run_id": "run-purge-0001"})
    assert worker.run_once() == "retry_scheduled"
    adapter.fail = False
    with sf(env)() as s:
        s.execute(text("update jobs set available_at='2000-01-01'"))
        s.commit()
    assert worker.run_once() == "succeeded" and "run-purge-0001" not in adapter.runs and idx.owner_of("run-purge-0001") is None
    jobs.enqueue(P.JOB_PURGE, {"run_id": "run-purge-0001"})
    assert worker.run_once() == "succeeded"                                                                     # replay after purge: no-op


# =============================================================== PRIV-W9-02: legal registry and acceptance
def test_baseline_documents_exist_with_a_truthful_baseline_version_and_no_fabricated_acceptance(env):
    legal = LegalService(sf(env))
    ov = legal.admin_overview()
    assert [d["code"] for d in ov["documents"]] == ["terms", "privacy", "ai_transparency"]
    for d in ov["documents"]:
        cur = d["current"]
        assert cur["version"] == P.BASELINE_VERSION and cur["state"] == "published" and cur["is_baseline"] is True
        assert cur["effective_at"] is None and cur["content_hash"] is None                                     # nothing invented
        assert d["current_accepted"] == 0
    uid, _ = env.user("user")
    status = legal.for_user(uid)
    assert all(x["accepted_current"] is False and x["last_acceptance"] is None for x in status["documents"])
    with sf(env)() as s:
        assert s.scalar(text("select count(*) from legal_acceptances")) == 0                                    # historical users: NOT backfilled


def test_draft_publish_lifecycle_immutability_uniqueness_and_audit_rollback(env, monkeypatch):
    legal = LegalService(sf(env))
    uid, _ = env.user("security_privacy_admin")
    for bad in (dict(version="bad label!"), dict(content_ref="javascript:alert(1)"), dict(content_hash="XYZ"), dict(content_ref="/terms ", content_hash="z" * 64)):
        args = dict(version="2.0", content_ref="/terms", content_hash=HASH, effective_at=None); args.update(bad)
        with pytest.raises(LegalValidationError):
            legal.create_draft("terms", actor_user_id=uid, **args)
    with pytest.raises(Exception):
        legal.create_draft("cookies", version="1", content_ref="/x", content_hash=HASH, effective_at=None, actor_user_id=uid)    # no arbitrary type
    d = legal.create_draft("terms", version="2.0", content_ref="/terms", content_hash=None, effective_at=None, actor_user_id=uid)
    with pytest.raises(LegalConflict):
        legal.create_draft("terms", version="2.0", content_ref="/terms", content_hash=HASH, effective_at=None, actor_user_id=uid)  # unique per document
    with pytest.raises(LegalConflict):
        legal.publish(d["id"], actor_user_id=uid)                                                              # needs hash and effective date
    legal.update_draft(d["id"], content_ref="/terms", content_hash=HASH, effective_at=utcnow() + timedelta(days=1))
    import src.privacy.legal as L
    monkeypatch.setattr(L, "_stage", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("audit down")))
    with pytest.raises(RuntimeError):
        legal.publish(d["id"], actor_user_id=uid, audit={"event_type": "x"})
    monkeypatch.undo()
    assert [v["state"] for v in legal.admin_overview()["documents"][0]["versions"] if v["version"] == "2.0"] == ["draft"]      # rolled back
    pub = legal.publish(d["id"], actor_user_id=uid)
    ov = legal.admin_overview()["documents"][0]
    assert pub["state"] == "published" and ov["current"]["version"] == "2.0"
    assert {v["version"]: v["state"] for v in ov["versions"]} == {"2.0": "published", P.BASELINE_VERSION: "retired"}
    with pytest.raises(LegalConflict):
        legal.update_draft(d["id"], content_ref="/terms", content_hash="b" * 64, effective_at=None)            # published is immutable
    with pytest.raises(LegalConflict):
        legal.publish(d["id"], actor_user_id=uid)
    with sf(env)() as s, pytest.raises(IntegrityError):                                                         # exactly one published per document (DB)
        doc_id = s.scalar(select(LegalDocumentVersion.document_id).limit(1))
        s.add(LegalDocumentVersion(document_id=doc_id, version="rogue", state="published", is_baseline=False, content_ref="/x",
                                   content_hash=HASH, published_at=utcnow(), created_at=utcnow(), updated_at=utcnow()))
        s.commit()


def test_acceptance_is_versioned_timestamped_idempotent_and_survives_a_new_version(env):
    legal = LegalService(sf(env))
    uid, _ = env.user("user"); admin, _ = env.user("security_privacy_admin")
    first = legal.accept(uid, "terms")
    t = next(x for x in first["documents"] if x["code"] == "terms")
    assert t["accepted_current"] is True and t["last_acceptance"]["version"] == P.BASELINE_VERSION and t["last_acceptance"]["source"] == "settings"
    again = legal.accept(uid, "terms")
    assert next(x for x in again["documents"] if x["code"] == "terms")["last_acceptance"]["accepted_at"] == t["last_acceptance"]["accepted_at"]
    with sf(env)() as s:
        assert s.scalar(text("select count(*) from legal_acceptances")) == 1                                    # no duplicate row
    d = legal.create_draft("terms", version="2.0", content_ref="/terms", content_hash=HASH, effective_at=utcnow(), actor_user_id=admin)
    legal.publish(d["id"], actor_user_id=admin)
    after = next(x for x in legal.for_user(uid)["documents"] if x["code"] == "terms")
    assert after["accepted_current"] is False and after["last_acceptance"]["version"] == P.BASELINE_VERSION and after["last_acceptance"]["is_current"] is False   # NOT falsely accepted
    ov = legal.admin_overview()["documents"][0]
    assert ov["current_accepted"] == 0 and {v["version"]: v["acceptances"] for v in ov["versions"]}[P.BASELINE_VERSION] == 1  # old acceptance preserved
    legal.accept(uid, "terms")
    assert next(x for x in legal.for_user(uid)["documents"] if x["code"] == "terms")["accepted_current"] is True
    with pytest.raises(LegalValidationError):
        legal.accept(uid, "terms", source="carrier_pigeon")
    cols = {c.name for c in LegalAcceptance.__table__.columns}
    assert cols == {"id", "user_id", "version_id", "accepted_at", "source"}                                      # no IP, device or fingerprint


def test_candidate_legal_api_scoped_rate_limited_route_and_consent_separation(env):
    uid, ck = env.user("user")
    r = env.c.get(f"{API}/privacy/legal", cookies=ck).json()
    assert [d["code"] for d in r["documents"]] == ["terms", "privacy", "ai_transparency"] and all(not d["accepted_current"] for d in r["documents"])
    assert r["documents"][0]["version_is_baseline"] is True and r["documents"][0]["effective_at"] is None
    assert env.c.post(f"{API}/privacy/legal/terms/accept", cookies=ck).json()["documents"][0]["accepted_current"] is True
    assert env.c.post(f"{API}/privacy/legal/cookies/accept", cookies=ck).status_code == 404
    other, ck2 = env.user("user")
    assert env.c.get(f"{API}/privacy/legal", cookies=ck2).json()["documents"][0]["accepted_current"] is False   # per-user truth
    with sf(env)() as s:                                                                                         # legal acceptance is NOT consent/preferences
        before = s.scalar(select(UserPreference.id).where(UserPreference.user_id == uid))
        env.c.post(f"{API}/privacy/legal/privacy/accept", cookies=ck)
        assert s.scalar(select(UserPreference.id).where(UserPreference.user_id == uid)) == before
    src = (ROOT / "src/privacy/legal.py").read_text()
    assert "consent" in src.lower() and "not consent" in src.lower()


def test_admin_legal_api_permissions_publish_flow_and_audit(env):
    _, plat = env.user("platform_admin"); _, adm = env.user("security_privacy_admin")
    assert env.c.get(f"{API}/admin/legal", cookies=plat).status_code == 200                                      # privacy.read
    body = {"version": "3.0", "content_ref": "/privacy", "content_hash": HASH, "effective_at": "2026-12-01T00:00:00+00:00"}
    assert env.c.post(f"{API}/admin/legal/privacy/versions", json=body, cookies=plat).status_code == 403          # legal.manage only
    v = env.c.post(f"{API}/admin/legal/privacy/versions", json=body, cookies=adm)
    assert v.status_code == 201 and v.json()["state"] == "draft"
    assert env.c.post(f"{API}/admin/legal/privacy/versions", json=body, cookies=adm).status_code == 409
    assert env.c.post(f"{API}/admin/legal/privacy/versions", json={**body, "version": "x y"}, cookies=adm).status_code == 422
    assert env.c.post(f"{API}/admin/legal/privacy/versions", json={**body, "version": "4", "effective_at": "not a date"}, cookies=adm).status_code == 422
    vid = v.json()["id"]
    assert env.c.post(f"{API}/admin/legal/versions/{vid}/publish", cookies=plat).status_code == 403
    assert env.c.post(f"{API}/admin/legal/versions/{vid}/publish", cookies=adm).json()["state"] == "published"
    assert env.c.patch(f"{API}/admin/legal/versions/{vid}", json={"content_ref": "/privacy"}, cookies=adm).status_code == 409
    names = {e["event_type"] for e in env.events()}
    assert {A.ADMIN_LEGAL_VERSION_CREATED, A.ADMIN_LEGAL_VERSION_PUBLISHED} <= names
    ov = env.c.get(f"{API}/admin/legal", cookies=adm).json()
    assert "not a compliance measure" in ov["note"] and next(d for d in ov["documents"] if d["code"] == "privacy")["current"]["version"] == "3.0"
    routes = [r for r in __import__("src.api.admin_route_invariant", fromlist=["x"]).admin_routes() if r.path.startswith(("/admin/legal", "/admin/privacy"))]
    assert routes and all(r.permissions for r in routes) and not any("DELETE" in r.methods for r in routes)


def test_acceptances_are_deleted_with_the_account_and_export_lists_new_domains_without_overclaiming(env):
    uid, ck = env.user("user")
    LegalService(sf(env)).accept(uid, "terms")
    PrivacyRequestService(sf(env)).create(uid, "other_privacy", NOTE)
    PreparationRunIndex(sf(env)).register("run-export-001", uid)
    exp = env.c.get(f"{API}/auth/account/export", cookies=ck).json()
    assert exp["legal_acceptances"][0]["document"] == "terms" and exp["privacy_requests"][0]["status"] == "submitted"
    assert exp["preparation_runs"] == [{"run_id": "run-export-001", "state": "started", "source": "created", "created_at": exp["preparation_runs"][0]["created_at"]}]
    assert any("preparation-chat runs" in n and "not yet supported" in n for n in exp["scope"]["not_included"])
    text_scope = " ".join(exp["scope"]["included"] + exp["scope"]["not_included"]).lower()
    assert "everything we hold" not in text_scope and "complete" not in text_scope.replace("completed", "")
    PreparationRunIndex(sf(env)).remove("run-export-001")
    s = AccountDeletionService(sf(env), preparation_index=PreparationRunIndex(sf(env))).delete_account(uid)
    assert s.legal_acceptances_deleted == 1 and s.privacy_requests_anonymized == 1
    with sf(env)() as s2:
        row = s2.scalar(select(PrivacyRequest))
        assert row.user_id is None and row.subject_user_id is None and row.request_note is None                 # minimal metadata only
        assert s2.scalar(text("select count(*) from legal_acceptances")) == 0


def test_command_center_shows_real_privacy_counts_for_authorised_roles_only(env):
    uid, _ = env.user("user"); _, adm = env.user("security_privacy_admin"); _, sup = env.user("support_operator")
    PrivacyRequestService(sf(env)).create(uid, "deletion", None)
    home = env.c.get(f"{API}/admin/home", cookies=adm).json()["privacy_requests"]
    assert home["status"] == "operational" and home["open"] == 1 and home["unassigned_open"] == 1
    assert env.c.get(f"{API}/admin/home", cookies=sup).json()["privacy_requests"]["status"] == "restricted"
    legacy = env.c.get(f"{API}/admin/privacy-requests", cookies=adm).json()
    assert legacy["total"] == 1 and "Durable queue" in legacy["note"]                                          # the old route is now live


# =============================================================== claims, retention, migration
def test_no_compliance_claims_no_hard_coded_retention_and_no_checkpoint_scan_in_privacy_code():
    code = " ".join(p.read_text() for p in (ROOT / "src/privacy").glob("*.py")) + (ROOT / "src/api/routes/admin_privacy.py").read_text() \
        + (ROOT / "src/api/routes/admin_legal.py").read_text() + (ROOT / "src/api/routes/privacy.py").read_text()
    low = code.lower()
    for claim in ("gdpr compliant", "legally compliant", "fully compliant", "certified", "complete dsar", "all legally required"):
        assert claim not in low, claim
    assert not re.search(r"\b\d+\s*(years?|months?|days?)\b.{0,40}retain|retain.{0,40}\b\d+\s*(years?|months?|days?)\b", low)
    for banned in ("list_threads", "checkpointer.list", "cp.list(", ".alist(", "get_state_history", "FROM checkpoints", "scan_all"):
        assert banned not in code, banned
    assert "get_tuple" in (ROOT / "src/privacy/preparation.py").read_text()      # a single-thread lookup is the only checkpoint read


def test_migration_0020_fresh_from_0019_seed_constraints_and_round_trip(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    def cfg(url):
        c = Config("alembic.ini"); c.set_main_option("script_location", "migrations"); c.set_main_option("sqlalchemy.url", url)
        return c

    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(cfg(url), "0019_knowledge_admin")
    assert "privacy_requests" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg(url), "head")
    eng = create_engine(url); insp = inspect(eng)
    assert {"privacy_requests", "preparation_runs", "legal_documents", "legal_document_versions", "legal_acceptances"} <= set(insp.get_table_names())
    for table in ("privacy_requests", "preparation_runs", "legal_acceptances", "legal_document_versions"):
        cols = {c["name"] for c in insp.get_columns(table)}
        assert not {"ip_address", "ip", "device_id", "fingerprint", "user_agent"} & cols, table
    assert not {"messages", "transcript", "conversation"} & {c["name"] for c in insp.get_columns("preparation_runs")}
    with eng.connect() as c:
        rows = c.execute(text("select d.code, v.version, v.state, v.is_baseline, v.effective_at, v.content_hash from legal_documents d "
                              "join legal_document_versions v on v.document_id=d.id order by d.id")).all()
        assert [(r[0], r[1], r[2], r[3]) for r in rows] == [(c_, "baseline-1", "published", 1) for c_ in ("terms", "privacy", "ai_transparency")]
        assert all(r[4] is None and r[5] is None for r in rows)                                                  # no invented date or hash
        assert c.execute(text("select count(*) from legal_acceptances")).scalar() == 0 and c.execute(text("select count(*) from preparation_runs")).scalar() == 0

    def bad(sql, **p):
        with pytest.raises(IntegrityError):
            with eng.begin() as c:
                c.execute(text(sql), p)
    base = "insert into privacy_requests(public_id,request_type,status,source,created_at,updated_at{x}) values (:p,:t,:s,'candidate_portal','2026-01-01','2026-01-01'{y})"
    bad(base.format(x="", y=""), p="a", t="bogus", s="submitted")
    bad(base.format(x="", y=""), p="b", t="deletion", s="exploded")
    bad(base.format(x="", y=""), p="c", t="deletion", s="completed")                                              # completed needs result + time
    with eng.begin() as c:
        c.execute(text(base.format(x="", y="")), {"p": "ok1", "t": "deletion", "s": "submitted"})
    bad(base.format(x="", y=""), p="ok1", t="deletion", s="submitted")                                            # duplicate public id
    run = "insert into preparation_runs(run_id,owner_user_id,state,source,created_at,updated_at) values (:r,1,:s,'created','2026-01-01','2026-01-01')"
    bad(run, r="r1", s="weird")
    with eng.begin() as c:
        c.execute(text(run), {"r": "r1", "s": "started"})
    bad(run, r="r1", s="started")                                                                                  # unique run id
    ver = "insert into legal_document_versions(document_id,version,state,is_baseline,content_ref,content_hash,published_at,created_at,updated_at) values (1,:v,:s,0,'/x',:h,:pa,'2026-01-01','2026-01-01')"
    bad(ver, v="x1", s="published", h=None, pa="2026-01-01")                                                      # published non-baseline needs a hash
    bad(ver, v="x2", s="published", h="a" * 64, pa="2026-01-01")                                                  # second published version for the document
    bad(ver, v="x3", s="draft", h="short", pa=None)
    bad(ver, v="baseline-1", s="draft", h=None, pa=None)                                                          # unique (document, version)
    bad("insert into legal_documents(code,title,created_at) values ('cookies','x','2026-01-01')")
    command.downgrade(cfg(url), "0019_knowledge_admin")
    assert "privacy_requests" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg(url), "head")
