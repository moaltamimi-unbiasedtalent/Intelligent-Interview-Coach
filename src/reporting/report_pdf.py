"""Governed PDF rendering for the Admin report builder (package 03E2, PR 2). A dependency-free, deterministic, text-only PDF of the SAME already-suppressed rows
the CSV and JSON exports carry (``report_builder.export_rows``): nothing is recomputed, re-rounded or re-aggregated here.

Why a small writer and not a library: the report is a plain table of ASCII registry values. A hand-written PDF 1.4 file with the standard (non-embedded) Courier fonts
needs no new dependency, no font file, no image and no network, and its byte output is a pure function of its input (no timestamp, no document id, no random
value), which makes the tests exact. The writer can express ONLY: one catalog, one page tree, two standard fonts, an info dictionary with a title and a producer, and
per page one content stream of text-show operators. It has no code path that can emit JavaScript, an action, a link, a form, an attachment, an image, an
annotation, an embedded or external font, a XObject or a URI, so there is no active content and no external resource fetch.

Escaping: every string is reduced to printable ASCII (anything else becomes ``?``) and the three PDF string metacharacters ``\\``, ``(`` and ``)`` are escaped, so
text from the data (a bucket label such as ``=SUM(1+1)`` or an attempt such as ``) Tj ... (``) can never close the string or inject an operator or an object.

Bounds (checked BEFORE anything is audited or sent): at most ``PDF_MAX_ROWS`` rows, ``PDF_MAX_PAGES`` pages and ``PDF_MAX_BYTES`` bytes.
"""

from __future__ import annotations

from typing import Any, Final

from src.reporting.report_builder import EXPORT_COLUMNS, PRIVACY_NOTE, ReportInvalid

PDF_MAX_ROWS: Final = 500
PDF_MAX_PAGES: Final = 60
PDF_MAX_BYTES: Final = 1_000_000

_PAGE_W, _PAGE_H = 595, 842                      # A4 in points
_MARGIN = 40
_SIZE = 8                                       # Courier is monospaced: every glyph is 600/1000 em, so widths are exact
_CHAR_W = _SIZE * 0.6
_LINE_H = 10
_MAX_CELL_LINES = 6
_TOP = _PAGE_H - _MARGIN
_BOTTOM = _MARGIN + 14                           # room for the page footer
# (column key, header, offset in characters, width in characters)
_COLUMNS: Final[tuple[tuple[str, str, int, int], ...]] = (
    ("metric", "Metric", 0, 30), ("group", "Group", 32, 20), ("state", "State", 54, 14), ("value", "Value", 70, 14), ("unit", "Unit", 86, 9),
)
_TEXT_WIDTH_CHARS = 107                          # (595 - 2 * 40) / 4.8


def pdf_text(value: Any) -> str:
    """Printable ASCII only. Control characters are dropped, line breaks become spaces and every non-ASCII character becomes ``?`` (the standard fonts carry no more)."""
    s = "" if value is None else str(value)
    out = []
    for ch in s:
        o = ord(ch)
        if ch in "\r\n\t":
            out.append(" ")
        elif 0x20 <= o <= 0x7E:
            out.append(ch)
        elif o < 0x20 or o == 0x7F:
            continue
        else:
            out.append("?")
    return "".join(out)


def _literal(s: str) -> str:
    """A PDF string literal for already-sanitised ASCII: escapes backslash and both parentheses."""
    return "(" + s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


def _wrap(text: str, width: int, max_lines: int = _MAX_CELL_LINES) -> list[str]:
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        while len(w) > width:                                    # a word longer than the column is hard-broken
            if cur:
                lines.append(cur)
                cur = ""
            lines.append(w[:width])
            w = w[width:]
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max(0, width - 3)] + "..."
    return lines


def _value_text(v: Any) -> str:
    """The same figure text the CSV carries (an int as is, a float by ``repr``); a missing value is ``-`` (never ``0``)."""
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "true" if v else "false"
    return repr(v) if isinstance(v, float) else str(v)


def _state_text(row: dict) -> str:
    return f"{row['state']} (partial)" if row.get("partial") else str(row["state"])


def _cells(row: dict) -> dict[str, str]:
    return {"metric": pdf_text(row["metric_label"]), "group": pdf_text(row["group_value"]) if row["group_value"] is not None else "-",
            "state": pdf_text(_state_text(row)), "value": pdf_text(_value_text(row["value"])), "unit": pdf_text(row["unit"])}


def _layout(preview: dict, rows: list[dict]) -> list[list[tuple[str, int, int, str]]]:
    """Pages of text placements ``(font, x, y, text)``, one per text-show operator."""
    pages: list[list[tuple[str, int, int, str]]] = [[]]
    y = _TOP

    def put(font: str, x: float, ypos: int, text: str) -> None:
        pages[-1].append((font, int(round(x)), ypos, text))

    def newline_check(lines_needed: int) -> None:
        nonlocal y
        if y - (lines_needed - 1) * _LINE_H < _BOTTOM:
            pages.append([])
            y = _TOP
            header()

    def header() -> None:
        nonlocal y
        for key, title, off, _w in _COLUMNS:
            put("F2", _MARGIN + off * _CHAR_W, y, title)
        y -= _LINE_H * 2

    put("F2", _MARGIN, y, "ASK4MO REPORT EXPORT")
    y -= _LINE_H * 2
    meta = [f"Report: {pdf_text(preview['title'])} ({pdf_text(preview['report_id'])})",
            f"Window: {pdf_text(preview['window'])}, UTC {pdf_text(preview['window_start'] or 'all time')} to {pdf_text(preview['window_end'])}",
            f"Generated: {pdf_text(preview['generated_at'])}", f"Rows: {len(rows)}"]
    for text in meta:
        for ln in _wrap(text, _TEXT_WIDTH_CHARS):
            put("F1", _MARGIN, y, ln)
            y -= _LINE_H
    y -= _LINE_H
    for ln in _wrap(pdf_text(PRIVACY_NOTE), _TEXT_WIDTH_CHARS):
        put("F1", _MARGIN, y, ln)
        y -= _LINE_H
    y -= _LINE_H
    header()
    for row in rows:
        cells = _cells(row)
        wrapped = {key: _wrap(cells[key], w) for key, _t, _o, w in _COLUMNS}
        n = max(len(v) for v in wrapped.values())
        newline_check(n)
        for key, _t, off, _w in _COLUMNS:
            for i, ln in enumerate(wrapped[key]):
                put("F1", _MARGIN + off * _CHAR_W, y - i * _LINE_H, ln)
        y -= n * _LINE_H
    return pages


def check_pdf_size(rows: list[dict]) -> None:
    """Bounds that need no rendering (refused with the stable ``export_too_large`` problem before anything is audited or sent)."""
    if len(rows) > PDF_MAX_ROWS:
        raise ReportInvalid([("export_too_large", "definition", f"A PDF export is limited to {PDF_MAX_ROWS} rows; narrow the metrics or the grouping, or use CSV or JSON.")])


def render_pdf(preview: dict, rows: list[dict]) -> bytes:
    """The PDF bytes for ``rows`` (the CSV/JSON rows). Raises ``ReportInvalid`` when a bound is exceeded; never returns a partial file."""
    check_pdf_size(rows)
    if any(set(r) != set(EXPORT_COLUMNS) for r in rows):
        raise ValueError("unexpected export row shape")
    pages = _layout(preview, rows)
    if len(pages) > PDF_MAX_PAGES:
        raise ReportInvalid([("export_too_large", "definition", f"A PDF export is limited to {PDF_MAX_PAGES} pages; narrow the metrics or the grouping, or use CSV or JSON.")])
    n = len(pages)
    objs: list[bytes] = []                                                    # object i+1 is objs[i]
    kids = " ".join(f"{6 + 2 * i} 0 R" for i in range(n))
    title = pdf_text(f"Ask4Mo report {preview['report_id']} {preview['window']}")
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode("ascii"))
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold /Encoding /WinAnsiEncoding >>")
    objs.append(f"<< /Title {_literal(title)} /Producer (Ask4Mo) >>".encode("ascii"))
    for i, page in enumerate(pages):
        ops = []
        for font, x, y, text in page:
            ops.append(f"BT /{font} {_SIZE} Tf {x} {y} Td {_literal(text)} Tj ET")
        footer = f"Page {i + 1} of {n}"
        ops.append(f"BT /F1 {_SIZE} Tf {_MARGIN} {_MARGIN} Td {_literal(footer)} Tj ET")
        stream = "\n".join(ops).encode("ascii")
        objs.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_PAGE_W} {_PAGE_H}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {7 + 2 * i} 0 R >>").encode("ascii"))
        objs.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs):
        offsets.append(len(out))
        out += f"{i + 1} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode("ascii") + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info 5 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    if len(out) > PDF_MAX_BYTES:
        raise ReportInvalid([("export_too_large", "definition", "The PDF would be too large; narrow the metrics or the grouping, or use CSV or JSON.")])
    return bytes(out)
