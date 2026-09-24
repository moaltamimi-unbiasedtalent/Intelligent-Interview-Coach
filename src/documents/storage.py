"""Private document storage (Capstone P4).

An abstraction over where original candidate files live. The default
:class:`LocalDocumentStore` writes to a private directory OUTSIDE the web root, keyed by
an opaque random ``storage_key`` (never a client-supplied or guessable name), so files
are never served from a public path/URL. The interface is object-storage-compatible so a
hosted deployment can swap in S3/GCS without changing callers.

Safety: the storage key is validated to a strict ``[A-Za-z0-9_-]`` pattern before it ever
touches the filesystem, so a caller can never traverse outside the private root.
"""

from __future__ import annotations

import os
import re
import secrets
from pathlib import Path
from typing import Protocol

__all__ = ["DocumentStore", "LocalDocumentStore", "new_storage_key", "build_document_store"]

_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def new_storage_key() -> str:
    """Return an opaque, non-guessable storage key (~43 url-safe chars)."""
    return secrets.token_urlsafe(32)


def _safe_key(key: str) -> str:
    if not _KEY_RE.match(key or ""):
        raise ValueError("Invalid storage key.")
    return key


class DocumentStore(Protocol):
    def save(self, key: str, data: bytes) -> None: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> bool: ...
    def exists(self, key: str) -> bool: ...


class LocalDocumentStore:
    """Filesystem store under a private root (dev + single-node). Never web-served."""

    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self._root / _safe_key(key)).resolve()
        # Defence in depth: the resolved path must remain within the private root.
        if os.path.commonpath([str(self._root), str(p)]) != str(self._root):
            raise ValueError("Path traversal detected.")
        return p

    def save(self, key: str, data: bytes) -> None:
        with open(self._path(key), "wb") as fh:
            fh.write(data)

    def read(self, key: str) -> bytes:
        with open(self._path(key), "rb") as fh:
            return fh.read()

    def delete(self, key: str) -> bool:
        try:
            self._path(key).unlink()
            return True
        except FileNotFoundError:
            return False

    def exists(self, key: str) -> bool:
        try:
            return self._path(key).is_file()
        except ValueError:
            return False


def build_document_store() -> DocumentStore:
    """Build the configured store. Defaults to a private local dir OUTSIDE the web root."""
    root = os.environ.get("DOCUMENT_STORAGE_DIR", "").strip() or os.path.join(
        os.environ.get("TMPDIR", "/tmp"), "ask4mo_documents"
    )
    return LocalDocumentStore(root)
