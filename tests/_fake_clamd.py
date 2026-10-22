"""A fake clamd for tests: a real TCP server on 127.0.0.1 with an EPHEMERAL port that speaks the clamd zINSTREAM / PING / VERSION protocol.

It is test harness code only: no real clamd, no docker, no network beyond loopback. The EICAR test string is built at runtime in memory from two
fragments so the complete signature is never written to disk or committed whole by this module (the repository's own ``EICAR`` constant in
``src.documents.file_security`` is the pre-existing production constant for the development simulation).
"""

from __future__ import annotations

import socket
import struct
import threading
import time

_A = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR"
_B = "-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def eicar_bytes() -> bytes:
    """The standard EICAR test string, assembled in memory only."""
    return (_A + _B).encode("ascii")


DEFAULT_VERSION = "ClamAV 1.0.1/27000/Mon Oct 19 08:00:00 2026"


class FakeClamd:
    """``mode``: clean | auto | refuse | timeout | slow | partial | malformed | error | empty | size_limit | multiline | closed_early.

    ``auto`` (default): INSTREAM is scanned for the EICAR fragments and answered FOUND/OK.
    """

    def __init__(self, mode: str = "auto", *, version: str = DEFAULT_VERSION, signature: str = "Win.Test.EICAR_HDB-1", max_stream: int = 25 * 1024 * 1024):
        self.mode, self.version, self.signature, self.max_stream = mode, version, signature, max_stream
        self.received: list[int] = []        # total INSTREAM bytes received per connection
        self.commands: list[bytes] = []
        self.chunks_seen: list[int] = []
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(8)
        self._srv.settimeout(0.2)
        self.port = self._srv.getsockname()[1]
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._t = threading.Thread(target=self._loop, daemon=True)

    # lifecycle
    def start(self) -> "FakeClamd":
        self._t.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._t.join(timeout=2)
        try:
            self._srv.close()
        except OSError:
            pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *a):
        self.stop()

    # server
    def _loop(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._srv.accept()
            except (socket.timeout, OSError):
                continue
            t = threading.Thread(target=self._handle, args=(conn,), daemon=True)
            t.start()
            self._threads.append(t)

    @staticmethod
    def _read_exact(conn, n):
        buf = b""
        while len(buf) < n:
            part = conn.recv(n - len(buf))
            if not part:
                raise ConnectionError("closed")
            buf += part
        return buf

    def _handle(self, conn):
        conn.settimeout(10)
        try:
            cmd = b""
            while not cmd.endswith(b"\x00") and not cmd.endswith(b"\n"):
                part = conn.recv(1)
                if not part:
                    return
                cmd += part
            self.commands.append(cmd)
            if cmd.strip(b"\x00\n") == b"PING" or cmd == b"zPING\x00":
                conn.sendall(b"PONG\x00")
            elif b"VERSION" in cmd:
                conn.sendall(self.version.encode() + b"\x00")
            elif b"INSTREAM" in cmd:
                self._instream(conn)
        except (OSError, ConnectionError):
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _instream(self, conn):
        mode = self.mode
        if mode == "timeout":
            time.sleep(3)                      # never answers within the client's deadline
            return
        data = b""
        total = 0
        while True:
            size = struct.unpack(">I", self._read_exact(conn, 4))[0]
            if size == 0:
                break
            self.chunks_seen.append(size)
            chunk = self._read_exact(conn, size)
            total += size
            if mode == "size_limit" and total > self.max_stream:
                conn.sendall(b"INSTREAM size limit exceeded. ERROR\x00")
                return
            data += chunk
        self.received.append(total)
        if mode == "slow":
            time.sleep(1.2)
        if mode == "closed_early":
            return
        if mode == "error":
            conn.sendall(b"lstat() failed: No such file or directory. ERROR\x00")
        elif mode == "empty":
            return
        elif mode == "malformed":
            conn.sendall(b"stream: banana\x00")
        elif mode == "multiline":
            conn.sendall(b"stream: OK\nstream: OK\x00")
        elif mode == "partial":
            reply = b"stream: OK\x00" if eicar_bytes() not in data else f"stream: {self.signature} FOUND\x00".encode()
            for i in range(len(reply)):
                conn.sendall(reply[i:i + 1])    # one byte at a time
                time.sleep(0.005)
        elif mode == "clean" or eicar_bytes() not in data:
            conn.sendall(b"stream: OK\x00")
        else:
            conn.sendall(f"stream: {self.signature} FOUND\x00".encode())
