"""Authenticated, chunked file sealing for backup sets (AES-256-GCM, ``cryptography`` is already a dependency since W12.4B).

KEY HANDLING (the contract the runbook repeats)
* The key is 32 random bytes, base64 encoded, supplied ONLY through the operator's environment (``BACKUP_ENCRYPTION_KEY``) or a secret manager that injects it
  into that environment. It is never written to the repository, a manifest, a report, a log or a drill record, and no function here echoes it.
* The manifest records only a KEY FINGERPRINT (HMAC of a fixed label under the key, 8 hex characters) so a restore can say "wrong key" instead of failing with a
  generic authentication error. A fingerprint is not the key and cannot be reversed to it.
* Every file is sealed with its own random prefix; the associated data binds the set id and the logical file name, so a sealed file cannot be swapped between
  names or sets, and a final-chunk marker makes truncation detectable.
* Losing the key means the set is unrecoverable. Keep the key in a different place from the backups (the runbook gives the rotation and escrow rules).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
from pathlib import Path
from typing import Iterator

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ENCRYPTION_KEY_ENV = "BACKUP_ENCRYPTION_KEY"
SIGNING_KEY_ENV = "BACKUP_SIGNING_KEY"
MAGIC = b"A4MB1"
CHUNK = 1 << 20
_LEN = struct.Struct(">I")
_IDX = struct.Struct(">I")


class CryptoError(Exception):
    """A refusal with a fixed, safe ``code`` (never key material, a path or the cryptography library's text)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def parse_key(value: str | None, *, missing: str = "encryption_key_missing", invalid: str = "encryption_key_invalid") -> bytes:
    if not value or not value.strip():
        raise CryptoError(missing)
    text = value.strip()
    try:
        raw = base64.b64decode(text.encode("ascii"), validate=True)
    except Exception:  # noqa: BLE001 - never echo the value
        try:
            raw = base64.urlsafe_b64decode(text.encode("ascii") + b"=" * (-len(text) % 4))
        except Exception:  # noqa: BLE001
            raise CryptoError(invalid) from None
    if len(raw) != 32:
        raise CryptoError(invalid)
    return raw


def key_from_env(name: str = ENCRYPTION_KEY_ENV, *, env: dict | None = None) -> bytes:
    """Read a 32-byte key from the process environment. The environment is the operator's, never a ``.env`` file loaded by this tool."""
    enc = name == ENCRYPTION_KEY_ENV
    return parse_key((env if env is not None else os.environ).get(name), missing="encryption_key_missing" if enc else "signing_key_missing",
                     invalid="encryption_key_invalid" if enc else "signing_key_invalid")


def generate_key() -> str:
    """A fresh base64 key for the operator to store in a secret manager. Printed once by the CLI ``keygen`` and never stored by this tool."""
    return base64.b64encode(os.urandom(32)).decode("ascii")


def fingerprint(key: bytes) -> str:
    return hmac.new(key, b"ask4mo-backup-key-fingerprint-v1", hashlib.sha256).hexdigest()[:8]


def derive_signing_key(encryption_key: bytes) -> bytes:
    """A domain-separated manifest-signing key derived from the sealing key, so a sealed set is always manifest-authenticated without a second secret."""
    return hmac.new(encryption_key, b"ask4mo-backup-manifest-signing-v1", hashlib.sha256).digest()


def _aad(set_id: str, logical: str, index: int, final: bool) -> bytes:
    return f"{set_id}|{logical}|".encode("utf-8") + _IDX.pack(index) + (b"\x01" if final else b"\x00")


def _nonce(prefix: bytes, index: int) -> bytes:
    return prefix + _IDX.pack(index)


def seal_file(src: Path, dst: Path, key: bytes, *, set_id: str, logical: str) -> tuple[str, int]:
    """Encrypt ``src`` into the NEW file ``dst`` (refused when it exists). Returns (plaintext sha256, plaintext size)."""
    if dst.exists() or dst.is_symlink():
        raise CryptoError("destination_exists")
    gcm = AESGCM(key)
    prefix = os.urandom(8)
    h = hashlib.sha256()
    size = 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(src, "rb") as fin, open(dst, "xb") as fout:
        fout.write(MAGIC + prefix)
        index = 0
        block = fin.read(CHUNK)
        while True:
            nxt = fin.read(CHUNK)
            final = not nxt
            h.update(block)
            size += len(block)
            ct = gcm.encrypt(_nonce(prefix, index), block, _aad(set_id, logical, index, final))
            fout.write(_LEN.pack(len(ct)) + ct)
            if final:
                break
            block, index = nxt, index + 1
    return h.hexdigest(), size


def open_sealed(src: Path, key: bytes, *, set_id: str, logical: str) -> Iterator[bytes]:
    """Yield the plaintext chunks of a sealed file. Raises ``CryptoError('sealed_file_invalid')`` on a wrong key, a modified, truncated or swapped file."""
    gcm = AESGCM(key)
    with open(src, "rb") as fin:
        head = fin.read(len(MAGIC) + 8)
        if len(head) != len(MAGIC) + 8 or not head.startswith(MAGIC):
            raise CryptoError("sealed_file_invalid")
        prefix = head[len(MAGIC):]
        index = 0
        pending = fin.read(_LEN.size)
        if not pending:
            raise CryptoError("sealed_file_invalid")
        while pending:
            if len(pending) != _LEN.size:
                raise CryptoError("sealed_file_invalid")
            (n,) = _LEN.unpack(pending)
            if not 16 <= n <= CHUNK + 16:
                raise CryptoError("sealed_file_invalid")
            ct = fin.read(n)
            if len(ct) != n:
                raise CryptoError("sealed_file_invalid")
            following = fin.read(_LEN.size)
            final = not following
            try:
                yield gcm.decrypt(_nonce(prefix, index), ct, _aad(set_id, logical, index, final))
            except InvalidTag:
                raise CryptoError("sealed_file_invalid") from None
            pending, index = following, index + 1


def unseal_to(src: Path, dst: Path, key: bytes, *, set_id: str, logical: str) -> tuple[str, int]:
    """Decrypt into the NEW file ``dst`` (refused when it exists). Returns (plaintext sha256, size)."""
    if dst.exists() or dst.is_symlink():
        raise CryptoError("destination_exists")
    h = hashlib.sha256()
    size = 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "xb") as fout:
        for block in open_sealed(src, key, set_id=set_id, logical=logical):
            fout.write(block)
            h.update(block)
            size += len(block)
    return h.hexdigest(), size


def sealed_sha256(src: Path, key: bytes, *, set_id: str, logical: str) -> str:
    h = hashlib.sha256()
    for block in open_sealed(src, key, set_id=set_id, logical=logical):
        h.update(block)
    return h.hexdigest()
