"""Company Intelligence API + service (P10B Wave 5).

Deterministic (0 paid/live calls): the happy path injects the offline fixture provider; the SSRF /
degradation path uses the REAL research service with a private-IP website, which the engine rejects
BEFORE any fetch (no network). Covers identity disambiguation, FACT/REVIEW/MODEL_INFERENCE
separation, provenance, provider status honesty, JD owner-scoping (own/foreign/deleted), gating,
and no-secret / no-fabrication invariants.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("DOCUMENT_STORAGE_DIR", tempfile.mkdtemp(prefix="ask4mo_company_test_"))

import pytest
from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.application.company_intelligence_service import (
    ClaimKind,
    CompanyIntelligenceQuery,
    CompanyIntelligenceService,
    IdentityConfidence,
    ProviderState,
    ReportStatus,
)
from src.copilot.research.fake_provider import FakeCompanyResearchProvider
from src.copilot.research.service import ExternalResearchService
from tests._auth_factories import build_auth_app, cookies_for, login_token, register

PW = "correcthorsebattery"


def _fake_service() -> ExternalResearchService:
    return ExternalResearchService([FakeCompanyResearchProvider()], enabled=True)


def _client(research_service: ExternalResearchService | None = None):
    app, repo, _mail = build_auth_app()
    app.dependency_overrides[deps.get_research_service] = lambda: (research_service or _fake_service())
    c = TestClient(app)
    c.__enter__()
    register(c, "a@example.com", PW)
    register(c, "b@example.com", PW)
    a = login_token(c, "a@example.com", PW)
    b = login_token(c, "b@example.com", PW)
    return c, a, b


def _post(c, cookies, **body):
    return c.post("/api/v1/research/company", json=body, cookies=cookies)


# --------------------------------------------------------------------------- service unit


def test_service_confirmed_identity_separates_fact_and_inference():
    svc = CompanyIntelligenceService(_fake_service(), adzuna_configured=False)
    r = svc.research(
        CompanyIntelligenceQuery(company_name="Acme", location="Berlin", website="acme.example",
                                 target_role="Engineer"),
        user_id=1,
    )
    assert r.identity.confidence is IdentityConfidence.CONFIRMED
    assert r.identity.domain == "acme.example"
    assert r.business_market, "expected FACT claims from the company web fixture"
    assert all(c.kind is ClaimKind.FACT for c in r.business_market)
    assert all(c.kind is ClaimKind.MODEL_INFERENCE for c in r.interview_preparation.topics)
    assert all(c.kind is ClaimKind.MODEL_INFERENCE for c in r.role_relevance)
    # Every FACT with a source id points at a real retrieved source (no fabricated citations).
    ids = {s.id for s in r.sources}
    for claim in r.business_market:
        assert all(sid in ids for sid in claim.source_ids)
    # Provenance + freshness present.
    assert r.sources and all(s.retrieved_at for s in r.sources)


def test_name_only_requests_clarification_and_fabricates_nothing():
    svc = CompanyIntelligenceService(_fake_service(), adzuna_configured=False)
    r = svc.research(CompanyIntelligenceQuery(company_name="Acme", location="Berlin"), user_id=1)
    assert r.status is ReportStatus.NEEDS_CLARIFICATION
    assert r.identity.confidence is IdentityConfidence.NEEDS_CLARIFICATION
    assert r.business_market == [] and r.sources == []
    web = next(p for p in r.provider_statuses if p.key == "company_web")
    assert web.state is ProviderState.UNAVAILABLE


def test_review_providers_reported_not_integrated_with_link_only():
    svc = CompanyIntelligenceService(_fake_service(), adzuna_configured=False)
    r = svc.research(CompanyIntelligenceQuery(company_name="Acme", website="acme.example"), user_id=1)
    assert r.review_signals == []          # no REVIEW claims are ever fabricated in Wave 5
    for key in ("glassdoor", "kununu", "google"):
        p = next(s for s in r.provider_statuses if s.key == key)
        assert p.state is ProviderState.NOT_INTEGRATED
        assert p.external_url and p.external_url.startswith("https://")
    assert "reviews_not_integrated" in r.limitations


def test_ssrf_private_website_degrades_without_fetch_or_fabrication():
    # REAL service (no creds → Adzuna unavailable, no network). A private-IP website is rejected by
    # the engine's validate_url BEFORE any fetch, so we get an honest unavailable result, 0 network.
    from src.copilot.research.service import ExternalResearchService as _R
    real = _R.default(enabled=True)
    svc = CompanyIntelligenceService(real, adzuna_configured=False)
    r = svc.research(
        CompanyIntelligenceQuery(company_name="Acme", website="http://127.0.0.1/admin"),
        user_id=1,
    )
    # Website normalised to https and passed on; the SSRF guard yields no evidence (no fabrication).
    assert r.business_market == []
    assert r.status in (ReportStatus.INSUFFICIENT_EVIDENCE, ReportStatus.UNAVAILABLE)


def test_no_secret_or_credential_appears_in_report():
    svc = CompanyIntelligenceService(_fake_service(), adzuna_configured=True)
    r = svc.research(CompanyIntelligenceQuery(company_name="Acme", website="acme.example",
                                              target_role="Engineer"), user_id=1)
    blob = r.model_dump_json().lower()
    for secret in ("app_key", "app_id", "api.adzuna.com/v1", "password", "authorization"):
        assert secret not in blob


# --------------------------------------------------------------------------- JD owner-scoping (service)


def test_jd_linked_only_when_resolver_returns_owner_text():
    """The service links a JD only when the owner-scoped resolver yields text. A foreign/deleted
    document yields None (resolver returns None) and is never linked or disclosed. The resolver's
    owner-scoping itself is the shared Wave 4 helper (tested in the documents suite)."""
    jd_text = "Senior Platform Engineer. Strong Kubernetes and observability experience required."

    # Owner: resolver returns text → linked, and keywords steer the inference.
    own = CompanyIntelligenceService(_fake_service(), resolve_jd=lambda _id: jd_text)
    r_own = own.research(CompanyIntelligenceQuery(
        company_name="Acme", website="acme.example", target_role="Engineer",
        job_description_document_id=7), user_id=1)
    assert r_own.jd_linked is True
    inf = " ".join(c.text.lower() for c in r_own.role_relevance)
    assert "kubernetes" in inf or "observability" in inf

    # Foreign/deleted: resolver returns None → not linked, no JD-derived inference.
    foreign = CompanyIntelligenceService(_fake_service(), resolve_jd=lambda _id: None)
    r_foreign = foreign.research(CompanyIntelligenceQuery(
        company_name="Acme", website="acme.example", target_role="Engineer",
        job_description_document_id=7), user_id=2)
    assert r_foreign.jd_linked is False
    assert "kubernetes" not in " ".join(c.text.lower() for c in r_foreign.role_relevance)


def test_endpoint_invokes_resolver_with_authenticated_user_id():
    """Wiring: the route resolves the JD with the caller's authenticated user id and the requested
    document id (owner scoping is enforced inside the shared resolver)."""
    from src.api.routes import company as company_route

    captured: dict = {}

    def _fake_resolve(request, *, user_id, document_id, max_chars=8000):
        captured["user_id"] = user_id
        captured["document_id"] = document_id
        return "Kubernetes platform role"

    c, a, _b = _client()
    orig = company_route.resolve_document_text
    company_route.resolve_document_text = _fake_resolve
    try:
        res = _post(c, cookies_for(a), company_name="Acme", website="acme.example",
                    job_description_document_id=42)
    finally:
        company_route.resolve_document_text = orig
    assert res.status_code == 200, res.text
    assert res.json()["jd_linked"] is True
    assert captured["document_id"] == 42
    assert isinstance(captured["user_id"], int) and captured["user_id"] >= 1


# --------------------------------------------------------------------------- API


def test_endpoint_returns_report_for_authenticated_user():
    c, a, _b = _client()
    res = _post(c, cookies_for(a), company_name="Acme", website="acme.example", target_role="Engineer")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["identity"]["confidence"] == "confirmed"
    assert body["business_market"] and body["sources"]
    assert body["status"] in ("ready", "partial")


def test_paused_capability_returns_truthful_503():
    from src.application.pause import get_pause_registry, reset_pause_registry

    c, a, _b = _client()
    get_pause_registry().set("current_market", True)
    try:
        res = _post(c, cookies_for(a), company_name="Acme", website="acme.example")
        assert res.status_code == 503
        assert "paused" in res.text.lower()          # safe error envelope, no raw provider detail
    finally:
        reset_pause_registry()


def test_capabilities_exposes_company_research_flag():
    c, _a, _b = _client()
    caps = c.get("/api/v1/capabilities").json()
    assert caps["company_research_enabled"] is True


@pytest.mark.parametrize("bad", [{"company_name": ""}, {"company_name": "x", "country": "DEU"}])
def test_rejects_malformed_requests(bad):
    c, a, _b = _client()
    assert _post(c, cookies_for(a), **bad).status_code == 422
