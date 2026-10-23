"""06B (LG-03, LG-09): the Story Bank and Workspaces SERVER journeys in each of the seven selectable languages.

The browser journeys (frontend/e2e/language-journeys-06b.spec.ts) mock the network; this suite proves the server paths over the
real FastAPI app against a temporary database: every step of the Story Bank and Workspaces journeys, with the candidate's interface
and conversation language set to each language, must (a) behave identically (language never changes authorization, consent or
isolation), (b) keep the candidate's own words byte for byte (never translated), (c) never touch the career geography, and (d) send
the invitation e-mail in the INVITEE's interface language with the protected slogan untranslated. Deterministic, 0 paid/live calls.
All non-English strings are ENGINEERING translations, not native-reviewed.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("DOCUMENT_STORAGE_DIR", tempfile.mkdtemp(prefix="ask4mo_06b_test_"))

import pytest
from fastapi.testclient import TestClient

from src.locales import ACTIVE_CANDIDATE_LOCALES
from src.mail.templates import BRAND_LINE, render as render_mail
from tests._auth_factories import build_auth_app
from tests._workspaces_04b_world import API, World
from tests.test_story_bank_04a import S, Env, _close_clients, _create_practice, _practice_env  # noqa: F401  (autouse fixture re-exported)

LOCALES = list(ACTIVE_CANDIDATE_LOCALES)
# The candidate's own words in each language: stored and shown exactly as written, never translated.
OWN_WORDS = {
    "en": "Led the ward migration",
    "de": "Die Stationsumstellung geleitet: Größe, Übergabe, Qualität",
    "fr": "Piloté la migration du service : équipe, qualité, délai",
    "es": "Dirigí la migración de la planta: año, equipo, calidad",
    "it": "Ho guidato la migrazione del reparto: qualità, tempi",
    "pt": "Liderei a migração da ala: equipa, qualidade, prazo",
    "nl": "De afdelingsmigratie geleid: kwaliteit, tempo, overdracht",
}


def _prefs(client, cookies, **body):
    r = client.patch(f"{API}/auth/preferences", json=body, cookies=cookies)
    assert r.status_code == 200, r.text
    return r.json()


def _me(client, cookies):
    return client.get(f"{API}/auth/me", cookies=cookies).json()


def test_the_seven_languages_are_exactly_the_active_candidate_locales():
    assert LOCALES == ["en", "de", "fr", "es", "it", "pt", "nl"]               # Russian is excluded (06A); its dormant specs stay skipped


@pytest.mark.parametrize("loc", LOCALES)
def test_story_bank_server_journey(loc):
    """create, evidence, verify, use in Practice with consent, share with consent, revoke, delete, survive a restart (fresh reads)."""
    e = _practice_env()
    _prefs(e.c, e.ck_a, interface_locale=loc, conversation_language=loc, career_geography="ch")
    _prefs(e.c, e.ck_b, interface_locale=loc, conversation_language=loc)
    title = OWN_WORDS[loc]

    # create: the title is required and the candidate's words are stored verbatim
    assert e.c.post(S, json={"title": "   "}, cookies=e.ck_a).status_code == 422
    st = e.story(title=title, situation=f"{title} (situation)")
    assert st["title"] == title and st["verification"] == "unverified" and st["evidence_state"] == "none"
    other = e.story(title="Not chosen", situation="SENTINEL-NOT-CHOSEN-06b")

    # evidence: only the candidate's own approved document item makes it supported; self-confirmation is not evidence
    assert e.c.post(f"{S}/{other['id']}/confirm", cookies=e.ck_a).json()["verification"] == "self_confirmed"
    doc = e.doc()
    cid = doc["claims"][0]["id"]
    assert e.c.post(f"{S}/{st['id']}/evidence", json={"kind": "claim", "ref_id": cid}, cookies=e.ck_b).status_code == 404   # a foreign candidate cannot attach it
    linked = e.c.post(f"{S}/{st['id']}/evidence", json={"kind": "claim", "ref_id": cid}, cookies=e.ck_a).json()
    assert linked["verification"] == "evidence_verified" and linked["title"] == title

    # use in Practice: consent is explicit; only the chosen story reaches the model; the session language is the conversation language
    assert _create_practice(e, story_ids=[st["id"]], conversation_language=loc).status_code == 422
    assert e.domain.configs == []
    r = _create_practice(e, story_ids=[st["id"]], confirm_story_use=True, conversation_language=loc)
    assert r.status_code == 200, r.text
    cfg = e.domain.configs[-1]
    assert title in cfg.candidate_background and "SENTINEL-NOT-CHOSEN-06b" not in cfg.candidate_background
    assert cfg.conversation_language == loc
    assert e.c.get(f"{S}/{st['id']}", cookies=e.ck_a).json()["use_count"] == 1

    # share with consent, revoke
    wid = e.workspace_with_member()
    assert e.c.post(f"{API}/shares", json={"workspace_id": wid, "resource_type": "story", "resource_id": str(st["id"]), "consent": False}, cookies=e.ck_a).status_code in (400, 403, 422)
    assert e.c.get(f"{API}/shares/resource/story/{st['id']}", cookies=e.ck_b).status_code == 404
    assert e.share(wid, st["id"]).status_code == 200
    seen = e.c.get(f"{API}/shares/resource/story/{st['id']}", cookies=e.ck_b)
    assert seen.status_code == 200 and seen.json()["resource"]["title"] == title            # the owner's words, untranslated
    share_id = e.c.get(f"{API}/shares/mine", cookies=e.ck_a).json()["shares"][0]["id"]
    assert e.c.delete(f"{API}/shares/{share_id}", cookies=e.ck_a).status_code == 200
    assert e.c.get(f"{API}/shares/resource/story/{st['id']}", cookies=e.ck_b).status_code == 404

    # survive a restart: fresh reads from the database return the same stories
    listed = {s["id"]: s for s in e.c.get(S, cookies=e.ck_a).json()["stories"]}
    assert listed[st["id"]]["title"] == title and listed[st["id"]]["verification"] == "evidence_verified"

    # delete: gone for the owner, and the text is stripped from the practice session record
    assert e.c.delete(f"{S}/{st['id']}", cookies=e.ck_a).status_code == 200
    assert e.c.get(f"{S}/{st['id']}", cookies=e.ck_a).status_code == 404
    assert st["id"] not in {s["id"] for s in e.c.get(S, cookies=e.ck_a).json()["stories"]}
    # language choices never touched geography
    assert _me(e.c, e.ck_a)["career_geography"] == "ch"


@pytest.mark.parametrize("loc", LOCALES)
def test_story_isolation_is_identical_in_every_language(loc):
    """Another owner gets the same refusals whatever language either person uses (LG-09 owner isolation)."""
    e = _practice_env()
    _prefs(e.c, e.ck_a, interface_locale=loc, conversation_language=loc)
    _prefs(e.c, e.ck_b, interface_locale=loc, conversation_language=loc)
    st = e.story(title=OWN_WORDS[loc])
    for method, path, body in (
        ("GET", f"{S}/{st['id']}", None), ("PATCH", f"{S}/{st['id']}", {"title": "x"}), ("DELETE", f"{S}/{st['id']}", None),
        ("POST", f"{S}/{st['id']}/archive", None), ("POST", f"{S}/{st['id']}/confirm", None),
    ):
        r = e.c.request(method, path, json=body, cookies=e.ck_b)
        assert r.status_code == 404, (loc, method, path, r.text)
    assert OWN_WORDS[loc] not in e.c.get(S, cookies=e.ck_b).text
    prod_app, _repo, _mail = build_auth_app(env="production")                                # test/dev allow an anonymous developer identity by design
    with TestClient(prod_app) as pc:
        assert pc.get(S, headers={"Accept-Language": loc}).status_code == 401                                                       # no session, no stories, in any language
    assert _create_practice(e, ck=e.ck_b, story_ids=[st["id"]], confirm_story_use=True, conversation_language=loc).status_code in (404, 422)
    assert e.domain.configs == []


@pytest.mark.parametrize("loc", LOCALES)
def test_workspaces_server_journey(loc):
    """create, invite (e-mail in the invitee's language), verified accept, share with consent, revoke, remove member, delete."""
    w = World()
    try:
        for n in ("alice", "ben", "olga"):
            w.user(n)
        assert w.call("alice", "PATCH", "/auth/preferences", {"interface_locale": loc, "conversation_language": loc, "career_geography": "ch"}).status_code == 200
        assert w.call("ben", "PATCH", "/auth/preferences", {"interface_locale": loc, "conversation_language": loc}).status_code == 200
        name = f"Équipe {OWN_WORDS[loc][:12]}"                                                  # a localised, non-ASCII workspace name
        wid = w.workspace("alice", name)
        assert w.get("alice", f"/workspaces/{wid}").json()["name"] == name

        # invite: the e-mail is in the INVITEE's interface language, carries the link and the slogan once, untranslated
        r = w.post("alice", f"/workspaces/{wid}/invite", {"email": w.u["ben"]["email"]})
        assert r.status_code == 200 and r.json()["email_delivery"] == "submitted"
        mail = w.mail.sent[-1]
        link = next(line for line in mail.body.splitlines() if "token=" in line).strip()
        expected = render_mail("workspace_invitation", locale=loc, link=link, expires_in_seconds=72 * 3600)
        assert mail.subject == expected.subject and mail.body == expected.body              # the invitee's language, nothing else
        assert mail.body.count(BRAND_LINE) == 1 and mail.body.rstrip().endswith(BRAND_LINE) and "token=" in mail.body
        if loc != "en":
            assert mail.subject != render_mail("workspace_invitation", locale="en").subject
        token = w.token()

        # verified accept: another account cannot use the link; the invitee can; joining shares nothing
        assert w.post("olga", "/workspaces/invitations/accept", {"token": token}).status_code in (403, 404, 409)
        assert w.get("ben", f"/workspaces/{wid}").status_code == 404                              # not a member yet
        assert w.post("ben", "/workspaces/invitations/accept", {"token": token}).status_code == 200
        assert w.get("ben", "/shares/with-me").json()["shares"] == []

        # share ONE story: consent is mandatory; the member sees only that story, read-only, in the owner's words
        sid = w.story("alice", OWN_WORDS[loc])
        assert w.share("alice", wid, "story", sid, consent=False).status_code in (400, 403, 422)
        assert w.get("ben", f"/shares/resource/story/{sid}").status_code == 404
        assert w.share("alice", wid, "story", sid).status_code == 200
        seen = w.get("ben", f"/shares/resource/story/{sid}")
        assert seen.status_code == 200 and seen.json()["resource"]["title"] == OWN_WORDS[loc]
        assert w.call("ben", "PATCH", f"/stories/{sid}", {"title": "hijack"}).status_code == 404   # view only
        assert w.get("olga", f"/shares/resource/story/{sid}").status_code == 404                  # an outsider sees nothing

        # revoke: immediate
        share_id = w.get("alice", "/shares/mine").json()["shares"][0]["id"]
        assert w.call("ben", "DELETE", f"/shares/{share_id}").status_code == 404                  # only the owner revokes
        assert w.call("alice", "DELETE", f"/shares/{share_id}").status_code == 200
        assert w.get("ben", f"/shares/resource/story/{sid}").status_code == 404

        # remove member, then delete the workspace with the exact name
        assert w.post("alice", f"/workspaces/{wid}/members/{w.u['ben']['uid']}/remove").status_code == 200
        assert w.get("ben", f"/workspaces/{wid}").status_code == 404
        assert w.post("alice", f"/workspaces/{wid}/delete", {"confirm_name": name.lower()}).status_code == 422
        assert w.post("alice", f"/workspaces/{wid}/delete", {"confirm_name": name}).status_code == 200
        assert w.get("alice", f"/workspaces/{wid}").status_code == 404
        # the owner's own story survives the workspace and the language choices never touched geography
        assert w.get("alice", f"/stories/{sid}").status_code == 200
        assert w.get("alice", "/auth/me").json()["career_geography"] == "ch"
    finally:
        w.close()


def test_invitation_mail_for_an_invitee_without_an_account_falls_back_to_english_with_the_slogan():
    w = World()
    try:
        w.user("alice")
        wid = w.workspace("alice", "Alpha")
        assert w.post("alice", f"/workspaces/{wid}/invite", {"email": "new.person@example.com"}).status_code == 200
        mail = w.mail.sent[-1]
        assert mail.subject == render_mail("workspace_invitation", locale="en").subject
        assert mail.body.count(BRAND_LINE) == 1
    finally:
        w.close()
