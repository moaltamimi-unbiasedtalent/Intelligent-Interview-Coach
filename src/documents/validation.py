"""Upload validation & filename sanitisation (Capstone P4/E2, §3/§5).

Bounded, allow-listed file safety. We accept only text-based PDF, DOCX and TXT (plus
PNG/JPEG images for the OCR path), enforce size and page limits, sanitise the display
filename, and check that the declared type is internally consistent (magic-byte sniff)
to resist MIME spoofing. No file is ever executed, interpreted, or given a public path.

NOTE: this is content-safety validation, NOT malware scanning. No antivirus is claimed;
production must add a real scanner before public launch (documented in the privacy notes).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "MAX_FILE_BYTES", "MAX_PAGES", "SUPPORTED",
    "ValidatedUpload", "DocumentValidationError",
    "validate_upload", "sanitise_filename",
]

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_PAGES = 50

# Allow-list: extension → (canonical mime, is_ocr_image). PDF/DOCX/TXT are the declared
# text types; PNG/JPEG are accepted only as scanned-image inputs for the OCR path.
SUPPORTED: dict[str, tuple[str, bool]] = {
    "pdf": ("application/pdf", False),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", False),
    "txt": ("text/plain", False),
    "png": ("image/png", True),
    "jpg": ("image/jpeg", True),
    "jpeg": ("image/jpeg", True),
}


class DocumentValidationError(Exception):
    """A safe, user-facing validation failure (no internal detail)."""


@dataclass(frozen=True)
class ValidatedUpload:
    extension: str
    mime_type: str
    is_image: bool
    size_bytes: int
    safe_filename: str


def sanitise_filename(name: str) -> str:
    """Return a safe DISPLAY filename (never used as a filesystem path)."""
    base = (name or "").replace("\\", "/").split("/")[-1]  # strip any path components
    base = re.sub(r"[\x00-\x1f]", "", base)  # control chars
    base = re.sub(r"[^A-Za-z0-9._ \-()]", "_", base).strip() or "document"
    return base[:255]


def _sniff(data: bytes, extension: str) -> bool:
    """Best-effort magic-byte consistency check to resist MIME/extension spoofing."""
    if extension == "pdf":
        return data[:5] == b"%PDF-"
    if extension == "docx":
        # DOCX is a ZIP (Office Open XML) → PK zip signature.
        return data[:2] == b"PK"
    if extension == "png":
        return data[:8] == b"\x89PNG\r\n\x1a\n"
    if extension in ("jpg", "jpeg"):
        return data[:3] == b"\xff\xd8\xff"
    if extension == "txt":
        # A text file must decode as UTF-8/latin-1 and contain no NUL bytes.
        if b"\x00" in data[:4096]:
            return False
        try:
            data[:4096].decode("utf-8")
            return True
        except UnicodeDecodeError:
            try:
                data[:4096].decode("latin-1")
                return True
            except UnicodeDecodeError:
                return False
    return False


def validate_upload(filename: str, data: bytes, *, declared_mime: str | None = None) -> ValidatedUpload:
    """Validate an upload against the allow-list, size and content-consistency checks."""
    if not data:
        raise DocumentValidationError("The file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise DocumentValidationError("The file is too large (max 10 MB).")

    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    if ext not in SUPPORTED:
        raise DocumentValidationError("Unsupported file type. Use PDF, DOCX, TXT, PNG or JPEG.")

    mime, is_image = SUPPORTED[ext]
    if not _sniff(data, ext):
        # Extension/content mismatch (possible spoof) or corrupt/binary text.
        raise DocumentValidationError("The file content does not match its type.")

    return ValidatedUpload(
        extension=ext,
        mime_type=mime,
        is_image=is_image,
        size_bytes=len(data),
        safe_filename=sanitise_filename(filename),
    )
