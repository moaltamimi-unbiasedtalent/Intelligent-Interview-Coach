"""INTEGRATED CANDIDATE / ADMIN / OPERATIONS REQUALIFICATION: cross-domain negative scenarios (real HTTP on a temp database, deterministic doubles, no provider, no network, 0 paid calls).

Complements tests/test_integrated_w11.py (cross-plane seams) and the per-domain suites; the requalification report maps every scenario to the test that proves it. Nothing here asserts a quality
or production-readiness claim."""

from __future__ import annotations

import httpx
import pytest

from src.copilot.rag import localized
from tests.test_integrated_w11 import API, W, denied, rich_candidate

CANADA_Q = "What does a Data Analyst earn in Canada?"


def _block_external_network(monkeypatch):
    """The in-process TestClient also uses httpx; only a request to a real host is a violation."""
    real_sync, real_async = httpx.Client.send, httpx.AsyncClient.send

    def guard(request):
        if (request.url.host or "") != "testserver":
            raise AssertionError(f"an external network request was attempted: {request.url.host}")

    def sync(self, request, **k):
        guard(request)
        return real_sync(self, request, **k)

    async def asynch(self, request, **k):
        guard(request)
        return await real_async(self, request, **k)

    monkeypatch.setattr(httpx.Client, "send", sync)
    monkeypatch.setattr(httpx.AsyncClient, "send", asynch)


@pytest.fixture()
def w():
    x = W()
    yield x
    x.close()


# ------------------------------------------------------------------------------------------------------------------------- candidate isolation and authentication
def test_candidate_a_cannot_read_or_mutate_candidate_b_resources(w):
    a = rich_candidate(w, "a-int@x.com")
    b = rich_candidate(w, "b-int@x.com")
    for path in (f"/opportunities/{a['opp']}", f"/documents/{a['doc']}", f"/memory/{a['mem']}"):
        r = w.get(path, b["ck"])
        assert r.status_code in (404, 405), (path, r.status_code)                 # foreign ids look like missing ids (never 200, never 403 that confirms existence)
    assert w.c.delete(f"{API}/opportunities/{a['opp']}", cookies=b["ck"]).status_code == 404
    assert w.get(f"/opportunities/{a['opp']}", a["ck"]).status_code == 200      # the owner is unaffected


def test_expired_or_forged_authentication_is_rejected_in_production_style_requests(w):
    uid, ck, _e, token = w.user("user", "expiry-int@x.com")
    assert w.get("/auth/me", ck).status_code == 200
    assert w.get("/auth/me", {"ask4mo_session": token + "x"}).status_code == 401           # forged
    w.c.post(f"{API}/auth/logout", cookies=ck)
    assert w.get("/auth/me", ck).status_code == 401                                            # a revoked or expired session is never accepted
    with w.sf() as s:
        from sqlalchemy import text

        s.execute(text("UPDATE auth_sessions SET expires_at = '2000-01-01 00:00:00'"))
        s.commit()
    assert w.get("/auth/me", ck).status_code == 401


# ------------------------------------------------------------------------------------------------------------------------- admin boundaries
def test_a_candidate_and_a_least_privilege_role_cannot_reach_restricted_admin_operations(w):
    _, cand, _e, _t = w.user("user", "plain-int@x.com")
    for path in ("/admin/readiness", "/admin/speech"):
        assert denied(w.get(path, cand)), path                                                    # an ordinary candidate gets the fixed administrator-required refusal
    support = w.ck("support_operator")
    assert denied(w.get("/admin/speech", support)) or w.get("/admin/speech", support).status_code == 403   # a support operator holds no speech-governance permission
    assert w.post("/admin/step-up", cand, {"password": "x"}).status_code in (401, 403)


# ------------------------------------------------------------------------------------------------------------------------- commercial and speech stay disabled
def test_a_disabled_commercial_feature_cannot_start_a_real_payment_and_no_provider_is_contacted(w, monkeypatch):
    _block_external_network(monkeypatch)
    from src.billing import policy

    assert policy.LIVE_BILLING_ENABLED is False and policy.EXTERNAL_CHECKOUT_AUTHORIZED is False
    _, ck, _e, _t = w.user("user", "pay-int@x.com")
    r = w.post("/billing/checkout-sessions", ck, {"plan": "premium"})
    assert r.status_code in (400, 403, 404, 409, 422, 503), r.text                              # refused: never a redirect to a payment provider
    assert "checkout.stripe.com" not in r.text and "url" not in (r.json() if r.headers.get("content-type", "").startswith("application/json") else {})


def test_speech_provider_authorization_stays_disabled_and_the_candidate_surface_reflects_it(w):
    from src.speech import policy

    assert policy.SERVER_SPEECH_PROVIDERS_AUTHORIZED is False and policy.WHISPER_API_TRANSPORT_AUTHORIZED is False
    assert policy.MODEL_DOWNLOADS_AUTHORIZED is False and policy.VOICE_CLONING_ENABLED is False
    _, ck, _e, _t = w.user("user", "speech-int@x.com")
    body = w.get("/speech/capabilities", ck).json()
    assert body["server_stt_languages"] == [] and body["server_tts_languages"] == []             # no server speech language is offered while authorization is disabled
    assert "ru" in body["excluded_languages"] and "ru" not in body["product_languages"] and body["audio_persisted"] is False


# ------------------------------------------------------------------------------------------------------------------------- grounding policies through the real service path
def _answer(reply_text, query=CANADA_Q, language="en"):
    from src.copilot.knowledge import requalification as Q
    from src.copilot.rag.responder import ModelReply

    with Q.temp_world(Q.load_corpus()) as world:
        return world.service(responder=lambda m: ModelReply(content=reply_text)).answer(query, conversation_language=language)


def test_a_fabricated_citation_and_an_unsupported_canadian_salary_cannot_survive_the_career_path():
    res = _answer("A Data Analyst in Canada earns CAD 90,000 per year [1]. See also [42].")
    text = res.response.answer
    assert "90,000" not in text and "[42]" not in text
    assert {c.marker for c in res.response.citations} <= {f"[{i}]" for i in range(1, len(res.response.evidence) + 1)}
    assert res.trace.response_class in ("ABSTENTION_WITHOUT_CITATIONS", "ABSTENTION_WITH_CONTEXTUAL_CITATIONS")


@pytest.mark.parametrize("lang", ["en", "de", "fr", "es", "it", "pt", "nl"])
def test_an_unsourced_estimate_offer_is_replaced_by_localized_guidance_through_the_career_path(lang):
    from src.p10e import policy_evals as PE

    c = PE.load_contract()["unsourced_estimate_offers"]
    reply = localized.insufficient_message(lang) + " " + c["scripted_answers"][lang][1]
    res = _answer(reply, query=c["query_by_language"][lang], language=lang)
    from src.copilot.security import grounding_policy as GP

    assert not any(GP.offers_unsourced_estimate(s) for _, s in GP._units(res.response.answer))
    assert localized.compensation_guidance(lang) in res.response.answer and not GP.money_figures(res.response.answer)


def test_a_failing_provider_degrades_safely_without_leaking_credentials_or_prompts():
    from src.copilot.knowledge import requalification as Q

    secret = "sk-or-v1-SENTINEL-DO-NOT-LEAK-000000000000"

    def broken(messages):
        raise RuntimeError(f"upstream failure with key {secret} and prompt {messages[0]['content'][:40]}")

    with Q.temp_world(Q.load_corpus()) as world:
        res = world.service(responder=broken).answer("What does a Data Analyst do?", conversation_language="de")
    dump = repr(res.response.answer) + repr(res.trace.notes) + repr(res.trace.degraded) + repr(res.trace.output_findings)
    assert secret not in dump and "You are the Career Intelligence Copilot" not in dump
    assert "model" in res.trace.degraded and res.response.answer.strip()


def test_malformed_or_empty_provider_replies_never_produce_a_blank_or_unverified_answer():
    for reply in ("", "   ", "[1][2][3][4][5][6][7][8][9]"):
        res = _answer(reply)
        assert res.response.answer.strip()
        assert all(c.marker in res.response.answer for c in res.response.citations)


# ------------------------------------------------------------------------------------------------------------------------- operations
def test_operations_single_alembic_head_and_no_unexpected_gate_is_true():
    import re
    from pathlib import Path

    versions = Path(__file__).resolve().parents[1] / "migrations" / "versions"
    revs, downs = set(), set()
    for f in versions.glob("*.py"):
        t = f.read_text()
        m = re.search(r"^revision(?:: str)?\s*=\s*['\"]([^'\"]+)['\"]", t, re.M)
        d = re.search(r"^down_revision(?:[^=]*)=\s*(.+)$", t, re.M)
        if m:
            revs.add(m.group(1))
        if d:
            downs.update(re.findall(r"['\"]([^'\"]+)['\"]", d.group(1)))
    assert len(revs - downs) == 1


def test_no_test_workflow_can_emit_a_real_customer_notification(w, monkeypatch):
    _block_external_network(monkeypatch)
    from src.mail import MemoryEmailSender

    uid, ck, email, _t = w.user("user", "mail-int@x.com")
    assert isinstance(w.mail, MemoryEmailSender) and w.mail.sent                                 # captured in memory only (registration mail)


def test_the_export_legal_acceptance_claim_is_derived_from_real_records(w):
    from src.privacy.legal import LegalService

    uid, ck, _e, _t = w.user("user", "export-int@x.com")
    before = w.get("/auth/account/export", ck).json()
    assert before["legal_acceptance"] == {"recorded": False}                                       # no record: never fabricated
    assert not any("does not record it yet" in n for n in before["scope"]["not_included"])
    LegalService(w.sf).accept(uid, "terms")
    after = w.get("/auth/account/export", ck).json()
    assert after["legal_acceptance"] == {"recorded": True} and after["legal_acceptances"][0]["document"] == "terms"
