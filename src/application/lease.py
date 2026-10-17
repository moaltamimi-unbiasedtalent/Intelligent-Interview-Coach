"""A tiny lease heartbeat (W12.4D-P5-B): renew a lease from a daemon thread while a long, blocking operation runs.

Used by Pack generation (its row) and by quota reservations (their expiry), so recovery means "no sign of life", never "older than N minutes". A failing renewal is
swallowed on purpose (the operation must not die because a heartbeat write failed); if renewals stay broken for longer than the lease the recovery is then legitimate.
Fencing is the caller's job and already exists: finalization is single-use (``WHERE status = 'generating'`` / ``state = 'reserved'``), so a worker that returns after
being recovered can never overwrite or re-finalize anything."""

from __future__ import annotations

import logging
import threading
from typing import Callable

log = logging.getLogger("lease.heartbeat")

__all__ = ["Heartbeat"]


class Heartbeat:
    def __init__(self, beat: Callable[[], object], interval: float) -> None:
        self._beat, self._interval = beat, max(0.01, float(interval))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._beat()
            except Exception:  # noqa: BLE001 - a failed renewal never kills the operation
                log.warning("lease renewal failed")

    def __enter__(self) -> "Heartbeat":
        self._thread = threading.Thread(target=self._run, name="lease-heartbeat", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
