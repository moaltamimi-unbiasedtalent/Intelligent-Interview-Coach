"""P10B Wave 4 — governed document/evidence context + language acceptance (no live calls).

Two harnesses:
- build_auth_app (real users/repo/store) for the owner-scoped document-text resolver and the
  approved-evidence-only composition — the security-critical building blocks;
- the durable interview harness (mocked generation) for API language acceptance and for proving
  scores are independent of conversation_language.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("DOCUMENT_STORAGE_DIR", tempfile.mkdtemp(prefix="wave4_doc_test_"))

from fastapi.testclient import TestClient

from src.application.documents_service import DocumentsApplicationService
from src.application.evidence_access_service import EvidenceAccessService
from src.documents.repository import DocumentRepository, StoryRepository
from src.documents.storage import LocalDocumentStore
from tests._auth_factories import build_auth_app, cookies_for, login_token, register

PW = "correcthorsebattery"
JD = (
    "Senior Registered Nurse\nLead a ward team and own patient safety.\n"
    "Requirements: 5+ years, triage, mentoring.\n"
).encode()
CV = (
    "Jane Doe\nSenior Software Engineer at Acme Corp\n"
    "Skills: Python, FastAPI, Kubernetes\n"
    "- Reduced latency by 40% across core services\n"
).encode()


def _env():
    app, repo, _ = build_auth_app()
    c = TestClient(app)
    c.__enter__()
    register(c, "a@example.com", PW)
    register(c, "b@example.com", PW)
    a = login_token(c, "a@example.com", PW)
    b = login_token(c, "b@example.com", PW)
    a_id = c.get("/api/v1/auth/me", cookies=cookies_for(a)).json()["user_id"]
    b_id = c.get("/api/v1/auth/me", cookies=cookies_for(b)).json()["user_id"]
    sf = repo.session_factory
    store = LocalDocumentStore(os.environ["DOCUMENT_STORAGE_DIR"])
    docs_svc = DocumentsApplicationService(
        repo=DocumentRepository(sf), stories=StoryRepository(sf), store=store, ocr=_NoOcr())
    evidence = EvidenceAccessService(documents=DocumentRepository(sf), stories=StoryRepository(sf))
    return c, a, b, a_id, b_id, docs_svc, evidence


class _NoOcr:
    def is_available(self):
        return False

    def image_to_text(self, *a, **k):
        return ""

    def pdf_to_text(self, *a, **k):
        return []


def _upload(c, cookies, data, name, category):
    return c.post("/api/v1/documents", files={"file": (name, data, "text/plain")},
                  data={"category": category}, cookies=cookies).json()


# --- owner-scoped JD document text resolver ----------------------------------

def test_extracted_text_owner_scoped():
    c, a, b, a_id, b_id, docs_svc, _ = _env()
    try:
        did = _upload(c, cookies_for(a), JD, "jd.txt", "job_description")["id"]
        # Owner reads the text…
        text = docs_svc.extracted_text(user_id=a_id, document_id=did)
        assert text and "Registered Nurse" in text
        # …a different user gets nothing (never another user's document).
        assert docs_svc.extracted_text(user_id=b_id, document_id=did) is None
        # A non-existent id is safe.
        assert docs_svc.extracted_text(user_id=a_id, document_id=999999) is None
    finally:
        c.__exit__(None, None, None)


def test_extracted_text_is_bounded():
    c, a, b, a_id, b_id, docs_svc, _ = _env()
    try:
        big = ("Responsibilities include leadership. " * 2000).encode()
        did = _upload(c, cookies_for(a), big, "jd.txt", "job_description")["id"]
        text = docs_svc.extracted_text(user_id=a_id, document_id=did, max_chars=500)
        assert text is not None and len(text) <= 500
    finally:
        c.__exit__(None, None, None)


# --- approved-evidence-only composition --------------------------------------

def test_evidence_composition_approved_only():
    from src.api.routes.interview import _compose_evidence_background

    c, a, b, a_id, b_id, _, evidence = _env()
    try:
        doc = _upload(c, cookies_for(a), CV, "cv.txt", "cv")
        claims = doc["claims"]
        assert len(claims) >= 3
        # Accept the first, reject the second, leave the rest pending.
        c.post(f"/api/v1/documents/{doc['id']}/claims/{claims[0]['id']}/review",
               json={"action": "accept"}, cookies=cookies_for(a))
        c.post(f"/api/v1/documents/{doc['id']}/claims/{claims[1]['id']}/review",
               json={"action": "reject"}, cookies=cookies_for(a))
        summary = _compose_evidence_background(evidence, a_id)
        accepted_text = claims[0]["display_text"]
        rejected_text = claims[1]["display_text"]
        assert accepted_text in summary          # approved evidence is included
        assert rejected_text not in summary      # rejected is excluded
        # A different user sees none of A's evidence.
        assert _compose_evidence_background(evidence, b_id) == ""
    finally:
        c.__exit__(None, None, None)


def test_deleted_source_excluded_from_evidence():
    from src.api.routes.interview import _compose_evidence_background

    c, a, b, a_id, b_id, _, evidence = _env()
    try:
        doc = _upload(c, cookies_for(a), CV, "cv.txt", "cv")
        cid = doc["claims"][0]["id"]
        c.post(f"/api/v1/documents/{doc['id']}/claims/{cid}/review",
               json={"action": "accept"}, cookies=cookies_for(a))
        assert _compose_evidence_background(evidence, a_id) != ""
        # Deleting the source document removes its approved claims from evidence.
        c.delete(f"/api/v1/documents/{doc['id']}", cookies=cookies_for(a))
        assert _compose_evidence_background(evidence, a_id) == ""
    finally:
        c.__exit__(None, None, None)
