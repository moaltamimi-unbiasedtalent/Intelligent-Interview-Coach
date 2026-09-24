"""Native text extraction with provenance (Capstone P4/E2, §8).

Extracts text from text-based PDF (pypdf, per-page), DOCX (python-docx, per-paragraph)
and TXT (per-block), preserving a source location so a later claim can point back to the
document page/section. Bounded by a page limit; encrypted/corrupt files fail safely with
a user-safe reason. No document text is ever executed or fed to an LLM here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.documents.validation import MAX_PAGES

__all__ = ["Segment", "ParseResult", "ParseError", "parse_document", "needs_ocr"]


class ParseError(Exception):
    """A safe, user-facing parse failure (encrypted / corrupt / unreadable)."""


@dataclass(frozen=True)
class Segment:
    text: str
    page: int | None = None
    section: str | None = None


@dataclass
class ParseResult:
    segments: list[Segment] = field(default_factory=list)
    page_count: int | None = None
    origin: str = "native"

    @property
    def has_text(self) -> bool:
        return any(s.text.strip() for s in self.segments)

    @property
    def full_text(self) -> str:
        return "\n".join(s.text for s in self.segments if s.text.strip())


def parse_pdf(data: bytes) -> ParseResult:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(_bytes_io(data))
    except (PdfReadError, Exception) as exc:  # noqa: BLE001 - normalise to a safe error
        raise ParseError("This PDF could not be read (it may be corrupt).") from exc
    if getattr(reader, "is_encrypted", False):
        # Attempt an empty-password decrypt; if it still needs one, fail safely.
        try:
            if reader.decrypt("") == 0:  # 0 = failed
                raise ParseError("This PDF is password-protected. Remove the password and re-upload.")
        except ParseError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ParseError("This PDF is password-protected. Remove the password and re-upload.") from exc

    pages = reader.pages[:MAX_PAGES]
    segments: list[Segment] = []
    for i, page in enumerate(pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - a bad page never aborts the whole parse
            text = ""
        if text.strip():
            segments.append(Segment(text=text.strip(), page=i))
    return ParseResult(segments=segments, page_count=len(reader.pages), origin="native")


def parse_docx(data: bytes) -> ParseResult:
    try:
        import docx  # python-docx
    except ImportError as exc:  # pragma: no cover - declared dependency
        raise ParseError("DOCX support is not available.") from exc
    try:
        document = docx.Document(_bytes_io(data))
    except Exception as exc:  # noqa: BLE001
        raise ParseError("This DOCX could not be read (it may be corrupt).") from exc
    segments: list[Segment] = []
    for idx, para in enumerate(document.paragraphs, start=1):
        text = (para.text or "").strip()
        if text:
            segments.append(Segment(text=text, section=f"paragraph {idx}"))
    return ParseResult(segments=segments, page_count=None, origin="native")


def parse_txt(data: bytes) -> ParseResult:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="replace")
    segments: list[Segment] = []
    # Split into blank-line-separated blocks with a stable section index.
    blocks = [b.strip() for b in text.replace("\r\n", "\n").split("\n\n")]
    idx = 1
    for block in blocks:
        if block:
            segments.append(Segment(text=block, section=f"block {idx}"))
            idx += 1
    return ParseResult(segments=segments, page_count=None, origin="native")


def parse_document(data: bytes, extension: str) -> ParseResult:
    if extension == "pdf":
        return parse_pdf(data)
    if extension == "docx":
        return parse_docx(data)
    if extension == "txt":
        return parse_txt(data)
    # Images have no native text — the OCR path handles them.
    return ParseResult(segments=[], page_count=None, origin="native")


def needs_ocr(extension: str, native: ParseResult) -> bool:
    """Route to OCR only when there is no usable native text (scanned/image)."""
    if extension in ("png", "jpg", "jpeg"):
        return True
    if extension == "pdf" and not native.has_text:
        return True
    return False


def _bytes_io(data: bytes):
    from io import BytesIO

    return BytesIO(data)
