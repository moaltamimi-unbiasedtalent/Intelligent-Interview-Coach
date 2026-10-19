"""Shared engine plumbing for the governed speech adapters (W12.4E): controlled exceptions, bounded concurrency and a hard timeout.

An engine is the thing that actually runs inference (a local model, or a hosted API transport). The adapters never call one unless policy authorises it, translate every engine failure into a
``SpeechError`` CATEGORY (never the raw exception text, which could carry content), and bound concurrent use so a burst cannot exhaust the host.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Callable, TypeVar

from src.speech_service import SpeechError

__all__ = ["ModelUnavailable", "ProviderNotAuthorized", "EngineError", "BoundedRunner"]

T = TypeVar("T")


class ModelUnavailable(Exception):
    """The weights or a dependency are not present. Never triggers a download."""


class ProviderNotAuthorized(Exception):
    """Server speech execution is not authorized (a code constant), so nothing ran."""


class EngineError(Exception):
    """The engine failed while running (a crash or an unusable result)."""


class BoundedRunner:
    """Runs one engine call with a hard wall-clock timeout and at most ``max_concurrent`` calls in flight. A request over the bound is refused immediately (``busy``), not queued."""

    def __init__(self, max_concurrent: int = 2) -> None:
        self._slots = threading.BoundedSemaphore(max_concurrent)
        self._pool = ThreadPoolExecutor(max_workers=max_concurrent, thread_name_prefix="ask4mo-speech")
        self.max_concurrent = max_concurrent

    def run(self, fn: Callable[[], T], *, timeout_seconds: float) -> T:
        if not self._slots.acquire(blocking=False):
            raise SpeechError("Speech is busy. Please try again in a moment.", category="busy")
        future = self._pool.submit(fn)
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeout as exc:
            future.cancel()
            raise SpeechError("Speech took too long. Please try again.", category="timeout") from exc
        except ModelUnavailable as exc:
            raise SpeechError("Speech is not available right now.", category="model_unavailable") from exc
        except ProviderNotAuthorized as exc:
            raise SpeechError("Speech is not available right now.", category="not_authorized") from exc
        except SpeechError:
            raise
        except Exception as exc:  # noqa: BLE001 - category only: the exception text may carry content
            raise SpeechError("Speech failed. Please try again.", category="provider_error") from exc
        finally:
            self._slots.release()
