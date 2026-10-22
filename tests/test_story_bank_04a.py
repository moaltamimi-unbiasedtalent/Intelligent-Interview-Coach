"""04A Story Bank completion (REQ-OWN-06): lifecycle, verification truthfulness, search, suggestions, Practice reuse with consent and attribution, deletion
correctness, sharing consent, cross-user isolation on EVERY route, metadata-only logs and the migration. Offline: fakes for generation, temp SQLite only."""

from __future__ import annotations

import json
import logging
import os
import tempfile

os.environ.setdefault("DOCUMENT_STORAGE_DIR", tempfile.mkdtemp(prefix="ask4mo_04a_test_"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src import persistence as P
from src.api import dependencies as deps
from src.documents.repository import STORY_BLOCK_CLOSE, STORY_BLOCK_OPEN, StoryRepository, quality_prompts, strip_story_blocks
from tests._auth_factories import build_auth_app, cookies_for, login_token, register

PW = "correcthorsebattery"
SENTINEL = "SENTINEL-STORY-TEXT-8f3a"
CV = (
    "Jane Doe\nSenior Software Engineer at Acme Corp\n"
    "Skills: Python, FastAPI, Kubernetes\n"
    "- Reduced latency by 40% across core services\n"
).encode()
S = "/api/v1/stories"
_OPEN: list[TestClient] = []


@pytest.fixture(autouse=True)
def _close_clients():
    yield
    while _OPEN:
        _OPEN.pop().__exit__(None, None, None)


class Env:
    def __init__(self):
        self.app, self.repo, self.mail = build_auth_app()
        self.c = TestClient(self.app)
        self.c.__enter__()
        _OPEN.append(self.c)
        for e in ("a@example.com", "b@example.com", "m@example.com"):
            register(self.c, e, PW)
        self.a, self.b, self.m = (login_token(self.c, f"{x}@example.com", PW) for x in ("a", "b", "m"))
        self.ck_a, self.ck_b, self.ck_m = cookies_for(self.a), cookies_for(self.b), cookies_for(self.m)
        self.uid_a = self.c.get("/api/v1/auth/me", cookies=self.ck_a).json()["user_id"]
        self.uid_b = self.c.get("/api/v1/auth/me", cookies=self.ck_b).json()["user_id"]

    def story(self, ck=None, **kw):
        body = {"title": "Led a migration", "status": "user_created", "situation": "Legacy billing", "task": "Move it",
                "action": "I planned the cut-over with the team and ran the rollout in three stages", "result": "Zero downtime", "competencies": ["Leadership"]}
        body.update(kw)
        r = self.c.post(S, json=body, cookies=ck or self.ck_a)
        assert r.status_code == 201, r.text
        return r.json()

    def doc(self, ck=None):
        r = self.c.post("/api/v1/documents", files={"file": ("cv.txt", CV, "text/plain")}, data={"category": "cv"}, cookies=ck or self.ck_a)
        assert r.status_code == 201, r.text
        return r.json()

    def answer_id(self, uid):
        payload = {"configuration": {"target_role": "PM"}, "mode": "Record", "status": "completed", "questions": [{
            "position": 0, "canonical_question": "Tell me about a challenge.", "question_type": "behavioural", "difficulty": "moderate",
            "timing_guidance": {}, "answer": {"text": "My own answer", "evaluation": {"overall_score": 70}, "timing_metrics": {}, "visual_metrics": {}}}]}
        iid = self.repo.save_interview(uid, payload)
        with self.repo.session_factory() as s:
            return s.scalar(select(P.Answer.id).join(P.Question, P.Question.id == P.Answer.question_id).where(P.Question.interview_id == iid))

    def opportunity(self, ck=None, role="Registered Nurse"):
        r = self.c.post("/api/v1/opportunities", json={"target_role": role}, cookies=ck or self.ck_a)
        assert r.status_code in (200, 201), r.text
        return r.json()["id"]

    def workspace_with_member(self):
        wid = self.c.post("/api/v1/workspaces", json={"name": "Alpha"}, cookies=self.ck_a).json()["id"]
        self.c.post(f"/api/v1/workspaces/{wid}/invite", json={"email": "b@example.com"}, cookies=self.ck_a)
        tok = self.mail.sent[-1].body.split("token=")[1].split()[0]
        assert self.c.post("/api/v1/workspaces/invitations/accept", json={"token": tok}, cookies=self.ck_b).status_code in (200, 201)
        return wid

    def share(self, wid, sid):
        r = self.c.post("/api/v1/shares", json={"workspace_id": wid, "resource_type": "story", "resource_id": str(sid)}, cookies=self.ck_a)
        return r

    def repo_stories(self):
        return StoryRepository(self.repo.session_factory)


# --- lifecycle: create, edit, archive, restore, delete ---------------------------------------------------------------------------------------------

def test_create_edit_archive_restore_delete_lifecycle():
    e = Env()
    st = e.story(competencies=["Leadership", "leadership", " Planning "])
    assert st["competencies"] == ["Leadership", "Planning"] and st["status"] == "user_created" and st["verification"] == "unverified"
    r = e.c.patch(f"{S}/{st['id']}", json={"result": "Zero downtime, three stages"}, cookies=e.ck_a)
    assert r.status_code == 200 and r.json()["result"] == "Zero downtime, three stages" and r.json()["status"] == "user_created"
    assert e.c.post(f"{S}/{st['id']}/archive", cookies=e.ck_a).json()["archived_at"]
    assert e.c.get(S, cookies=e.ck_a).json()["stories"] == []                                   # archived are out of the default list
    arch = e.c.post(f"{S}/search", json={"archived": "archived"}, cookies=e.ck_a).json()["stories"]
    assert [s["id"] for s in arch] == [st["id"]]
    assert e.c.post(f"{S}/{st['id']}/restore", cookies=e.ck_a).json()["archived_at"] is None
    assert [s["id"] for s in e.c.get(S, cookies=e.ck_a).json()["stories"]] == [st["id"]]
    assert e.c.delete(f"{S}/{st['id']}", cookies=e.ck_a).status_code == 200
    assert e.c.get(f"{S}/{st['id']}", cookies=e.ck_a).status_code == 404
    assert e.c.delete(f"{S}/{st['id']}", cookies=e.ck_a).status_code == 404                    # idempotent, never a 5xx


def test_validation_rejects_bad_input():
    e = Env()
    assert e.c.post(S, json={"title": "", "status": "user_created"}, cookies=e.ck_a).status_code == 422
    assert e.c.post(S, json={"title": "x", "status": "bogus"}, cookies=e.ck_a).status_code == 422
    assert e.c.post(S, json={"title": "x", "status": "source_backed"}, cookies=e.ck_a).status_code == 422
    assert e.c.post(S, json={"title": "x", "status": "user_created", "situation": "s" * 4001}, cookies=e.ck_a).status_code == 422
    st = e.story()
    assert e.c.patch(f"{S}/{st['id']}", json={}, cookies=e.ck_a).status_code == 422             # nothing to update


def test_editing_model_suggested_text_makes_it_user_corrected_and_confirm_makes_it_usable():
    e = Env()
    st = e.story(status="model_suggested")
    assert st["status"] == "model_suggested"
    assert e.repo_stories().evidence_stories(e.uid_a) == []                                     # an unconfirmed suggestion is not usable
    assert e.c.post(f"{S}/{st['id']}/confirm", cookies=e.ck_a).status_code == 200
    assert [s["id"] for s in e.repo_stories().evidence_stories(e.uid_a)] == [st["id"]]          # the candidate's approval makes it usable
    e2 = e.story(status="model_suggested", title="Other")
    edited = e.c.patch(f"{S}/{e2['id']}", json={"action": "I rewrote the plan myself with the whole team over a month"}, cookies=e.ck_a).json()
    assert edited["status"] == "user_corrected"


# --- verification: nothing is verified without evidence ---------------------------------------------------------------------------------------------

def test_unverified_self_confirmed_and_evidence_verified_are_distinct():
    e = Env()
    st = e.story()
    assert st["verification"] == "unverified" and st["evidence_state"] == "none"
    conf = e.c.post(f"{S}/{st['id']}/confirm", cookies=e.ck_a).json()
    assert conf["verification"] == "self_confirmed" and conf["evidence_state"] == "none"       # attestation is NOT evidence
    edited = e.c.patch(f"{S}/{st['id']}", json={"situation": "Changed context"}, cookies=e.ck_a).json()
    assert edited["confirmed_at"] is None and edited["verification"] == "unverified"           # a confirmation applies to the text confirmed
    doc = e.doc()
    cid = doc["claims"][0]["id"]
    with_claim = e.c.post(f"{S}/{st['id']}/evidence", json={"kind": "claim", "ref_id": cid}, cookies=e.ck_a).json()
    assert with_claim["verification"] == "evidence_verified" and with_claim["evidence_claim_ids"] == [cid]
    assert e.c.delete(f"{S}/{st['id']}/confirm", cookies=e.ck_a).json()["verification"] == "evidence_verified"
    removed = e.c.delete(f"{S}/{st['id']}/evidence/claim/{cid}", cookies=e.ck_a).json()
    assert removed["verification"] == "unverified" and removed["evidence_claim_ids"] == []


def test_rejecting_a_claim_or_deleting_its_document_revokes_verification_even_after_user_correction():
    e = Env()
    doc = e.doc()
    ids = [c["id"] for c in doc["claims"][:2]]
    st = e.c.post(f"{S}/draft", json={"title": "Win", "claim_ids": ids}, cookies=e.ck_a).json()
    assert st["verification"] == "evidence_verified"
    corrected = e.c.patch(f"{S}/{st['id']}", json={"result": "Reworded outcome"}, cookies=e.ck_a).json()
    assert corrected["status"] == "user_corrected" and corrected["verification"] == "evidence_verified"
    for cid in ids:
        assert e.c.post(f"/api/v1/documents/{doc['id']}/claims/{cid}/review", json={"action": "reject"}, cookies=e.ck_a).status_code == 200
    after = e.c.get(f"{S}/{st['id']}", cookies=e.ck_a).json()
    assert after["evidence_state"] == "source_revoked" and after["verification"] == "source_revoked"      # a rejected claim is not live evidence
    st2 = e.c.post(f"{S}/draft", json={"title": "Win2", "claim_ids": [doc["claims"][2]["id"]]}, cookies=e.ck_a).json()
    e.c.patch(f"{S}/{st2['id']}", json={"result": "Reworded"}, cookies=e.ck_a)
    e.c.delete(f"/api/v1/documents/{doc['id']}", cookies=e.ck_a)
    gone = e.c.get(f"{S}/{st2['id']}", cookies=e.ck_a).json()
    assert gone["status"] == "user_corrected" and gone["verification"] == "source_revoked"               # the G3 defect: was stuck on "verified"


def test_answer_link_is_a_reference_and_weaker_than_document_evidence():
    e = Env()
    st = e.story()
    aid = e.answer_id(e.uid_a)
    linked = e.c.post(f"{S}/{st['id']}/evidence", json={"kind": "answer", "ref_id": aid}, cookies=e.ck_a).json()
    assert linked["verification"] == "answer_linked" and linked["evidence_state"] == "none" and linked["evidence_answer_ids"] == [aid]
    assert "My own answer" not in json.dumps(linked)                                                    # a reference only; no answer text is copied
    # deleting the interview removes the answer: the link stops counting (SQLite does not enforce the cascade)
    with e.repo.session_factory() as s:
        iv = s.scalar(select(P.Interview).where(P.Interview.user_id == e.uid_a))
        s.delete(iv)
        s.commit()
    assert e.c.get(f"{S}/{st['id']}", cookies=e.ck_a).json()["verification"] == "unverified"


def test_quality_prompts_are_codes_that_never_invent_content():
    empty = quality_prompts({"competencies": []})
    assert empty == ["situation_missing", "task_missing", "action_missing", "result_missing", "no_tags"]
    thin = quality_prompts({"situation": "s", "task": "t", "action": "did it", "result": "went well", "competencies": ["x"]})
    assert thin == ["action_thin", "result_no_figure"]
    full = quality_prompts({"situation": "s", "task": "t", "action": "a" * 60, "result": "Cut cost by 12 percent", "competencies": ["x"]})
    assert full == []
    e = Env()
    st = e.story(result="", action="short")
    assert st["result"] is None and "result_missing" in st["quality_prompts"] and "action_thin" in st["quality_prompts"]   # prompts, never auto-filled text


# --- search, filter, tags, Opportunity link ----------------------------------------------------------------------------------------------------------

def test_search_filter_and_tags():
    e = Env()
    one = e.story(title="Migration lead", competencies=["Leadership", "Planning"])
    two = e.story(title="Conflict with a peer", situation="Disagreement over scope", action="I listened and aligned us " * 3, competencies=["Communication"])
    e.c.post(f"{S}/{two['id']}/confirm", cookies=e.ck_a)

    def ids(**body):
        return sorted(s["id"] for s in e.c.post(f"{S}/search", json=body, cookies=e.ck_a).json()["stories"])

    assert ids(q="MIGRATION") == [one["id"]]
    assert ids(q="disagreement scope") == [two["id"]]
    assert ids(q="migration disagreement") == []                                              # every word must match
    assert ids(tag="communication") == [two["id"]]
    assert ids(verification="self_confirmed") == [two["id"]] and ids(verification="unverified") == [one["id"]]
    assert ids(status="user_created") == sorted([one["id"], two["id"]])
    assert e.c.get(f"{S}/tags", cookies=e.ck_a).json()["tags"] == ["Communication", "Leadership", "Planning"]
    assert e.c.post(f"{S}/search", json={"verification": "bogus"}, cookies=e.ck_a).status_code == 422
    assert e.c.post(f"{S}/search", json={"q": "x", "unknown": 1}, cookies=e.ck_a).status_code == 422
    # another account never sees these and its tag list is empty
    assert e.c.post(f"{S}/search", json={"q": "migration"}, cookies=e.ck_b).json()["stories"] == []
    assert e.c.get(f"{S}/tags", cookies=e.ck_b).json()["tags"] == []


def test_opportunity_link_set_clear_foreign_and_unlink_on_opportunity_delete():
    e = Env()
    opp = e.opportunity()
    foreign_opp = e.opportunity(ck=e.ck_b)
    st = e.story(opportunity_id=opp)
    assert st["opportunity_id"] == opp
    assert e.c.post(S, json={"title": "x", "status": "user_created", "opportunity_id": foreign_opp}, cookies=e.ck_a).status_code == 422
    assert e.c.patch(f"{S}/{st['id']}", json={"opportunity_id": foreign_opp}, cookies=e.ck_a).status_code == 422
    assert e.c.post(f"{S}/search", json={"opportunity_id": opp}, cookies=e.ck_a).json()["stories"][0]["id"] == st["id"]
    assert e.c.patch(f"{S}/{st['id']}", json={"title": "Renamed"}, cookies=e.ck_a).json()["opportunity_id"] == opp      # absent = unchanged
    assert e.c.patch(f"{S}/{st['id']}", json={"opportunity_id": None}, cookies=e.ck_a).json()["opportunity_id"] is None   # explicit null clears
    e.c.patch(f"{S}/{st['id']}", json={"opportunity_id": opp}, cookies=e.ck_a)
    assert e.c.delete(f"/api/v1/opportunities/{opp}", cookies=e.ck_a).status_code == 200
    assert e.c.get(f"{S}/{st['id']}", cookies=e.ck_a).json()["opportunity_id"] is None                    # unlinked, story survives


# --- suggestions need approval --------------------------------------------------------------------------------------------------------------------------

def test_suggestions_rank_own_usable_stories_and_require_approval():
    e = Env()
    lead = e.story(title="Migration lead", competencies=["Leadership"])
    e.story(title="Spreadsheet tidy", competencies=["Admin"], situation="Quarterly", action="x" * 50)
    archived = e.story(title="Leadership offsite", competencies=["Leadership"])
    e.c.post(f"{S}/{archived['id']}/archive", cookies=e.ck_a)
    unconfirmed = e.story(title="Suggested leadership story", competencies=["Leadership"], status="model_suggested")
    other = e.story(ck=e.ck_b, title="Leadership at B", competencies=["Leadership"])
    r = e.c.post(f"{S}/suggest", json={"terms": ["leadership"]}, cookies=e.ck_a)
    assert r.status_code == 200
    got = r.json()["suggestions"]
    assert [g["id"] for g in got] == [lead["id"]]                                              # not archived, not unconfirmed, not another account's
    assert got[0]["requires_approval"] is True and "leadership" in got[0]["matched"]
    assert unconfirmed["id"] not in [g["id"] for g in got] and other["id"] not in [g["id"] for g in got]
    assert e.c.post(f"{S}/suggest", json={"terms": []}, cookies=e.ck_a).json()["suggestions"] == []
    assert e.c.post(f"{S}/suggest", json={"terms": ["x"], "opportunity_id": e.opportunity(ck=e.ck_b)}, cookies=e.ck_a).status_code == 422
    role_opp = e.opportunity(role="Migration Lead")
    by_role = e.c.post(f"{S}/suggest", json={"terms": [], "opportunity_id": role_opp}, cookies=e.ck_a).json()["suggestions"]
    assert [g["id"] for g in by_role] == [lead["id"]]


# --- Practice reuse: explicit selection, consent, attribution ------------------------------------------------------------------------------------------

class _Domain:
    def __init__(self):
        self.configs = []

    def generate_strategy(self, config, settings):
        from tests import _interview_factories as f
        self.configs.append(config)
        return f.strategy(), f.usage()

    def generate_next_question(self, config, settings, *, current_question_number, history):
        from tests import _interview_factories as f
        return f.question(current_question_number), f.usage()


def _practice_env():
    from src.api import dependencies as d
    from src.application.interview_service import InterviewApplicationService
    from src.interview.session_repository import DurableInterviewSessionStore
    from tests.test_api import _FakeClient
    from tests import _interview_factories as f

    class _Eval:
        def evaluate_answer(self, config, question, answer, settings):
            return f.evaluation(), f.usage()

    class _Report:
        def generate_report(self, config, questions, answers, evaluations, settings, branch_summaries=()):
            return f.report(), f.usage()

    e = Env()
    domain = _Domain()
    store = DurableInterviewSessionStore(e.repo.session_factory)
    e.app.dependency_overrides[d.get_interview_service] = lambda: InterviewApplicationService(config=None, services=(domain, _Eval(), _Report(), _FakeClient()))
    e.app.dependency_overrides[d.get_app_config] = lambda: None
    e.app.dependency_overrides[d.get_session_store] = lambda: store
    e.domain = domain
    e.store = store
    return e


def _create_practice(e, ck=None, **cfg):
    body = {"configuration": {"target_role": "Registered Nurse", "industry_or_sector": "healthcare", "career_level": "senior", "number_of_questions": 2, **cfg}}
    return e.c.post("/api/v1/interviews", json=body, cookies=ck or e.ck_a)


def test_practice_uses_only_explicitly_selected_stories_with_consent_and_attribution():
    e = _practice_env()
    chosen = e.story(title="Chosen story", result="Result with 12 percent")
    e.story(title="Not chosen", situation=SENTINEL)
    assert _create_practice(e, story_ids=[chosen["id"]]).status_code == 422                       # no consent, nothing sent
    assert e.domain.configs == []
    r = _create_practice(e, story_ids=[chosen["id"]], confirm_story_use=True)
    assert r.status_code == 200, r.text
    bg = e.domain.configs[-1].candidate_background
    assert "Chosen story" in bg and "verification: unverified" in bg and "Result with 12 percent" in bg    # attributed, labelled, the candidate's own text
    assert SENTINEL not in bg                                                                     # an unselected story never reaches the model
    assert STORY_BLOCK_OPEN.format(id=chosen["id"]) in bg and STORY_BLOCK_CLOSE.format(id=chosen["id"]) in bg
    got = e.c.get(f"{S}/{chosen['id']}", cookies=e.ck_a).json()
    assert got["use_count"] == 1 and got["last_used_at"]
    assert len(bg) <= 4000


@pytest.mark.parametrize("kind", ["foreign", "missing", "archived", "unconfirmed_suggestion", "revoked"])
def test_practice_refuses_any_unusable_story_with_one_indistinguishable_error(kind):
    e = _practice_env()
    if kind == "foreign":
        sid = e.story(ck=e.ck_b)["id"]
    elif kind == "missing":
        sid = 987654
    elif kind == "archived":
        sid = e.story()["id"]
        e.c.post(f"{S}/{sid}/archive", cookies=e.ck_a)
    elif kind == "unconfirmed_suggestion":
        sid = e.story(status="model_suggested")["id"]
    else:
        doc = e.doc()
        sid = e.c.post(f"{S}/draft", json={"title": "D", "claim_ids": [doc["claims"][0]["id"]]}, cookies=e.ck_a).json()["id"]
        e.c.delete(f"/api/v1/documents/{doc['id']}", cookies=e.ck_a)
    r = _create_practice(e, story_ids=[sid], confirm_story_use=True)
    assert r.status_code == 422 and "not available" in r.text
    assert e.domain.configs == []                                                                 # nothing reached generation
    msgs = {(r2.status_code, r2.json()["error"]["message"]) for r2 in (_create_practice(e, story_ids=[x], confirm_story_use=True) for x in (sid, 987654))}
    assert len(msgs) == 1                                                                         # foreign and missing look the same


def test_deleting_a_story_strips_its_text_from_sessions_and_removes_it_everywhere():
    e = _practice_env()
    st = e.story(title="Doomed", situation=SENTINEL)
    keep = e.story(title="Keeper", situation="Keep this context")
    r = _create_practice(e, story_ids=[st["id"], keep["id"]], confirm_story_use=True, candidate_background="My own pasted note")
    assert r.status_code == 200
    sid = r.json()["session_id"]
    with e.repo.session_factory() as s:
        row = s.get(P.InterviewSession, sid)
        assert SENTINEL in json.dumps(row.state_payload)
    wid = e.workspace_with_member()
    assert e.share(wid, st["id"]).status_code == 200
    with e.repo.session_factory() as s:                                                           # a pack item that cites the story
        s.add(P.PreparationPack(op_key="p1", user_id=e.uid_a, revision=1, status="completed", schema_version="1",
                                content={"sections": [{"id": "x", "items": [{"kind": "example", "text": SENTINEL, "ref_ids": [f"S{st['id']}", "R1"]},
                                                                            {"kind": "role", "text": "kept item", "ref_ids": []}]}]}))
        s.commit()
    assert e.c.delete(f"{S}/{st['id']}", cookies=e.ck_a).status_code == 200
    with e.repo.session_factory() as s:
        payload = json.dumps(s.get(P.InterviewSession, sid).state_payload)
        assert SENTINEL not in payload and "Doomed" not in payload                                # copied text gone from the session
        assert "Keeper" in payload and "My own pasted note" in payload                            # unrelated text untouched
        pack = json.dumps(s.scalar(select(P.PreparationPack.content)))
        assert SENTINEL not in pack and "kept item" in pack                                       # derived Pack item removed, others kept
        assert s.scalar(select(P.StoryUse).where(P.StoryUse.story_id == st["id"])) is None
    assert e.c.get("/api/v1/shares/mine", cookies=e.ck_a).json()["shares"] == []                  # grants revoked
    assert e.c.get(f"/api/v1/shares/resource/story/{st['id']}", cookies=e.ck_b).status_code == 404
    assert SENTINEL not in json.dumps(e.c.get(S, cookies=e.ck_a).json())
    assert SENTINEL not in json.dumps(e.c.post(f"{S}/search", json={"q": "doomed"}, cookies=e.ck_a).json())
    assert all(g["id"] != st["id"] for g in e.c.post(f"{S}/suggest", json={"terms": ["doomed", "context"]}, cookies=e.ck_a).json()["suggestions"])
    export = e.c.get("/api/v1/auth/account/export", cookies=e.ck_a)
    assert export.status_code == 200 and SENTINEL not in export.text and "Keeper" in export.text


def test_blanket_evidence_option_marks_and_attributes_stories_too():
    e = _practice_env()
    st = e.story(title="Blanket story", result="Outcome text")
    assert _create_practice(e, use_candidate_evidence=True).status_code == 200
    bg = e.domain.configs[-1].candidate_background
    assert STORY_BLOCK_OPEN.format(id=st["id"]) in bg
    assert e.c.get(f"{S}/{st['id']}", cookies=e.ck_a).json()["use_count"] == 1
    e.c.delete(f"{S}/{st['id']}", cookies=e.ck_a)
    with e.repo.session_factory() as s:
        assert "Blanket story" not in json.dumps(s.scalar(select(P.InterviewSession.state_payload)))


def test_strip_story_blocks_is_exact_and_idempotent():
    text = f"intro\n\n{STORY_BLOCK_OPEN.format(id=1)}one{STORY_BLOCK_CLOSE.format(id=1)}\n\n{STORY_BLOCK_OPEN.format(id=12)}twelve{STORY_BLOCK_CLOSE.format(id=12)}"
    once = strip_story_blocks(text, 1)
    assert "one" not in once and "twelve" in once and "intro" in once        # id 1 does not touch id 12
    assert strip_story_blocks(once, 1) == once and strip_story_blocks("", 1) == ""


# --- sharing consent ------------------------------------------------------------------------------------------------------------------------------------

def test_share_requires_explicit_grant_projection_is_bounded_and_archive_revokes():
    e = Env()
    wid = e.workspace_with_member()
    doc = e.doc()
    st = e.c.post(f"{S}/draft", json={"title": "Shared win", "claim_ids": [doc["claims"][0]["id"]], "opportunity_id": e.opportunity()}, cookies=e.ck_a).json()
    assert e.c.get(f"/api/v1/shares/resource/story/{st['id']}", cookies=e.ck_b).status_code == 404       # a workspace member sees nothing until shared
    assert e.c.post("/api/v1/shares", json={"workspace_id": wid, "resource_type": "story", "resource_id": str(st["id"])}, cookies=e.ck_b).status_code == 403
    assert e.share(wid, st["id"]).status_code == 200
    seen = e.c.get(f"/api/v1/shares/resource/story/{st['id']}", cookies=e.ck_b)
    assert seen.status_code == 200
    resource = seen.json()["resource"]
    assert resource["title"] == "Shared win" and resource["verification"] == "evidence_verified"
    for leaked in ("evidence_claim_ids", "evidence_answer_ids", "opportunity_id", "archived_at", "confirmed_at", "use_count", "last_used_at", "quality_prompts", "evidence_state"):
        assert leaked not in resource
    # archive revokes the grant at once; restore does NOT re-share; an archived story cannot be shared
    e.c.post(f"{S}/{st['id']}/archive", cookies=e.ck_a)
    assert e.c.get(f"/api/v1/shares/resource/story/{st['id']}", cookies=e.ck_b).status_code == 404
    assert e.c.get("/api/v1/shares/mine", cookies=e.ck_a).json()["shares"] == []
    assert e.share(wid, st["id"]).status_code == 403
    e.c.post(f"{S}/{st['id']}/restore", cookies=e.ck_a)
    assert e.c.get(f"/api/v1/shares/resource/story/{st['id']}", cookies=e.ck_b).status_code == 404       # consent is explicit every time
    assert e.share(wid, st["id"]).status_code == 200
    share_id = e.c.get("/api/v1/shares/mine", cookies=e.ck_a).json()["shares"][0]["id"]
    assert e.c.delete(f"/api/v1/shares/{share_id}", cookies=e.ck_b).status_code == 404                      # only the owner revokes
    assert e.c.delete(f"/api/v1/shares/{share_id}", cookies=e.ck_a).status_code == 200
    assert e.c.get(f"/api/v1/shares/resource/story/{st['id']}", cookies=e.ck_b).status_code == 404          # revocation is immediate


def test_outsider_and_platform_admin_get_no_shared_story_access():
    e = Env()
    wid = e.workspace_with_member()
    st = e.story()
    e.share(wid, st["id"])
    assert e.c.get(f"/api/v1/shares/resource/story/{st['id']}", cookies=e.ck_m).status_code == 404


# --- cross-user isolation and authentication on every route ------------------------------------------------------------------------------------------

def test_every_story_route_is_404_for_another_owner_and_401_without_a_session():
    e = Env()
    st = e.story()
    doc = e.doc()
    cid = doc["claims"][0]["id"]
    aid = e.answer_id(e.uid_a)
    e.c.post(f"{S}/{st['id']}/evidence", json={"kind": "claim", "ref_id": cid}, cookies=e.ck_a)
    b_doc = e.doc(ck=e.ck_b)
    b_claim = b_doc["claims"][0]["id"]
    b_answer = e.answer_id(e.uid_b)
    sid = st["id"]
    per_story = [
        ("GET", f"{S}/{sid}", None), ("PATCH", f"{S}/{sid}", {"title": "hijack"}), ("POST", f"{S}/{sid}/archive", None), ("POST", f"{S}/{sid}/restore", None),
        ("POST", f"{S}/{sid}/confirm", None), ("DELETE", f"{S}/{sid}/confirm", None),
        ("POST", f"{S}/{sid}/evidence", {"kind": "claim", "ref_id": b_claim}), ("POST", f"{S}/{sid}/evidence", {"kind": "answer", "ref_id": b_answer}),
        ("DELETE", f"{S}/{sid}/evidence/claim/{cid}", None), ("DELETE", f"{S}/{sid}/evidence/answer/{aid}", None), ("DELETE", f"{S}/{sid}", None),
    ]
    for method, path, body in per_story:
        r = e.c.request(method, path, json=body, cookies=e.ck_b)
        assert r.status_code == 404, (method, path, r.status_code, r.text)
    # the owner attaching ANOTHER account's claim or answer is also a plain 404 (and nothing is linked)
    assert e.c.post(f"{S}/{sid}/evidence", json={"kind": "claim", "ref_id": b_claim}, cookies=e.ck_a).status_code == 404
    assert e.c.post(f"{S}/{sid}/evidence", json={"kind": "answer", "ref_id": b_answer}, cookies=e.ck_a).status_code == 404
    assert e.c.post(f"{S}/draft", json={"title": "x", "claim_ids": [cid]}, cookies=e.ck_b).status_code == 422       # drafting from A's claim yields nothing
    # nothing of A's story was changed by any of that
    intact = e.c.get(f"{S}/{sid}", cookies=e.ck_a).json()
    assert intact["title"] == "Led a migration" and intact["archived_at"] is None and intact["evidence_claim_ids"] == [cid]
    # collection routes never include another account's data
    assert e.c.get(S, cookies=e.ck_b).json()["stories"] == []
    assert e.c.post(f"{S}/suggest", json={"terms": ["migration", "leadership"]}, cookies=e.ck_b).json()["suggestions"] == []
    # authentication is required on every method and path
    anon = [("GET", S, None), ("POST", S, {"title": "x"}), ("POST", f"{S}/draft", {"claim_ids": [1]}), ("POST", f"{S}/search", {}), ("GET", f"{S}/tags", None),
            ("GET", f"{S}/answer-sources", None), ("POST", f"{S}/suggest", {"terms": []})] + [(m, p, b) for m, p, b in per_story]
    # (development/test environments allow an anonymous developer identity by design; production is fail-closed, so probe a production app)
    prod_app, _repo, _mail = build_auth_app(env="production")
    with TestClient(prod_app) as pc:
        for method, path, body in anon:
            r = pc.request(method, path, json=body)
            assert r.status_code == 401, (method, path, r.status_code)


def test_story_routes_are_not_part_of_the_admin_surface():
    from src.api.admin_route_invariant import admin_routes

    paths = [r.path for r in admin_routes()]
    assert paths and not any("stories" in p or "/story" in p for p in paths)                                       # Platform Admin has no story route (no content browsing)


# --- metadata only: no story content in logs or audit -----------------------------------------------------------------------------------------------

def test_no_story_content_in_logs_or_audit(caplog):
    caplog.set_level(logging.DEBUG)
    e = _practice_env()
    st = e.story(title=SENTINEL, situation=SENTINEL, action=SENTINEL * 2, result=SENTINEL)
    e.c.post(f"{S}/search", json={"q": SENTINEL}, cookies=e.ck_a)
    e.c.post(f"{S}/suggest", json={"terms": [SENTINEL]}, cookies=e.ck_a)
    e.c.patch(f"{S}/{st['id']}", json={"result": SENTINEL + "x"}, cookies=e.ck_a)
    e.c.post(f"{S}/{st['id']}/confirm", cookies=e.ck_a)
    assert _create_practice(e, story_ids=[st["id"]], confirm_story_use=True).status_code == 200
    wid = e.workspace_with_member()
    e.share(wid, st["id"])
    e.c.post(f"{S}/{st['id']}/archive", cookies=e.ck_a)
    e.c.post(f"{S}/{st['id']}/restore", cookies=e.ck_a)
    e.c.delete(f"{S}/{st['id']}", cookies=e.ck_a)
    assert all(SENTINEL not in rec.getMessage() and SENTINEL not in str(rec.__dict__.get("args", "")) for rec in caplog.records)
    with e.repo.session_factory() as s:
        assert all(SENTINEL not in json.dumps(ev.context or {}) for ev in s.scalars(select(P.AuditEvent)).all())
        assert all(SENTINEL not in (ev.target_id or "") for ev in s.scalars(select(P.AuditEvent)).all())


# --- export and account deletion -----------------------------------------------------------------------------------------------------------------------

def test_export_carries_story_links_and_uses_for_the_owner_only_and_account_deletion_removes_all():
    from src.application.account_deletion_service import AccountDeletionService

    e = _practice_env()
    st = e.story(title="Exported story")
    doc = e.doc()
    e.c.post(f"{S}/{st['id']}/evidence", json={"kind": "claim", "ref_id": doc["claims"][0]["id"]}, cookies=e.ck_a)
    e.c.post(f"{S}/{st['id']}/evidence", json={"kind": "answer", "ref_id": e.answer_id(e.uid_a)}, cookies=e.ck_a)
    e.c.post(f"{S}/{st['id']}/archive", cookies=e.ck_a)
    e.c.post(f"{S}/{st['id']}/restore", cookies=e.ck_a)
    assert _create_practice(e, story_ids=[st["id"]], confirm_story_use=True).status_code == 200
    stories = e.c.get("/api/v1/auth/account/export", cookies=e.ck_a).json()["stories"]
    assert len(stories) == 1 and stories[0]["evidence_claim_ids"] and stories[0]["evidence_answer_ids"] and len(stories[0]["practice_uses"]) == 1
    assert e.c.get("/api/v1/auth/account/export", cookies=e.ck_b).json()["stories"] == []
    AccountDeletionService(e.repo.session_factory).delete_account(e.uid_a)
    with e.repo.session_factory() as s:
        for model in (P.CandidateStory, P.StoryEvidence, P.StoryAnswerLink, P.StoryUse):
            assert s.scalar(select(model)) is None, model


# --- migration 0041 -------------------------------------------------------------------------------------------------------------------------------------

def _alembic(tmp_path, monkeypatch):
    from tests.test_billing_f1_qualification import _alembic as make

    return make(tmp_path, monkeypatch)


def _story_rev():
    """(revision, its down_revision), found by its stable name so the lead can renumber and re-chain it at merge without editing these tests."""
    from tests._alembic_head import revisions

    found = [(rev, down) for rev, (down, _name) in revisions().items() if rev.endswith("_story_bank_completion")]
    assert len(found) == 1
    return found[0][0], found[0][1][0]


def test_migration_is_additive_chained_from_a_single_predecessor_and_single_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from tests._alembic_head import assert_chain, number, repository_head

    rev, prev = _story_rev()
    assert_chain(require=(prev, rev))
    assert number(rev) == number(prev) + 1                                                    # linear: it sits directly on its predecessor
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == [repository_head()]
    assert script.get_revision(rev).down_revision == prev


def test_migration_preserves_existing_stories_and_downgrade_is_fail_closed(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, text

    cfg, url = _alembic(tmp_path, monkeypatch)
    rev, prev = _story_rev()
    command.upgrade(cfg, prev)
    eng = create_engine(url)
    with eng.begin() as c:
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(candidate_stories)"))}
        assert not ({"archived_at", "confirmed_at", "opportunity_id"} & cols)
    command.upgrade(cfg, rev)
    with eng.begin() as c:
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(candidate_stories)"))}
        assert {"archived_at", "confirmed_at", "opportunity_id"} <= cols
        tables = {r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        assert {"story_answer_links", "story_uses"} <= tables
    # a clean downgrade removes only what this revision added, and re-upgrade works
    command.downgrade(cfg, prev)
    with eng.begin() as c:
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(candidate_stories)"))}
        assert not ({"archived_at", "confirmed_at", "opportunity_id"} & cols) and "title" in cols
    command.upgrade(cfg, rev)


def test_downgrade_refuses_while_candidate_authored_state_exists(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, text

    cfg, url = _alembic(tmp_path, monkeypatch)
    rev, prev = _story_rev()
    command.upgrade(cfg, rev)
    eng = create_engine(url)
    from sqlalchemy.orm import sessionmaker

    with sessionmaker(bind=eng)() as s:
        u = P.User(subject="d-subject", provider="dev", email="d@example.com")
        s.add(u)
        s.flush()
        st = P.CandidateStory(user_id=u.id, title="t", archived_at=P.utcnow())
        s.add(st)
        s.commit()
    with pytest.raises(Exception, match="Refusing to downgrade .*_story_bank_completion"):
        command.downgrade(cfg, prev)
    with eng.begin() as c:
        assert c.execute(text("SELECT COUNT(*) FROM candidate_stories")).scalar() == 1                 # nothing was deleted
        c.execute(text("UPDATE candidate_stories SET archived_at = NULL"))
    command.downgrade(cfg, prev)                                                                        # once reset, it proceeds


# --- the reviewed privacy-schema exception is exact -----------------------------------------------------------------------------------------------------

def test_privacy_schema_exception_is_exact(tmp_path):
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("eval_privacy_controls", root / "scripts/eval_privacy_controls.py")
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    known = set(P.Base.metadata.tables)
    assert ev.post_baseline_privacy_touches(root / "migrations/versions", known) == {}              # the real history, with this migration allowed
    real = next((root / "migrations/versions").glob("*_story_bank_completion.py")).read_text(encoding="utf-8")
    assert ev.migration_tables_touched(real, known) & ev.PRIVACY_TABLES <= ev.REVIEWED_PRIVACY_MIGRATIONS["_story_bank_completion.py"]

    counter = iter(range(100))

    def offenders(name, body):
        d = tmp_path / f"v{next(counter)}"
        d.mkdir()
        (d / name).write_text('"""x"""\nfrom alembic import op\n' + body, encoding="utf-8")
        return ev.post_baseline_privacy_touches(d, known)

    ok = 'def upgrade():\n    op.add_column("candidate_stories", None)\n'
    assert offenders("0099_story_bank_completion.py", ok) == {}                                      # renumbering keeps the exception
    assert offenders("0099_story_bank_completion.py", 'def upgrade():\n    op.drop_table("share_grants")\n') == {"0099_story_bank_completion.py": ["share_grants"]}
    assert offenders("0099_something_else.py", ok) == {"0099_something_else.py": ["candidate_stories"]}   # no other migration is exempt


# --- answer evidence sources never widen the history window -----------------------------------------------------------------------------------------

def test_answer_sources_list_question_text_only_owner_only_and_respect_the_history_window():
    e = Env()
    st = e.story()
    old_aid = e.answer_id(e.uid_a)
    new_aid = e.answer_id(e.uid_a)
    b_aid = e.answer_id(e.uid_b)
    src = e.c.get(f"{S}/answer-sources", cookies=e.ck_a).json()["sources"]
    assert {s["answer_id"] for s in src} == {old_aid, new_aid}                                  # never another account's
    assert all("My own answer" not in json.dumps(s) and s["question"] == "Tell me about a challenge." for s in src)
    assert e.c.get(f"{S}/answer-sources", cookies=e.ck_b).json()["sources"][0]["answer_id"] == b_aid

    class _Window:                                                                              # a Basic-style window of ONE interview
        def window_for(self, user_id):
            return 1

    e.app.dependency_overrides[deps.get_history_access_policy] = lambda: _Window()
    windowed = e.c.get(f"{S}/answer-sources", cookies=e.ck_a).json()["sources"]
    assert [s["answer_id"] for s in windowed] == [new_aid]
    assert e.c.post(f"{S}/{st['id']}/evidence", json={"kind": "answer", "ref_id": old_aid}, cookies=e.ck_a).status_code == 404   # outside the window = missing
    assert e.c.post(f"{S}/{st['id']}/evidence", json={"kind": "answer", "ref_id": new_aid}, cookies=e.ck_a).status_code == 200
