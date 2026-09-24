"""OCR abstraction for scanned/image documents (Capstone P4/E2, §9/§10).

A vendor-neutral seam so the pipeline is decoupled from any OCR engine. The default
:class:`TesseractOcrEngine` uses local, open-source Tesseract (lazily imported; NO paid
provider). When Tesseract (or its Python/system packages) is unavailable, OCR degrades to
a clear FAILED state — it never crashes and never silently drops the file. Tests inject a
deterministic fake, so the pipeline is fully testable without the binary.

Language support for en/de/fr/es/it/pt/nl is CONFIGURED (mapped to Tesseract language
codes) but its live quality is BROWSER/ENGINE-DEPENDENT and UNVALIDATED here. The
document/user may supply a language hint; we never infer language from identity.
OCR output is always labelled as OCR-derived (origin='ocr') with page identity preserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.documents.parsing import ParseResult, Segment
from src.documents.validation import MAX_PAGES

__all__ = ["OcrEngine", "OcrResult", "OcrError", "TesseractOcrEngine", "build_ocr_engine", "TESSERACT_LANGS"]

# Supported product locales → Tesseract language codes (configured, not quality-tested).
TESSERACT_LANGS: dict[str, str] = {
    "en": "eng", "de": "deu", "fr": "fra", "es": "spa", "it": "ita", "pt": "por", "nl": "nld",
}


class OcrError(Exception):
    """A safe OCR failure (engine unavailable / unreadable scan)."""


@dataclass(frozen=True)
class OcrResult:
    text: str
    page: int | None = None


class OcrEngine(Protocol):
    def is_available(self) -> bool: ...
    def image_to_text(self, image_bytes: bytes, *, lang: str = "en") -> str: ...
    def pdf_to_text(self, pdf_bytes: bytes, *, lang: str = "en") -> list[OcrResult]: ...


class TesseractOcrEngine:
    """Local Tesseract engine (lazily imported). Live quality UNVALIDATED."""

    def is_available(self) -> bool:
        try:
            import pytesseract  # noqa: F401

            return True
        except Exception:  # noqa: BLE001
            return False

    def image_to_text(self, image_bytes: bytes, *, lang: str = "en") -> str:  # pragma: no cover - live path
        try:
            import pytesseract
            from PIL import Image
            from io import BytesIO

            code = TESSERACT_LANGS.get(lang, "eng")
            return pytesseract.image_to_string(Image.open(BytesIO(image_bytes)), lang=code) or ""
        except Exception as exc:  # noqa: BLE001
            raise OcrError("Could not read this image.") from exc

    def pdf_to_text(self, pdf_bytes: bytes, *, lang: str = "en") -> list[OcrResult]:  # pragma: no cover - live path
        try:
            from pdf2image import convert_from_bytes

            images = convert_from_bytes(pdf_bytes)[:MAX_PAGES]
        except Exception as exc:  # noqa: BLE001
            raise OcrError("Could not render this scanned PDF for OCR.") from exc
        out: list[OcrResult] = []
        for i, img in enumerate(images, start=1):
            from io import BytesIO

            buf = BytesIO()
            img.save(buf, format="PNG")
            out.append(OcrResult(text=self.image_to_text(buf.getvalue(), lang=lang), page=i))
        return out


def ocr_parse(engine: OcrEngine, data: bytes, extension: str, *, lang: str = "en") -> ParseResult:
    """Run OCR and return a ParseResult labelled origin='ocr' with page provenance."""
    if not engine.is_available():
        raise OcrError("Scanned-document OCR is not available in this environment.")
    segments: list[Segment] = []
    if extension in ("png", "jpg", "jpeg"):
        text = engine.image_to_text(data, lang=lang)
        if text.strip():
            segments.append(Segment(text=text.strip(), page=1))
    else:  # scanned PDF
        for res in engine.pdf_to_text(data, lang=lang):
            if res.text.strip():
                segments.append(Segment(text=res.text.strip(), page=res.page))
    return ParseResult(segments=segments, page_count=len(segments) or None, origin="ocr")


def build_ocr_engine() -> OcrEngine:
    return TesseractOcrEngine()
