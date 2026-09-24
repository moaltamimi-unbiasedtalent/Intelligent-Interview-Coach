"""Document pipeline units (Capstone P4/E2): validation, parsing, extraction, storage, OCR routing."""

from __future__ import annotations

import tempfile

import pytest

from src.documents.extraction import extract_claims
from src.documents.ocr import OcrError, ocr_parse
from src.documents.parsing import ParseResult, Segment, needs_ocr, parse_document
from src.documents.storage import LocalDocumentStore, new_storage_key
from src.documents.validation import DocumentValidationError, sanitise_filename, validate_upload

CV = (
    "Jane Doe\nSenior Software Engineer at Acme Corp\n"
    "Skills: Python, FastAPI, Kubernetes\n"
    "- Reduced latency by 40% across core services\n"
    "MSc Computer Science, University of Example\n"
).encode()


# --- validation --------------------------------------------------------------

def test_validate_txt_ok():
    v = validate_upload("cv.txt", CV)
    assert v.extension == "txt" and v.mime_type == "text/plain" and not v.is_image


def test_reject_unsupported_type():
    with pytest.raises(DocumentValidationError):
        validate_upload("x.exe", b"MZ\x00")


def test_reject_oversized():
    with pytest.raises(DocumentValidationError):
        validate_upload("big.txt", b"x" * (11 * 1024 * 1024))


def test_reject_mime_spoof_pdf():
    with pytest.raises(DocumentValidationError):
        validate_upload("evil.pdf", b"this is not a pdf")


def test_reject_empty():
    with pytest.raises(DocumentValidationError):
        validate_upload("cv.txt", b"")


def test_filename_sanitisation_strips_paths_and_control():
    assert sanitise_filename("../../etc/passwd") == "passwd"
    assert "/" not in sanitise_filename("a/b/c.pdf")
    assert sanitise_filename("") == "document"


# --- parsing + extraction ----------------------------------------------------

def test_parse_txt_provenance_and_extract():
    parse = parse_document(CV, "txt")
    assert parse.has_text and not needs_ocr("txt", parse)
    claims = extract_claims(parse, category="cv")
    types = {c.claim_type for c in claims}
    assert {"skill", "experience", "achievement", "education"} <= types
    # every claim carries provenance and verbatim text (no invention)
    for c in claims:
        assert c.section or c.page is not None
        assert c.text in CV.decode()  # verbatim substring


def test_pdf_text_extraction_with_page_provenance():
    fpdf = pytest.importorskip("fpdf")
    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, "Senior Data Analyst at Globex\nSkills: SQL, Python\nDelivered 25% cost reduction")
    data = bytes(pdf.output())
    parse = parse_document(data, "pdf")
    assert parse.has_text and parse.page_count == 1
    assert all(s.page == 1 for s in parse.segments)
    claims = extract_claims(parse, category="cv")
    assert any(c.claim_type == "achievement" and c.page == 1 for c in claims)


def test_corrupt_pdf_fails_safely():
    from src.documents.parsing import ParseError

    with pytest.raises(ParseError):
        parse_document(b"%PDF-1.4 broken garbage not a real pdf", "pdf")


def test_needs_ocr_routing():
    empty = ParseResult(segments=[], page_count=1)
    assert needs_ocr("pdf", empty) is True   # scanned PDF (no text)
    assert needs_ocr("png", empty) is True   # image always OCR
    withtext = ParseResult(segments=[Segment(text="hello", page=1)])
    assert needs_ocr("pdf", withtext) is False


# --- storage -----------------------------------------------------------------

def test_storage_roundtrip_and_delete():
    store = LocalDocumentStore(tempfile.mkdtemp())
    key = new_storage_key()
    store.save(key, CV)
    assert store.exists(key) and store.read(key) == CV
    assert store.delete(key) and not store.exists(key)


def test_storage_rejects_path_traversal():
    store = LocalDocumentStore(tempfile.mkdtemp())
    with pytest.raises(ValueError):
        store.read("../../etc/passwd")
    assert store.exists("../../etc/passwd") is False


# --- OCR abstraction ---------------------------------------------------------

class _FakeOcr:
    def is_available(self):
        return True

    def image_to_text(self, image_bytes, *, lang="en"):
        return "Recognised scanned text: Project Lead"

    def pdf_to_text(self, pdf_bytes, *, lang="en"):
        from src.documents.ocr import OcrResult

        return [OcrResult(text="Scanned page one text", page=1)]


def test_ocr_parse_labels_origin_and_page():
    parse = ocr_parse(_FakeOcr(), b"\x89PNG...", "png", lang="de")
    assert parse.origin == "ocr" and parse.segments[0].page == 1
    assert "Project Lead" in parse.full_text


def test_ocr_unavailable_raises_safely():
    class _NoOcr:
        def is_available(self):
            return False
        def image_to_text(self, *a, **k):
            return ""
        def pdf_to_text(self, *a, **k):
            return []

    with pytest.raises(OcrError):
        ocr_parse(_NoOcr(), b"x", "png")
