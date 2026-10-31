"""03E2 (PR 2): governed PDF export of the Admin report builder. Offline and deterministic: temp DB, no provider, no network, no browser.

Load-bearing properties: the PDF carries exactly the rows (figures, states, suppression) the CSV and JSON exports carry; it has the same authorization and commercial gating
as the other formats; it is audited before anything is sent and nothing is sent when the audit write fails; it is bounded; text from the data can never inject PDF syntax;
the file contains no active content and no external resource; the same input gives the same bytes."""

from __future__ import annotations

import csv
import io
import json
import re
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from pypdf import PdfReader
from pypdf.generic import ContentStream, DictionaryObject, IndirectObject
from sqlalchemy import func, select

from src.application import admin_permissions as perm
from src.persistence import AuditEvent
from src.reporting import report_builder as RB
from src.reporting import report_pdf as PDF
from tests import _admin_matrix as M
from tests.test_report_builder_03e1 import (
    API, CAPI, DENIED, PW, World, _assert_audit_failure_response, create_saved, definition_dict, export, seed,
)  # noqa: F401  (World and seed back the fixtures below)


@pytest.fixture(scope="module")
def world():
    w = World()
    w.seeded = seed(w)
    yield w
    w.close()


# ------------------------------------------------------------------------------------------------------------------------------ helpers
def read(data: bytes) -> PdfReader:
    return PdfReader(io.BytesIO(data), strict=True)


def placements(data: bytes) -> list[tuple[int, int, str]]:
    """Every text-show operator of the PDF as (x, y, text), in content order, across pages, read from the parsed content stream (so the escapes are decoded by pypdf's own parser)."""
    out: list[tuple[int, int, str]] = []
    r = read(data)
    for page in r.pages:
        x = y = 0
        for operands, op in ContentStream(page.get_contents(), r).operations:
            if op == b"Td":
                x, y = round(float(operands[0])), round(float(operands[1]))
            elif op == b"Tj":
                out.append((x, y, str(operands[0])))
    return out


X = {key: round(PDF._MARGIN + off * PDF._CHAR_W) for key, _t, off, _w in PDF._COLUMNS}


def column(data: bytes, key: str) -> list[str]:
    """The text in one table column, body rows only (header and footer excluded), in row order."""
    body = []
    header_seen = False
    for x, y, text in placements(data):
        if x == X[key] and text == dict((k, t) for k, t, _o, _w in PDF._COLUMNS)[key] and y > PDF._TOP - 400:
            header_seen = True
            continue
        if x == X[key] and y > PDF._MARGIN + 2 and header_seen:
            body.append(text)
    return body


def csv_rows(text: str) -> list[dict]:
    rows = list(csv.reader(io.StringIO(text)))
    return [dict(zip(rows[0], r)) for r in rows[1:]]


def audit_count(w) -> int:
    with w.sf() as s:
        return int(s.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == "admin.report_exported")) or 0)


DEFS = {
    "ai_workflow": definition_dict(metric_ids=["ai_usage", "ai_known_cost"], group_by="workflow"),
    "ai_model": definition_dict(metric_ids=["ai_usage"], group_by="model"),
    "feedback": {"report_id": "quality", "metric_ids": ["feedback"], "window": "30d", "group_by": "feedback_category"},
    "ops": {"report_id": "quality", "metric_ids": ["request_outcomes"], "window": "30d", "group_by": "operation"},
    "product": {"report_id": "product", "metric_ids": ["registrations", "onboarding_completed", "activation", "returning"], "window": "7d"},
}


# ------------------------------------------------------------------------------------------------------------------------------ content parity
@pytest.mark.parametrize("name", list(DEFS))
def test_pdf_figures_states_and_groups_equal_the_csv_and_json_rows(world, name):
    d = DEFS[name]
    c = export(world, format="csv", definition=d)
    j = export(world, format="json", definition=d)
    p = export(world, format="pdf", definition=d)
    assert c.status_code == j.status_code == p.status_code == 200, (c.text[:200], p.text[:200])
    rows = csv_rows(c.text)
    jrows = j.json()["rows"]
    assert len(rows) == len(jrows) == int(p.headers["x-export-rows"]) == int(c.headers["x-export-rows"])
    for cr, jr in zip(rows, jrows):                                                                # CSV is the JSON row, formula-neutralised
        assert cr == {k: RB.csv_safe(jr[k]) for k in RB.EXPORT_COLUMNS}
    data = p.content
    assert column(data, "state") == [f"{r['state']} (partial)" if r["partial"] else r["state"] for r in jrows]
    assert column(data, "value") == ["-" if r["value"] is None else repr(r["value"]) if isinstance(r["value"], float) else str(r["value"]) for r in jrows]     # a missing value is '-', never 0
    assert column(data, "group") == [r["group_value"] if r["group_value"] is not None else "-" for r in jrows]
    assert column(data, "unit") == [r["unit"] for r in jrows]
    assert read(data).metadata.title.startswith("Ask4Mo report")


def test_suppression_is_preserved_no_figure_for_a_suppressed_or_unavailable_bucket(world):
    d = DEFS["feedback"]
    rows = csv_rows(export(world, format="csv", definition=d).text)
    tone = next(r for r in rows if r["group_value"] == "tone")
    assert tone["state"] == "suppressed" and tone["value"] == ""                                   # 2 candidates: below the cohort floor
    data = export(world, format="pdf", definition=d).content
    states, values, groups = column(data, "state"), column(data, "value"), column(data, "group")
    i = groups.index("tone")
    assert states[i] == "suppressed" and values[i] == "-"
    text = " ".join(t for _x, _y, t in placements(data))
    assert "<5" not in text and "< 5" not in text                                                  # the floor value is never printed as a stand-in for the count
    assert not re.search(r"\btone\b[^a-z]*\b[1-9]\d*\b", text)                                     # no count next to the suppressed label


def test_the_pdf_response_is_audited_bounded_and_safely_named(world):
    before = audit_count(world)
    r = export(world, format="pdf", definition=DEFS["ai_workflow"])
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert re.fullmatch(r'attachment; filename="ask4mo-ai_economics-30d-\d{8}\.pdf"', r.headers["content-disposition"])
    assert r.headers["cache-control"] == "no-store" and r.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert r.content.startswith(b"%PDF-1.4") and r.content.rstrip().endswith(b"%%EOF") and len(r.content) <= PDF.PDF_MAX_BYTES
    assert audit_count(world) == before + 1
    with world.sf() as s:
        ev = s.scalars(select(AuditEvent).where(AuditEvent.event_type == "admin.report_exported").order_by(AuditEvent.id.desc())).first()
    assert ev.context["format"] == "pdf" and ev.context["row_count"] == int(r.headers["x-export-rows"]) and ev.context["source"] == "inline"
    dump = json.dumps(ev.context)
    for needle in ("agent", "practice", "840", "sentinel", "@"):
        assert needle not in dump


def test_a_saved_definition_exports_as_pdf_like_the_other_formats(world):
    sid = create_saved(world, definition=DEFS["ai_model"]).json()["id"]
    r = export(world, format="pdf", saved_id=sid)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert column(r.content, "value") == [x["value"] or "-" for x in csv_rows(export(world, format="csv", saved_id=sid).text)]
    assert export(world, format="pdf", saved_id=987654).status_code == 404


def test_the_pdf_carries_no_candidate_identifier_or_content(world):
    for d in DEFS.values():
        r = export(world, format="pdf", definition=d)
        assert r.status_code == 200
        text = " ".join(t for _x, _y, t in placements(r.content)).lower()
        for needle in ("example.test", "sentinel-", PW.lower(), "cookie", "user_id", "email"):
            assert needle not in text
        assert not re.search(r"\S+@\S+\.\S+", text)                                                      # no e-mail address
    assert not [c for c in RB.EXPORT_COLUMNS if re.search(r"user|email|candidate|subject|owner|session|token", c)]


# ------------------------------------------------------------------------------------------------------------------------------ authorization
@pytest.mark.parametrize("base", [API, CAPI])
def test_pdf_authorization_matrix_over_the_seven_personas_equals_the_other_formats(world, base):
    required = perm.REPORTS_READ if base == API else perm.REPORTS_COMMERCIAL
    d = {"report_id": "product", "metric_ids": ["registrations"], "window": "30d"} if base == API else {"report_id": "commercial", "metric_ids": ["mock_failed_payments"], "window": "30d"}
    assert len(M.PERSONAS) == 7
    for persona in M.PERSONAS:
        allowed = M.expected_allowed(frozenset({required}), persona)
        statuses = {fmt: export(world, persona, base, format=fmt, definition=d) for fmt in ("csv", "json", "pdf")}
        for fmt, r in statuses.items():
            if allowed:
                assert r.status_code == 200, (base, persona, fmt, r.status_code)
            else:
                assert r.status_code == 403 and r.json()["error"]["message"] == DENIED, (base, persona, fmt, r.status_code)
                assert not r.content.startswith(b"%PDF") and "metric" not in r.text
        assert statuses["pdf"].status_code == statuses["csv"].status_code == statuses["json"].status_code


def test_commercial_pdf_needs_the_commercial_permission_and_never_crosses_families(world):
    d = {"report_id": "commercial", "metric_ids": ["mock_mrr"], "window": "30d", "group_by": "currency"}
    assert export(world, "operations_admin", CAPI, format="pdf", definition=d).status_code == 403          # no commercial permission
    assert export(world, "operations_admin", API, format="pdf", definition=d).status_code == 403
    assert export(world, "billing_admin", API, format="pdf", definition=d).status_code == 403              # lacks reports.read
    assert export(world, "user", CAPI, format="pdf", definition=d).status_code == 403
    ok = export(world, "billing_admin", CAPI, format="pdf", definition=d)
    assert ok.status_code == 200 and ok.content.startswith(b"%PDF")
    assert column(ok.content, "group") == ["EUR", "USD"]                                                    # currencies are never combined
    assert export(world, "platform_admin", CAPI, format="pdf", definition=d).status_code == 200
    assert export(world, "platform_admin", API, format="pdf", definition={"report_id": "commercial", "metric_ids": ["access_plans"], "window": "30d"}).status_code == 403
    sid = create_saved(world, "platform_admin", base=CAPI, definition={"report_id": "commercial", "metric_ids": ["access_plans"], "window": "30d", "group_by": "plan"}, shared=True).json()["id"]
    assert export(world, "operations_admin", CAPI, format="pdf", saved_id=sid).status_code == 403
    assert export(world, "billing_admin", CAPI, format="pdf", saved_id=sid).status_code == 200


def test_an_anonymous_caller_gets_no_pdf(world):
    from fastapi.testclient import TestClient

    with TestClient(world.app) as anon:
        r = anon.post(f"{API}/export", json={"format": "pdf", "definition": DEFS["product"]})
    assert r.status_code in (401, 403) and not r.content.startswith(b"%PDF")


# ------------------------------------------------------------------------------------------------------------------------------ audit failure, bounds
def _assert_pdf_audit_failure(response, *, export_events_before: int, export_events_after: int) -> None:
    assert not response.content.startswith(b"%PDF")
    _assert_audit_failure_response(response, export_events_before=export_events_before, export_events_after=export_events_after)


def test_a_pdf_that_cannot_be_audited_is_not_sent(world, monkeypatch):
    from src.auth_repository import AuditRepository

    def boom(self, **kw):
        raise RuntimeError("audit down")
    monkeypatch.setattr(AuditRepository, "record", boom)
    before = audit_count(world)
    response = export(world, format="pdf", definition=DEFS["ai_workflow"])
    _assert_pdf_audit_failure(response, export_events_before=before, export_events_after=audit_count(world))


def test_pdf_audit_failure_allows_correlation_id_containing_report_value(world, monkeypatch):
    from src.auth_repository import AuditRepository

    def boom(self, **kw):
        raise RuntimeError("audit down")
    monkeypatch.setattr(AuditRepository, "record", boom)
    monkeypatch.setattr("src.api.middleware.uuid.uuid4", lambda: uuid.UUID("08400000-0000-4000-8000-000000000000"))
    before = audit_count(world)
    response = export(world, format="pdf", definition=DEFS["ai_workflow"])
    assert "840" in response.json()["error"]["request_id"]
    _assert_pdf_audit_failure(response, export_events_before=before, export_events_after=audit_count(world))


@pytest.mark.parametrize("mutation", [
    "numeric_value", "string_value", "report_field", "nested_field", "invalid_id", "mismatched_header",
    "wrong_code", "wrong_message", "malformed_envelope", "pdf_content", "attachment", "audit_committed",
])
def test_pdf_audit_failure_assertion_rejects_leaks_and_invalid_metadata(mutation):
    request_id = "08400000000040008000000000000000"
    body = {"error": {"code": "http_error", "message": "The export could not be audited, so nothing was exported.", "request_id": request_id}}
    headers = {"x-request-id": request_id}
    after = 0
    if mutation == "numeric_value":
        body["error"]["value"] = 840
    elif mutation == "string_value":
        body["error"]["value"] = "840"
    elif mutation == "report_field":
        body["error"]["metric_id"] = "agent"
    elif mutation == "nested_field":
        body["rows"] = [{"value": "840"}]
    elif mutation == "invalid_id":
        body["error"]["request_id"] = "invalid"
    elif mutation == "mismatched_header":
        headers["x-request-id"] = "12345678901240008000000000000000"
    elif mutation == "wrong_code":
        body["error"]["code"] = "other"
    elif mutation == "wrong_message":
        body["error"]["message"] = "other"
    elif mutation == "malformed_envelope":
        body["error"] = []
    elif mutation == "attachment":
        headers["content-disposition"] = "attachment; filename=report.pdf"
    elif mutation == "audit_committed":
        after = 1
    if mutation == "pdf_content":
        response = httpx.Response(503, content=b"%PDF-1.7 synthetic", headers={**headers, "content-type": "application/json"})
    else:
        response = httpx.Response(503, json=body, headers=headers)
    with pytest.raises(AssertionError):
        _assert_pdf_audit_failure(response, export_events_before=0, export_events_after=after)


def test_a_refused_pdf_is_never_audited(world, monkeypatch):
    before = audit_count(world)
    monkeypatch.setattr(PDF, "PDF_MAX_ROWS", 1)
    r = export(world, format="pdf", definition=DEFS["ai_workflow"])
    assert r.status_code == 422 and "[export_too_large]" in r.text and not r.content.startswith(b"%PDF")
    assert audit_count(world) == before
    assert export(world, format="csv", definition=DEFS["ai_workflow"]).status_code == 200                 # the other formats keep their own, wider bound


def test_the_row_page_and_byte_bounds(monkeypatch):
    prev = {"report_id": "product", "title": "Product usage", "window": "30d", "window_start": "2026-09-22T00:00:00+00:00", "window_end": "2026-10-22T00:00:00+00:00",
            "generated_at": "2026-10-22T00:00:00+00:00"}

    def rows(n: int):
        return [{"report_id": "product", "window": "30d", "metric_id": "m", "metric_label": f"Metric {i}", "unit": "count", "group_dimension": None, "group_value": None,
                 "state": "ok", "value": i, "partial": False} for i in range(n)]
    PDF.render_pdf(prev, rows(PDF.PDF_MAX_ROWS))                                                           # at the bound: fine, and within the byte and page bounds
    with pytest.raises(RB.ReportInvalid) as e:
        PDF.render_pdf(prev, rows(PDF.PDF_MAX_ROWS + 1))
    assert e.value.problems[0][0] == "export_too_large"
    monkeypatch.setattr(PDF, "PDF_MAX_PAGES", 1)
    with pytest.raises(RB.ReportInvalid):
        PDF.render_pdf(prev, rows(100))
    monkeypatch.undo()
    monkeypatch.setattr(PDF, "PDF_MAX_BYTES", 500)
    with pytest.raises(RB.ReportInvalid):
        PDF.render_pdf(prev, rows(10))
    monkeypatch.undo()
    assert len(PDF.render_pdf(prev, rows(PDF.PDF_MAX_ROWS))) <= PDF.PDF_MAX_BYTES
    with pytest.raises(ValueError):
        PDF.render_pdf(prev, [{"report_id": "x"}])                                                         # a row of another shape is never rendered


# ------------------------------------------------------------------------------------------------------------------------------ escaping, no active content, determinism
HOSTILE = [") Tj ET /Launch << /S /JavaScript /JS (app.alert(1)) >> (", "((((", "\\", "\\) \\(", "a\x00b\x1fc\nd\re\tf", "café 中文 \U0001F600", "=SUM(1+1)", "<</Type/Catalog>>", "%PDF-1.4 endstream endobj", "x" * 400,
           "word " * 80]


def hostile_input():
    prev = {"report_id": "product", "title": HOSTILE[0], "window": "30d", "window_start": None, "window_end": HOSTILE[1], "generated_at": HOSTILE[2]}
    rows = [{"report_id": "product", "window": "30d", "metric_id": "m", "metric_label": h, "unit": h[:9], "group_dimension": "g", "group_value": h, "state": "ok", "value": h, "partial": i % 2 == 0}
            for i, h in enumerate(HOSTILE)]
    return prev, rows


ALLOWED_KEYS = {"/Type", "/Pages", "/Kids", "/Count", "/Subtype", "/BaseFont", "/Encoding", "/Title", "/Producer", "/Parent", "/MediaBox", "/Resources", "/Font", "/F1", "/F2",
                "/Contents", "/Length", "/Size", "/Root", "/Info"}


def test_text_from_the_data_cannot_inject_pdf_syntax_and_round_trips_escaped():
    prev, rows = hostile_input()
    data = PDF.render_pdf(prev, rows)
    r = read(data)                                                                                         # strict parse: the file is well-formed
    n = len(r.pages)
    assert len(r.xref_objStm) == 0 and n >= 1
    seen_objects = 0
    for obj_id in range(1, 6 + 2 * n):
        obj = IndirectObject(obj_id, 0, r).get_object()
        seen_objects += 1
        if isinstance(obj, DictionaryObject):
            assert set(obj.keys()) <= ALLOWED_KEYS, (obj_id, set(obj.keys()) - ALLOWED_KEYS)
    assert seen_objects == 5 + 2 * n and r.trailer["/Root"]["/Type"] == "/Catalog"
    assert set(r.trailer["/Root"].keys()) == {"/Type", "/Pages"}                                         # no /OpenAction, /AA, /Names, /AcroForm, /URI
    for page in r.pages:
        assert "/Annots" not in page and "/AA" not in page and set(page["/Resources"].keys()) == {"/Font"}
        assert set(page["/Resources"]["/Font"].keys()) == {"/F1", "/F2"}
    text = "\n".join(t for _x, _y, t in placements(data))
    assert "((((" in text and "/Launch" in text and "app.alert" in text                                    # the hostile string is DATA on the page, not syntax
    assert "?" in text and "é" not in text and "\U0001F600" not in text                              # non-ASCII is reduced to '?'
    assert "\x00" not in text and "\x1f" not in text
    assert r.metadata.title is not None and "\n" not in r.metadata.title


def test_pdf_text_and_literal_escape_exactly():
    assert PDF.pdf_text("a(b)c\\d") == "a(b)c\\d"
    assert PDF._literal("a(b)c\\d") == "(a\\(b\\)c\\\\d)"
    assert PDF.pdf_text("xéy z") == "x?y?z" and PDF.pdf_text(None) == "" and PDF.pdf_text("a\nb\tc\rd") == "a b c d"
    assert PDF.pdf_text("\x00\x07\x7f") == ""
    assert PDF._wrap("a" * 50, 20) == ["a" * 20, "a" * 20, "a" * 10]
    assert PDF._wrap("word " * 100, 20, 3)[-1].endswith("...")


def test_a_real_export_has_no_active_content_and_no_external_reference(world):
    data = export(world, format="pdf", definition=DEFS["ai_workflow"]).content
    for name in (b"/JavaScript", b"/JS", b"/Launch", b"/URI", b"/OpenAction", b"/AA", b"/EmbeddedFile", b"/AcroForm", b"/XObject", b"/Annots", b"/FontFile", b"/SubmitForm",
                 b"/GoToR", b"/ImportData", b"/XFA", b"/RichMedia", b"http://", b"https://", b"/CreationDate", b"/ModDate", b"/ID"):
        assert name not in data, name
    r = read(data)
    assert [k for k in r.trailer.keys()] and "/Encrypt" not in r.trailer


def test_the_output_is_deterministic_and_has_no_timestamp_or_random_value():
    prev, rows = hostile_input()
    a, b = PDF.render_pdf(prev, rows), PDF.render_pdf(prev, rows)
    assert a == b
    prev2 = {**prev, "generated_at": "2026-10-22T00:00:00+00:00"}
    c, d = PDF.render_pdf(prev2, rows[:3]), PDF.render_pdf(prev2, rows[:3])
    assert c == d and c != a
    assert b"2026-10-22T00:00:00+00:00" in c                                                               # the data's own generation time is content; the file adds none
    assert datetime.now(timezone.utc).strftime("%Y%m%d").encode() not in c


def test_the_audit_vocabulary_and_permission_registry_are_unchanged():
    assert len(perm.PERMISSIONS) == 44
    with pytest.raises(ValueError):
        RB.export_filename("product", "30d", "xlsx", datetime(2026, 10, 22, tzinfo=timezone.utc))          # no other format exists
    assert RB.export_filename("product", "30d", "pdf", datetime(2026, 10, 22, tzinfo=timezone.utc)) == "ask4mo-product-30d-20261022.pdf"
