"""File security scanning for uploads (Capstone P8, §16/§17; real clamd client in package 02C).

- A ``FileSecurityScanner`` abstraction with a deterministic ``FakeScanner`` (DEVELOPMENT SIMULATION ONLY; detects the EICAR test signature and is
  refused by the hosted configuration guard and by ``enforce_scan`` in staging/production), a ``NullScanner`` (no-op, dev only) and a real
  ``ClamAvScanner`` that speaks the clamd ``zINSTREAM`` protocol through ``ClamdClient``.
- Results are strictly typed (``ScanStatus``): clean, infected, unavailable, error, too_large, timeout. They never carry file content, paths or raw
  scanner output: only a bounded, character-restricted signature NAME for an infection.
- ``enforce_scan`` is FAIL CLOSED (§17): anything other than a clean result from a real scanner (when scanning is required) is refused, and a scanner
  outage (``FileScanUnavailable``) is a different exception from an infection (``FileRejected``) so callers can answer 503 versus 422.
"""

from __future__ import annotations

import os
import re
import socket
import struct
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

__all__ = [
    "ScanStatus", "ScanResult", "FileSecurityScanner", "NullScanner", "FakeScanner", "ClamAvScanner", "ClamdClient", "ClamdReply",
    "FileScanUnavailable", "FileRejected", "FileTooLarge", "build_file_scanner", "scan_required", "enforce_scan", "fake_scanner_forbidden",
    "parse_clamd_reply", "parse_signature_age_days", "scanner_health",
]

# The EICAR anti-malware test string (harmless, industry-standard). Used by FakeScanner so CI can prove the reject path without any real malware.
EICAR = (
    b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
)

CHUNK_BYTES = 64 * 1024                       # INSTREAM chunk size
DEFAULT_MAX_STREAM_BYTES = 25 * 1024 * 1024   # clamd's own default StreamMaxLength is 25 MiB
DEFAULT_CONNECT_TIMEOUT = 3.0
DEFAULT_SCAN_TIMEOUT = 30.0                   # total wall-clock deadline for one scan (a slow server cannot hold a request open)
DEFAULT_MAX_SIGNATURE_AGE_DAYS = 3
MAX_REPLY_BYTES = 4096                        # a reply is read up to this many bytes, never more
_SIGNATURE_OK = re.compile(r"[A-Za-z0-9._+\-/]{1,64}")


class ScanStatus(str, Enum):
    CLEAN = "clean"
    INFECTED = "infected"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    TOO_LARGE = "too_large"
    TIMEOUT = "timeout"


OUTAGE_STATUSES = (ScanStatus.UNAVAILABLE.value, ScanStatus.ERROR.value, ScanStatus.TIMEOUT.value)


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    scanner: str          # which scanner ran (so we never claim more than we did)
    detail: str = ""
    status: str = ""      # a ScanStatus value; derived from ``clean`` when not given (legacy constructors)
    signature: str | None = None   # bounded safe signature NAME for an infection; never raw scanner text

    def __post_init__(self) -> None:
        if not self.status:
            object.__setattr__(self, "status", (ScanStatus.CLEAN if self.clean else ScanStatus.INFECTED).value)
        if (self.status == ScanStatus.CLEAN.value) != bool(self.clean):
            raise ValueError("clean and status disagree")


class FileSecurityScanner(Protocol):
    name: str

    def available(self) -> bool:
        ...

    def scan(self, data: bytes, filename: str) -> ScanResult:
        ...


class FileScanUnavailable(RuntimeError):
    """The scan could not be completed (scanner down, timed out, or answered with an error) → fail closed. Never an infection verdict."""

    def __init__(self, message: str = "", status: str = ScanStatus.UNAVAILABLE.value) -> None:
        super().__init__(message)
        self.status = status


class FileRejected(RuntimeError):
    """A scanner ran and flagged the file."""

    def __init__(self, message: str = "", status: str = ScanStatus.INFECTED.value, signature: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.signature = signature


class FileTooLarge(FileRejected):
    """The file exceeds the scan stream limit: it is refused (it was never scanned and is never treated as clean)."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message, status=ScanStatus.TOO_LARGE.value)


class NullScanner:
    """No-op scanner (dev only). ``available`` is True but it performs NO real scanning, so it must never be used where scanning is REQUIRED —
    ``enforce_scan`` treats a NullScanner as 'no real scan ran' and never emits a clean/virus-free claim from it."""

    name = "null"

    def available(self) -> bool:
        return True

    def scan(self, data: bytes, filename: str) -> ScanResult:
        return ScanResult(clean=True, scanner=self.name, detail="no scan performed")


class FakeScanner:
    """DEVELOPMENT SIMULATION: flags the EICAR signature, passes everything else. Not a malware scanner; refused in hosted environments."""

    name = "fake"

    def available(self) -> bool:
        return True

    def scan(self, data: bytes, filename: str) -> ScanResult:
        if EICAR in data:
            return ScanResult(clean=False, scanner=self.name, detail="eicar-test-signature", signature="Eicar-Test-Signature")
        return ScanResult(clean=True, scanner=self.name, detail="no signatures matched")


# ------------------------------------------------------------------ clamd protocol
@dataclass(frozen=True)
class ClamdReply:
    status: ScanStatus
    signature: str | None = None


def parse_clamd_reply(raw: bytes) -> ClamdReply:
    """Parse one clamd INSTREAM reply. Strictly typed; anything unrecognised is ERROR (fail closed). Raw text is never kept."""
    text = raw[:MAX_REPLY_BYTES].replace(b"\x00", b"\n").decode("ascii", "replace").strip()
    if not text or "\n" in text:
        return ClamdReply(ScanStatus.ERROR)          # empty or multi-line: not a single well-formed INSTREAM answer
    if text == "stream: OK":
        return ClamdReply(ScanStatus.CLEAN)
    m = re.fullmatch(r"stream: (.{1,200}) FOUND", text)
    if m:
        name = m.group(1).strip()
        # infected, but only a charset-restricted, bounded name is retained
        return ClamdReply(ScanStatus.INFECTED, name if _SIGNATURE_OK.fullmatch(name) else "unnamed-signature")
    if text.endswith("ERROR"):
        return ClamdReply(ScanStatus.TOO_LARGE if "size limit" in text.lower() else ScanStatus.ERROR)
    return ClamdReply(ScanStatus.ERROR)


def parse_signature_age_days(version_reply: str, *, now: datetime | None = None) -> int | None:
    """``ClamAV 1.0.1/26789/Mon Oct 20 08:00:00 2026`` -> age in whole days of the signature database, or None when it cannot be read."""
    parts = version_reply.strip().strip("\x00").split("/", 2)
    if len(parts) != 3:
        return None
    try:
        built = datetime.strptime(" ".join(parts[2].split()), "%a %b %d %H:%M:%S %Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return max(0, ((now or datetime.now(timezone.utc)) - built).days)


class ClamdClient:
    """Minimal clamd TCP client (PING, VERSION, zINSTREAM). Bounded in time (connect and total deadline), chunk size and stream size. Opens a
    fresh connection per command; importing this module never opens a connection."""

    def __init__(self, host: str, port: int, *, connect_timeout: float = DEFAULT_CONNECT_TIMEOUT, scan_timeout: float = DEFAULT_SCAN_TIMEOUT,
                 max_stream_bytes: int = DEFAULT_MAX_STREAM_BYTES, chunk_bytes: int = CHUNK_BYTES) -> None:
        self._host, self._port = host, port
        self._connect_timeout, self._scan_timeout = connect_timeout, scan_timeout
        self._max_stream = max_stream_bytes
        self._chunk = max(1, min(chunk_bytes, 1024 * 1024))

    def _connect(self, deadline: float) -> socket.socket:
        return socket.create_connection((self._host, self._port), timeout=min(self._connect_timeout, max(0.05, deadline - time.monotonic())))

    @staticmethod
    def _arm(sock: socket.socket, deadline: float) -> None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise socket.timeout("deadline")
        sock.settimeout(remaining)

    def _read_reply(self, sock: socket.socket, deadline: float) -> bytes:
        buf = b""
        while len(buf) < MAX_REPLY_BYTES:
            self._arm(sock, deadline)
            part = sock.recv(MAX_REPLY_BYTES - len(buf))     # partial reads are accumulated
            if not part:
                break
            buf += part
            if b"\x00" in part or b"\n" in part:
                break
        return buf

    def _command(self, command: bytes, timeout: float) -> tuple[ScanStatus, bytes]:
        deadline = time.monotonic() + timeout
        try:
            with self._connect(deadline) as sock:
                self._arm(sock, deadline)
                sock.sendall(command)
                return ScanStatus.CLEAN, self._read_reply(sock, deadline)
        except (socket.timeout, TimeoutError):
            return ScanStatus.TIMEOUT, b""
        except OSError:
            return ScanStatus.UNAVAILABLE, b""

    def ping(self) -> bool:
        status, reply = self._command(b"zPING\x00", self._connect_timeout + 1.0)
        return status is ScanStatus.CLEAN and reply.strip(b"\x00\n ") == b"PONG"

    def version(self) -> str | None:
        status, reply = self._command(b"zVERSION\x00", self._connect_timeout + 1.0)
        if status is not ScanStatus.CLEAN:
            return None
        text = reply.strip(b"\x00\n ").decode("ascii", "replace")
        return text if text.startswith("ClamAV") else None

    def instream(self, data: bytes) -> ClamdReply:
        if len(data) > self._max_stream:
            return ClamdReply(ScanStatus.TOO_LARGE)           # refused locally: never streamed, never treated as clean
        deadline = time.monotonic() + self._scan_timeout
        try:
            with self._connect(deadline) as sock:
                self._arm(sock, deadline)
                sock.sendall(b"zINSTREAM\x00")
                view = memoryview(data)
                for i in range(0, len(data), self._chunk):
                    piece = view[i:i + self._chunk]
                    self._arm(sock, deadline)
                    try:
                        sock.sendall(struct.pack(">I", len(piece)) + piece.tobytes())
                    except (BrokenPipeError, ConnectionResetError):
                        break                                  # clamd may answer early (e.g. size limit); read its reply below
                try:
                    self._arm(sock, deadline)
                    sock.sendall(struct.pack(">I", 0))
                except OSError:
                    pass
                return parse_clamd_reply(self._read_reply(sock, deadline))
        except (socket.timeout, TimeoutError):
            return ClamdReply(ScanStatus.TIMEOUT)
        except OSError:
            return ClamdReply(ScanStatus.UNAVAILABLE)


class ClamAvScanner:
    """Real clamd scanner. A completed scan returns a typed ``ScanResult`` (clean or infected). Every other outcome fails CLOSED: too large raises
    ``FileTooLarge``; unavailable, timeout and error raise ``FileScanUnavailable`` (with the typed status). Clean only when clamd said OK."""

    name = "clamav"

    def __init__(self, host: str, port: int, *, client: ClamdClient | None = None, **client_kwargs) -> None:
        self._client = client or ClamdClient(host, port, **client_kwargs)

    def available(self) -> bool:
        return self._client.ping()

    def health(self, *, max_signature_age_days: int = DEFAULT_MAX_SIGNATURE_AGE_DAYS) -> dict:
        """Safe operational facts: reachable, version string, signature age. Never a host, path or raw reply."""
        reachable = self._client.ping()
        out: dict = {"reachable": reachable, "version": None, "signature_age_days": None, "signatures": "unknown"}
        if reachable:
            v = self._client.version()
            if v:
                out["version"] = v.split("/", 1)[0][:40]
                age = parse_signature_age_days(v)
                out["signature_age_days"] = age
                if age is not None:
                    out["signatures"] = "stale" if age > max_signature_age_days else "fresh"
        return out

    def scan(self, data: bytes, filename: str) -> ScanResult:
        reply = self._client.instream(data)
        if reply.status is ScanStatus.CLEAN:
            return ScanResult(clean=True, scanner=self.name, detail="no signatures matched", status="clean")
        if reply.status is ScanStatus.INFECTED:
            return ScanResult(clean=False, scanner=self.name, detail=reply.signature or "infected", status="infected", signature=reply.signature)
        if reply.status is ScanStatus.TOO_LARGE:
            raise FileTooLarge("The file is too large to be scanned.")
        raise FileScanUnavailable("The malware scanner could not complete the scan.", status=reply.status.value)


def _env_num(name: str, default, cast):
    try:
        v = cast(os.environ.get(name, "") or default)
        return v if v > 0 else default
    except ValueError:
        return default


def build_file_scanner() -> FileSecurityScanner:
    """Select the scanner from env. Default (dev) is NullScanner. ``fake`` is a development simulation; ``clamav`` is the real clamd client."""
    provider = (os.environ.get("FILE_SCAN_PROVIDER", "") or "").strip().lower()
    if provider == "clamav":
        return ClamAvScanner(os.environ.get("CLAMAV_HOST", "127.0.0.1"), _env_num("CLAMAV_PORT", 3310, int),
                             connect_timeout=_env_num("CLAMAV_CONNECT_TIMEOUT_SECONDS", DEFAULT_CONNECT_TIMEOUT, float),
                             scan_timeout=_env_num("CLAMAV_SCAN_TIMEOUT_SECONDS", DEFAULT_SCAN_TIMEOUT, float),
                             max_stream_bytes=_env_num("CLAMAV_MAX_STREAM_BYTES", DEFAULT_MAX_STREAM_BYTES, int))
    if provider == "fake":
        return FakeScanner()
    return NullScanner()


def scanner_health(scanner: FileSecurityScanner | None = None) -> dict:
    """Bounded health for readiness/Admin: reachable plus signature freshness. Never raises."""
    down = {"reachable": False, "version": None, "signature_age_days": None, "signatures": "unknown"}
    try:
        scanner = scanner if scanner is not None else build_file_scanner()
        if hasattr(scanner, "health"):
            return scanner.health(max_signature_age_days=_env_num("CLAMAV_MAX_SIGNATURE_AGE_DAYS", DEFAULT_MAX_SIGNATURE_AGE_DAYS, int))
        return {**down, "reachable": bool(scanner.available())}
    except Exception:  # noqa: BLE001
        return down


def _hosted() -> bool:
    return (os.environ.get("API_ENV", "development") or "development").strip().lower() in ("staging", "production")


def scan_required() -> bool:
    """Whether a real malware scan is REQUIRED before accepting an upload (§17). Always required in staging/production."""
    if _hosted():
        return True
    return (os.environ.get("MALWARE_SCAN_REQUIRED", "") or "").strip().lower() in {"1", "true", "yes", "on"}


def fake_scanner_forbidden(scanner_name: str | None) -> bool:
    """True when a record or result produced by a development-simulation scanner (fake/null) must not be trusted: hosted environments."""
    return _hosted() and (scanner_name or "").strip().lower() in ("fake", "null")


def _real_scanner(scanner: FileSecurityScanner) -> bool:
    """A NullScanner does not count as a real scan, and neither does the fake scanner in a hosted environment."""
    if scanner is None or scanner.name == "null" or fake_scanner_forbidden(scanner.name):
        return False
    return scanner.available()


def enforce_scan(data: bytes, filename: str, *, scanner: FileSecurityScanner | None = None,
                 required: bool | None = None) -> ScanResult:
    """Apply the fail-closed upload policy (§17).

    - required + no real scanner (or the fake/null scanner in a hosted environment) → FileScanUnavailable (503).
    - the scanner is down, times out or errors → FileScanUnavailable (503), never an infection verdict.
    - a real scanner flags the file → FileRejected (422); a file over the scan limit → FileTooLarge (a FileRejected, 413).
    - a real scanner passes → clean ScanResult (the only case that may claim 'scanned').
    - not required + only NullScanner → returns a NullScanner result (never a virus-free claim).
    """
    scanner = scanner if scanner is not None else build_file_scanner()
    require = scan_required() if required is None else required
    if fake_scanner_forbidden(scanner.name):
        raise FileScanUnavailable("A development scanner is not permitted in a hosted environment.")
    if require and not _real_scanner(scanner):
        raise FileScanUnavailable(
            "Malware scanning is required but no scanner is available.")
    result = scanner.scan(data, filename)
    if not result.clean:
        if result.status == ScanStatus.TOO_LARGE.value:
            raise FileTooLarge("The file is too large to be scanned.")
        if result.status in OUTAGE_STATUSES:
            raise FileScanUnavailable("The malware scanner could not complete the scan.", status=result.status)
        raise FileRejected(result.detail or "file failed a security scan", signature=result.signature)
    return result
