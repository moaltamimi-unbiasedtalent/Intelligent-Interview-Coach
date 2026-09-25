"""File security scanning for uploads (Capstone P8, §16/§17).

P4 delivered content-safety validation (MIME/magic/size/page). This adds the malware-scan
seam with an explicit, defensible fail-safe policy for hosted operation:

- A ``FileSecurityScanner`` abstraction with a deterministic ``FakeScanner`` (CI/dev; detects
  the EICAR test signature), a ``NullScanner`` (no-op, dev only), and a ``ClamAvScanner`` stub
  for a real clamd deployment (LIVE-UNVALIDATED; never runs in tests).
- ``enforce_scan`` implements the fail-safe rule (§17): when scanning is REQUIRED by policy
  and no scanner is available, uploads **fail closed** (503) rather than silently claiming the
  file was scanned. We never display "virus-free" unless a real scanner actually ran and
  passed.

No external/live scan is performed without configuration; the default (dev) is a NullScanner
with scanning NOT required.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

__all__ = [
    "ScanResult",
    "FileSecurityScanner",
    "NullScanner",
    "FakeScanner",
    "ClamAvScanner",
    "FileScanUnavailable",
    "FileRejected",
    "build_file_scanner",
    "scan_required",
    "enforce_scan",
]

# The EICAR anti-malware test string (harmless, industry-standard). Used by FakeScanner so CI
# can prove the reject path without any real malware.
EICAR = (
    b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
)


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    scanner: str          # which scanner ran (so we never claim more than we did)
    detail: str = ""


class FileSecurityScanner(Protocol):
    name: str

    def available(self) -> bool:
        ...

    def scan(self, data: bytes, filename: str) -> ScanResult:
        ...


class FileScanUnavailable(RuntimeError):
    """Scanning is required by policy but no scanner is available → fail closed."""


class FileRejected(RuntimeError):
    """A scanner ran and flagged the file."""


class NullScanner:
    """No-op scanner (dev only). ``available`` is True but it performs NO real scanning, so it
    must never be used where scanning is REQUIRED — ``enforce_scan`` treats a NullScanner as
    'no real scan ran' and never emits a clean/virus-free claim from it."""

    name = "null"

    def available(self) -> bool:
        return True

    def scan(self, data: bytes, filename: str) -> ScanResult:
        return ScanResult(clean=True, scanner=self.name, detail="no scan performed")


class FakeScanner:
    """Deterministic scanner for CI/dev: flags the EICAR signature, passes everything else."""

    name = "fake"

    def available(self) -> bool:
        return True

    def scan(self, data: bytes, filename: str) -> ScanResult:
        if EICAR in data:
            return ScanResult(clean=False, scanner=self.name, detail="eicar-test-signature")
        return ScanResult(clean=True, scanner=self.name, detail="no signatures matched")


class ClamAvScanner:
    """Adapter for a real clamd deployment (LIVE-UNVALIDATED — never exercised in tests).

    ``available`` checks reachability without scanning; ``scan`` streams to clamd. The actual
    socket path is guarded so importing this module never opens a connection.
    """

    name = "clamav"

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port

    def available(self) -> bool:  # pragma: no cover - requires a live clamd
        import socket

        try:
            with socket.create_connection((self._host, self._port), timeout=1.5):
                return True
        except Exception:  # noqa: BLE001
            return False

    def scan(self, data: bytes, filename: str) -> ScanResult:  # pragma: no cover - live clamd
        import socket

        try:
            with socket.create_connection((self._host, self._port), timeout=10.0) as sock:
                sock.sendall(b"zINSTREAM\x00")
                chunk = len(data).to_bytes(4, "big") + data
                sock.sendall(chunk)
                sock.sendall((0).to_bytes(4, "big"))
                reply = sock.recv(4096).decode("latin-1", "ignore")
            clean = "OK" in reply and "FOUND" not in reply
            return ScanResult(clean=clean, scanner=self.name, detail=reply.strip())
        except Exception as exc:  # noqa: BLE001
            raise FileScanUnavailable(str(exc)) from exc


def build_file_scanner() -> FileSecurityScanner:
    """Select the scanner from env. Default (dev) is NullScanner. ``fake`` for CI; ``clamav``
    for a configured clamd host."""
    provider = (os.environ.get("FILE_SCAN_PROVIDER", "") or "").strip().lower()
    if provider == "clamav":
        host = os.environ.get("CLAMAV_HOST", "127.0.0.1")
        port = int(os.environ.get("CLAMAV_PORT", "3310") or "3310")
        return ClamAvScanner(host, port)
    if provider == "fake":
        return FakeScanner()
    return NullScanner()


def scan_required() -> bool:
    """Whether a real malware scan is REQUIRED before accepting an upload (§17)."""
    return (os.environ.get("MALWARE_SCAN_REQUIRED", "") or "").strip().lower() in {
        "1", "true", "yes", "on"}


def _real_scanner(scanner: FileSecurityScanner) -> bool:
    """A NullScanner does not count as a real scan."""
    return scanner is not None and scanner.name != "null" and scanner.available()


def enforce_scan(data: bytes, filename: str, *, scanner: FileSecurityScanner | None = None,
                 required: bool | None = None) -> ScanResult:
    """Apply the fail-safe upload policy (§17).

    - required + no real scanner → FileScanUnavailable (caller returns 503; fail closed).
    - a real scanner flags the file → FileRejected.
    - a real scanner passes → clean ScanResult (the only case that may claim 'scanned').
    - not required + only NullScanner → returns a NullScanner result (never a virus-free claim).
    """
    scanner = scanner if scanner is not None else build_file_scanner()
    require = scan_required() if required is None else required
    if require and not _real_scanner(scanner):
        raise FileScanUnavailable(
            "Malware scanning is required but no scanner is available.")
    result = scanner.scan(data, filename)
    if not result.clean:
        raise FileRejected(result.detail or "file failed a security scan")
    return result
