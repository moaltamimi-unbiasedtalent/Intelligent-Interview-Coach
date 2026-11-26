"""04D, AC-03 (IR-AC03-TESTS): a profile and two Opportunities; the data persists across a reload and a backend RESTART; the chosen Opportunity supplies the correct context;
old anonymous records are never silently reassigned; and no candidate can reach another candidate's Opportunity or session.

Offline evidence only: a temp SQLite FILE database (so a second app instance is a real restart), fixture model replies, no provider, no network.
"""

from __future__ import annotations

import json
import os
import tempfile

os.environ.setdefault("DOCUMENT_STORAGE_DIR", tempfile.mkdtemp(prefix="ask4mo_ac03_docs_"))

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select

from scripts.e2e import journey_fakes as F
from src.api import dependencies as deps
from src.api.config import ApiSettings
from src.api.main import create_app
from src.mail import MemoryEmailSender
from src.persistence import Base, make_session_factory
from src.repository import InterviewRepository
from tests._auth_factories import cookies_for, login_token, register

API = "/api/v1"
PW = "correcthorsebattery"
JD_NURSE = "AC03-JD-NURSE: medication safety, ward handover and patient communication."
JD_ELECTRICIAN = "AC03-JD-ELECTRICIAN: circuit inspection, fault finding and wiring regulations."


@pytest.fixture(autouse=True)
def _no_external_network(monkeypatch):
    real_sync, real_async = httpx.Client.send, httpx.AsyncClient.send

    def guard(request):
        if (request.url.host or "") != "testserver":
            raise AssertionError(f"an external network request was attempted: {request.url.host}")

    monkeypatch.setattr(httpx.Client, "send", lambda self, request, **k: (guard(request), real_sync(self, request, **k))[1])

    async def asynch(self, request, **k):
        guard(request)
        return await real_async(self, request, **k)

    monkeypatch.setattr(httpx.AsyncClient, "send", asynch)


def _boot(db_path: Path):
    """One app instance over a FILE database. Calling it again on the same path is a backend restart (new engine, new app, new caches)."""
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, future=True)
    Base.metadata.create_all(engine)
    repo = InterviewRepository(make_session_factory(engine))
    app = create_app(ApiSettings(env="test", frontend_origins=("http://localhost:3000",)))
    app.dependency_overrides[deps.get_repository] = lambda: repo
    from src.application.memory_service import MemoryApplicationService
    from src.repository import MemoryRepository

    mem = MemoryApplicationService(MemoryRepository(repo.session_factory))
    app.dependency_overrides[deps.get_memory_service] = lambda: mem
    app.dependency_overrides[deps.get_email_sender] = lambda: MemoryEmailSender()
    # get_session_store is reached through Depends, so this override binds interview sessions to THIS database file (otherwise they would land in the process-wide test
    # database and a "restart" would prove nothing about them).
    from src.interview.session_repository import DurableInterviewSessionStore

    store = DurableInterviewSessionStore(repo.session_factory)
    app.dependency_overrides[deps.get_session_store] = lambda: store
    fake = F.install_offline_interview_services(app, "healthy", capture_prompts=True)
    client = TestClient(app)
    client.__enter__()
    return client, repo, fake


def _user(c: TestClient, email: str):
    assert register(c, email, PW).status_code in (200, 201)
    token = login_token(c, email, PW)
    return cookies_for(token), token


def _opp(c, ck, role, jd_text=None):
    body = {"target_role": role, "company_name": f"{role} Co"}
    if jd_text:
        up = c.post(f"{API}/documents", files={"file": ("jd.txt", jd_text.encode(), "text/plain")}, data={"category": "job_description"}, cookies=ck)
        assert up.status_code in (200, 201), up.text
        body["job_description_document_id"] = up.json()["id"]
    r = c.post(f"{API}/opportunities", json=body, cookies=ck)
    assert r.status_code == 201, r.text
    return r.json()


def _start(c, ck, opp):
    cfg = {"target_role": opp["target_role"], "industry_or_sector": "Healthcare", "career_level": "mid", "number_of_questions": 1, "conversation_language": "en"}
    if opp.get("job_description_document_id"):
        cfg["job_description_document_id"] = opp["job_description_document_id"]
    return c.post(f"{API}/interviews", json={"configuration": cfg, "opportunity_id": opp["id"]}, cookies=ck)


def _install_agent(client, repo, checkpoint):
    from src.application.agent_service import AgentApplicationService
    from src.privacy.preparation import PreparationRunIndex

    model = F.ScriptedAgentModel()
    service = AgentApplicationService(
        model_factory=lambda: model, career_service=F.NoRetrievalCareerService(),
        checkpoint_url=f"sqlite:///{checkpoint}", run_index=PreparationRunIndex(repo.session_factory),
    )
    client.app.state.resources["agent_service"] = service
    return model


@pytest.mark.parametrize("start_path", ["run", "run/stream"])
def test_mo_binds_only_the_owned_opportunity_and_restores_it_after_restart(tmp_path, start_path):
    db = tmp_path / "linked.db"
    checkpoint = tmp_path / "agent_checkpoints.sqlite"
    c, repo, _ = _boot(db)
    model = _install_agent(c, repo, checkpoint)
    owner, _ = _user(c, "linked-owner@example.com")
    other, _ = _user(c, "linked-other@example.com")
    first = _opp(c, owner, "Other role")
    selected = _opp(c, owner, "Senior Product Manager")
    foreign = _opp(c, other, "Private role")
    deleted = _opp(c, owner, "Deleted role")
    assert c.delete(f"{API}/opportunities/{deleted['id']}", cookies=owner).status_code == 200
    body = {"goal": F.LINKED_HANDOFF_GOAL, "target_role": selected["target_role"]}
    for invalid in (foreign["id"], deleted["id"], 9999):
        refused = c.post(f"{API}/agent/{start_path}", json={**body, "opportunity_id": invalid}, cookies=owner)
        assert refused.status_code == 404
    assert model.calls == 0
    assert c.get(f"{API}/agent/runs", cookies=owner).json()["runs"] == []
    started = c.post(f"{API}/agent/{start_path}", json={**body, "opportunity_id": selected["id"]}, cookies=owner)
    assert started.status_code == 200, started.text
    if start_path == "run/stream":
        events = [json.loads(line[6:]) for line in started.text.splitlines() if line.startswith("data: ")]
        run_id = next(event["run_id"] for event in events if event.get("run_id"))
    else:
        run_id = started.json()["run_id"]
        assert started.json()["opportunity_id"] == selected["id"]
    c.__exit__(None, None, None)

    c, repo, fake = _boot(db)
    model = _install_agent(c, repo, checkpoint)
    restored = c.get(f"{API}/agent/runs/{run_id}?opportunity={first['id']}", cookies=owner)
    assert restored.status_code == 200
    run = restored.json()
    assert run["opportunity_id"] == selected["id"]
    assert run["pending_action"]["type"] == "approve_practice_handoff"
    assert c.get(f"{API}/agent/runs/{run_id}", cookies=other).status_code == 404
    headers = {"Idempotency-Key": f"agent-handoff:{run_id}"}
    pending = {
        "preparation_context": run["preparation_context"], "opportunity_id": first["id"],
        "industry_or_sector": "Software", "career_level": "senior",
    }
    assert c.post(f"{API}/interviews", json=pending, headers=headers, cookies=owner).status_code == 409
    assert c.post(f"{API}/interviews", json=pending, headers=headers, cookies=other).status_code == 404
    assert not fake.calls and model.calls == 0
    approved = c.post(
        f"{API}/agent/runs/{run_id}/resume",
        json={"action_id": run["pending_action"]["action_id"], "decision": "approve"}, cookies=owner,
    )
    assert approved.status_code == 200, approved.text
    run = approved.json()
    assert run["handoff_approved"] and run["opportunity_id"] == selected["id"]
    assert c.post(f"{API}/interviews", json=pending, headers=headers, cookies=owner).status_code == 409
    assert not fake.calls
    handoff = {"preparation_context": {**run["preparation_context"], "target_role": "Substituted role"},
               "industry_or_sector": "Software", "career_level": "senior", "number_of_questions": 1}
    created = c.post(f"{API}/interviews", json=handoff, headers=headers, cookies=owner)
    assert created.status_code == 200, created.text
    assert created.json()["target_role"] == selected["target_role"]
    sid = created.json()["session_id"]
    assert fake.calls == ["InterviewStrategy", "InterviewQuestion"]
    c.__exit__(None, None, None)

    c, repo, fake = _boot(db)
    model = _install_agent(c, repo, checkpoint)
    reload_body = {"preparation_context": run["preparation_context"], "opportunity_id": selected["id"]}
    retry = c.post(f"{API}/interviews", json=reload_body, headers=headers, cookies=owner)
    assert retry.status_code == 200 and retry.json() == created.json()
    assert not fake.calls and model.calls == 0
    assert c.post(f"{API}/interviews/{sid}/answers", json={"answer": "I compared two roadmap options."}, cookies=owner).status_code == 200
    assert c.post(f"{API}/interviews/{sid}/next-question", cookies=owner).json()["state"] == "INTERVIEW_COMPLETE"
    report = c.post(f"{API}/interviews/{sid}/report", cookies=owner).json()
    assert report["saved_report_id"]
    assert c.post(f"{API}/interviews/{sid}/report", cookies=owner).json()["saved_report_id"] == report["saved_report_id"]
    assert c.get(f"{API}/opportunities/{selected['id']}", cookies=owner).json()["interview_ids"] == [report["saved_report_id"]]
    assert c.get(f"{API}/opportunities/{first['id']}", cookies=owner).json()["interview_count"] == 0
    history = c.get(f"{API}/history/interviews", cookies=owner).json()["interviews"]
    assert [row["id"] for row in history] == [report["saved_report_id"]]
    assert c.get(f"{API}/progress", cookies=owner).json()["interviews_completed"] == 1
    c.__exit__(None, None, None)


def _approved_handoff(client, cookies, opportunity_id=None):
    started = client.post(f"{API}/agent/run", json={
        "goal": F.LINKED_HANDOFF_GOAL, "target_role": "Senior Product Manager", "opportunity_id": opportunity_id,
    }, cookies=cookies)
    assert started.status_code == 200, started.text
    run = started.json()
    approved = client.post(f"{API}/agent/runs/{run['run_id']}/resume", json={
        "action_id": run["pending_action"]["action_id"], "decision": "approve",
    }, cookies=cookies)
    assert approved.status_code == 200 and approved.json()["handoff_approved"]
    return {"Idempotency-Key": f"agent-handoff:{run['run_id']}"}


@pytest.mark.parametrize("linked", [True, False])
def test_handoff_refuses_a_preexisting_wrong_link_without_rewriting_it(tmp_path, linked):
    c, repo, fake = _boot(tmp_path / "preexisting.db")
    _install_agent(c, repo, tmp_path / "agent_checkpoints.sqlite")
    owner, _ = _user(c, "preexisting@example.com")
    wrong = _opp(c, owner, "Other role")["id"]
    selected = _opp(c, owner, "Senior Product Manager")["id"] if linked else None
    headers = _approved_handoff(c, owner, selected)
    with repo.session_factory() as db:
        from src.persistence import User

        user_id = db.scalar(select(User.id).where(User.email == "preexisting@example.com"))
    store = c.app.dependency_overrides[deps.get_session_store]()
    existing_id, created = store.create_or_get(user_id, headers["Idempotency-Key"], opportunity_id=wrong)
    assert created
    refused = c.post(f"{API}/interviews", json={
        "industry_or_sector": "Software", "career_level": "senior",
    }, headers=headers, cookies=owner)
    assert refused.status_code == 409 and not fake.calls
    assert store.find_idempotent_session(user_id, headers["Idempotency-Key"]) == existing_id
    assert store.opportunity_id_for(existing_id, user_id) == wrong
    assert store.load_state(existing_id, user_id).data.questions == []
    c.__exit__(None, None, None)


def test_handoff_retry_after_another_create_releases_its_lease_does_not_dispatch(tmp_path, monkeypatch):
    from src.persistence import InterviewSession

    c, repo, fake = _boot(tmp_path / "concurrent.db")
    _install_agent(c, repo, tmp_path / "agent_checkpoints.sqlite")
    owner, _ = _user(c, "concurrent@example.com")
    selected = _opp(c, owner, "Senior Product Manager")["id"]
    headers = _approved_handoff(c, owner, selected)
    store = c.app.dependency_overrides[deps.get_session_store]()
    claim_lease = store._claim_lease
    first_at_claim, second_at_claim, first_finished = Event(), Event(), Event()
    lock = Lock()
    claims = 0

    def ordered_claim(session_id, user_id, operation):
        nonlocal claims
        assert operation == "create"
        with lock:
            claims += 1
            first = claims == 1
        if first:
            first_at_claim.set()
            assert second_at_claim.wait(10)
        else:
            second_at_claim.set()
            assert first_finished.wait(10)
        return claim_lease(session_id, user_id, operation)

    def create():
        return c.post(f"{API}/interviews", json={
            "industry_or_sector": "Software", "career_level": "senior",
        }, headers=headers, cookies=owner)

    def first_create():
        try:
            return create()
        finally:
            first_finished.set()

    monkeypatch.setattr(store, "_claim_lease", ordered_claim)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_create)
        assert first_at_claim.wait(10)
        second = pool.submit(create)
        one, two = first.result(timeout=20), second.result(timeout=20)
    assert claims == 2
    assert one.status_code == two.status_code == 200
    assert one.json() == two.json()
    assert fake.calls == ["InterviewStrategy", "InterviewQuestion"]
    with repo.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(InterviewSession)) == 1
        row = db.get(InterviewSession, one.json()["session_id"])
        assert row.opportunity_id == selected and row.active_operation is None
    c.__exit__(None, None, None)


def test_deleting_the_opportunity_after_mo_approval_does_not_start_unlinked_practice(tmp_path):
    c, repo, fake = _boot(tmp_path / "deleted-after-approval.db")
    _install_agent(c, repo, tmp_path / "agent_checkpoints.sqlite")
    owner, _ = _user(c, "deleted-after-approval@example.com")
    selected = _opp(c, owner, "Senior Product Manager")
    run = c.post(f"{API}/agent/run", json={
        "goal": F.LINKED_HANDOFF_GOAL, "target_role": selected["target_role"], "opportunity_id": selected["id"],
    }, cookies=owner).json()
    run_id = run["run_id"]
    approved = c.post(f"{API}/agent/runs/{run_id}/resume", json={
        "action_id": run["pending_action"]["action_id"], "decision": "approve",
    }, cookies=owner).json()
    assert approved["handoff_approved"]
    assert c.delete(f"{API}/opportunities/{selected['id']}", cookies=owner).status_code == 200
    restored = c.get(f"{API}/agent/runs/{run_id}", cookies=owner).json()
    assert restored["opportunity_id"] == selected["id"]
    refused = c.post(f"{API}/interviews", json={
        "preparation_context": restored["preparation_context"], "opportunity_id": restored["opportunity_id"],
        "industry_or_sector": "Software", "career_level": "senior",
    }, headers={"Idempotency-Key": f"agent-handoff:{run_id}"}, cookies=owner)
    assert refused.status_code == 404
    assert not fake.prompts
    assert c.get(f"{API}/interviews", cookies=owner).json()["sessions"] == []
    c.__exit__(None, None, None)


# ------------------------------------------------------------------------------------------------------------- chosen Opportunity supplies the correct context
def test_the_chosen_opportunity_supplies_its_own_role_and_job_description_and_never_the_others(tmp_path):
    c, _repo, fake = _boot(tmp_path / "a.db")
    ck, _ = _user(c, "ctx@example.com")
    nurse = _opp(c, ck, "Registered Nurse", JD_NURSE)
    electrician = _opp(c, ck, "Electrician", JD_ELECTRICIAN)
    assert nurse["id"] != electrician["id"]
    r = _start(c, ck, electrician)
    assert r.status_code == 200, r.text
    assert r.json()["target_role"] == "Electrician"
    sent = "\n".join(fake.prompts)
    assert "AC03-JD-ELECTRICIAN" in sent and "AC03-JD-NURSE" not in sent       # the chosen Opportunity's context reached the model, the other one did not
    sessions = c.get(f"{API}/interviews", cookies=ck).json()["sessions"]
    assert [s["target_role"] for s in sessions] == ["Electrician"]
    # Finish it: the completed interview is attached to the chosen Opportunity only.
    sid = r.json()["session_id"]
    assert c.post(f"{API}/interviews/{sid}/answers", json={"answer": "I inspected the circuit and isolated the fault."}, cookies=ck).status_code == 200
    assert c.post(f"{API}/interviews/{sid}/next-question", cookies=ck).json()["state"] == "INTERVIEW_COMPLETE"
    assert c.post(f"{API}/interviews/{sid}/report", cookies=ck).status_code == 200
    assert c.get(f"{API}/opportunities/{electrician['id']}", cookies=ck).json()["interview_count"] == 1
    assert c.get(f"{API}/opportunities/{nurse['id']}", cookies=ck).json()["interview_count"] == 0


# ------------------------------------------------------------------------------------------------------------- persistence: reload and restart
def test_profile_two_opportunities_and_an_in_progress_interview_survive_a_backend_restart(tmp_path):
    db = tmp_path / "restart.db"
    c1, _repo1, _fake1 = _boot(db)
    ck, token = _user(c1, "restart@example.com")
    assert c1.patch(f"{API}/auth/preferences", json={"target_role": "Registered Nurse", "display_name": "Restart Candidate"}, cookies=ck).status_code == 200
    nurse = _opp(c1, ck, "Registered Nurse", JD_NURSE)
    electrician = _opp(c1, ck, "Electrician", JD_ELECTRICIAN)
    started = _start(c1, ck, nurse)
    assert started.status_code == 200
    sid = started.json()["session_id"]
    c1.__exit__(None, None, None)                                         # the first process is gone

    c2, _repo2, _fake2 = _boot(db)                                        # a NEW app, engine and caches on the same database file
    me = c2.get(f"{API}/auth/me", cookies=cookies_for(token)).json()       # the SAME session cookie still authenticates (server-side sessions are durable)
    assert me["email"] == "restart@example.com" and me["target_role"] == "Registered Nurse" and me["display_name"] == "Restart Candidate"
    listed = c2.get(f"{API}/opportunities", cookies=ck).json()["opportunities"]
    assert sorted(o["target_role"] for o in listed) == ["Electrician", "Registered Nurse"]
    assert {o["id"] for o in listed} == {nurse["id"], electrician["id"]}
    assert c2.get(f"{API}/opportunities/{nurse['id']}", cookies=ck).json()["jd_available"] is True
    resumed = c2.get(f"{API}/interviews/{sid}", cookies=ck)
    assert resumed.status_code == 200 and resumed.json()["state"] == "AWAITING_ANSWER" and resumed.json()["current_question"]["question"]   # resumable after restart
    assert [s["session_id"] for s in c2.get(f"{API}/interviews", cookies=ck).json()["sessions"]] == [sid]
    c2.__exit__(None, None, None)


def test_a_reload_returns_the_same_opportunities_in_the_same_order(tmp_path):
    c, _repo, _fake = _boot(tmp_path / "reload.db")
    ck, _ = _user(c, "reload@example.com")
    ids = [_opp(c, ck, role)["id"] for role in ("Chef", "Pilot", "Teacher")]
    first = [o["id"] for o in c.get(f"{API}/opportunities", cookies=ck).json()["opportunities"]]
    second = [o["id"] for o in c.get(f"{API}/opportunities", cookies=ck).json()["opportunities"]]
    assert first == second and set(first) == set(ids)


# ------------------------------------------------------------------------------------------------------------- legacy anonymous rows are not adopted
def test_old_anonymous_records_are_never_silently_reassigned_to_a_registered_account(tmp_path):
    c, repo, _fake = _boot(tmp_path / "legacy.db")
    anon = c.post(f"{API}/opportunities", json={"target_role": "Legacy Anonymous Role"})           # no cookie: the development anonymous identity
    assert anon.status_code == 201, anon.text
    anon_id = anon.json()["id"]
    anon_iid = repo.save_interview(repo.get_or_create_user(subject="local-dev", provider="dev", display_name="Local developer", email=None),
                                   {"configuration": {"target_role": "Legacy Anonymous Role"}, "mode": "Record", "status": "completed", "questions": [], "report": {}})
    ck, _ = _user(c, "newcomer@example.com")
    assert c.get(f"{API}/opportunities", cookies=ck).json()["opportunities"] == []                   # nothing was adopted
    assert c.get(f"{API}/opportunities/{anon_id}", cookies=ck).status_code == 404
    assert c.get(f"{API}/history/interviews", cookies=ck).json()["interviews"] == []
    assert c.get(f"{API}/history/interviews/{anon_iid}", cookies=ck).status_code == 404
    assert c.get(f"{API}/progress", cookies=ck).json()["interviews_completed"] == 0
    # The legacy rows are still where they were (still the anonymous identity's), neither deleted nor moved.
    with TestClient(c.app) as anonymous:                                                           # a fresh client with no session cookie: the development anonymous identity again
        assert anonymous.get(f"{API}/opportunities/{anon_id}").status_code == 200


# ------------------------------------------------------------------------------------------------------------- cross-user isolation
def test_a_candidate_cannot_link_read_or_resume_another_candidates_opportunity_or_session(tmp_path):
    c, _repo, _fake = _boot(tmp_path / "iso.db")
    a_ck, _ = _user(c, "iso-a@example.com")
    b_ck, _ = _user(c, "iso-b@example.com")
    a_opp = _opp(c, a_ck, "Isolated Role A", JD_NURSE)
    a_session = _start(c, a_ck, a_opp).json()["session_id"]
    assert c.get(f"{API}/opportunities/{a_opp['id']}", cookies=b_ck).status_code == 404
    assert c.get(f"{API}/opportunities", cookies=b_ck).json()["opportunities"] == []
    # B cannot attach a new interview to A's Opportunity (not-found, never A's data) and creates nothing.
    foreign = c.post(f"{API}/interviews", json={"configuration": {"target_role": "x", "industry_or_sector": "y", "career_level": "mid", "number_of_questions": 1, "conversation_language": "en"},
                                                "opportunity_id": a_opp["id"]}, cookies=b_ck)
    assert foreign.status_code == 404
    assert c.get(f"{API}/interviews", cookies=b_ck).json()["sessions"] == []
    assert c.get(f"{API}/interviews/{a_session}", cookies=b_ck).status_code in (404, 422)
    assert c.post(f"{API}/interviews/{a_session}/answers", json={"answer": "intrusion"}, cookies=b_ck).status_code in (404, 422)
    assert c.get(f"{API}/interviews/{a_session}", cookies=a_ck).status_code == 200                    # the owner is unaffected
