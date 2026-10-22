"""04D, AC-03 (IR-AC03-TESTS): a profile and two Opportunities; the data persists across a reload and a backend RESTART; the chosen Opportunity supplies the correct context;
old anonymous records are never silently reassigned; and no candidate can reach another candidate's Opportunity or session.

Offline evidence only: a temp SQLite FILE database (so a second app instance is a real restart), fixture model replies, no provider, no network.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("DOCUMENT_STORAGE_DIR", tempfile.mkdtemp(prefix="ask4mo_ac03_docs_"))

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

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
