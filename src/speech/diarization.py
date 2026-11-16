"""Governed diarization (pyannote Community-1)."""

from __future__ import annotations

import importlib.util
import multiprocessing
import os
from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Any, Callable, Protocol

from src import constants
from src.speech import policy
from src.speech.audio import TransientAudio, secure_tempfile, validate_and_sniff
from src.speech.engines import EngineError, ModelUnavailable, ProviderNotAuthorized
from src.speech_service import SpeechError

if os.environ.get("PYANNOTE_METRICS_ENABLED") is None:
    os.environ["PYANNOTE_METRICS_ENABLED"] = "0"


__all__ = [
    "DiarizationEngine",
    "DiarizationError",
    "DiarizationTurn",
    "DiarizationResult",
    "DiarizationOutput",
    "FixtureDiarizationEngine",
    "DiarizationFixtureEngine",
    "LocalPyannoteEngine",
    "LocalCommunity1Engine",
    "PyannoteCommunityDiarizationService",
    "SpeakerDiarizationService",
    "Community1DiarizationService",
]


class DiarizationError(Exception):
    pass


@dataclass(frozen=True)
class DiarizationTurn:
    start: float
    end: float
    speaker: str


@dataclass(frozen=True)
class DiarizationResult:
    provider: str
    regular_turns: tuple[DiarizationTurn, ...]
    exclusive_turns: tuple[DiarizationTurn, ...]
    duration_seconds: float | None
    speaker_count: int | None
    deployment: str = ""
    authorized: bool = False


DiarizationOutput = DiarizationResult


class DiarizationEngine(Protocol):
    deployment: str

    def diarize(
        self,
        audio: bytes,
        mime_type: str,
        *,
        num_speakers: int | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> dict[str, Any]:
        ...


def _diarize_in_worker(connection: Any, call: Callable[[], dict[str, Any]]) -> None:
    try:
        connection.send(("ok", call()))
    except ModelUnavailable:
        connection.send(("model_unavailable", None))
    except ProviderNotAuthorized:
        connection.send(("not_authorized", None))
    except Exception:  # noqa: BLE001 - only a bounded status crosses the worker boundary
        connection.send(("provider_error", None))
    finally:
        connection.close()


class DiarizationRunner:
    """Runs inference in a terminable process and holds capacity through cleanup."""

    def __init__(self, max_concurrent: int = 1) -> None:
        self._slots = threading.BoundedSemaphore(max_concurrent)
        self._context = multiprocessing.get_context("fork")

    @staticmethod
    def _stop(process: multiprocessing.Process) -> None:
        if process.is_alive():
            process.terminate()
            process.join(timeout=1)
        if process.is_alive():
            process.kill()
        process.join()

    def _execute(self, call: Callable[[], dict[str, Any]], timeout_seconds: float) -> dict[str, Any]:
        receiver, sender = self._context.Pipe(duplex=False)
        process = self._context.Process(target=_diarize_in_worker, args=(sender, call), daemon=True)
        received: list[tuple[bool, Any]] = []
        read_complete = threading.Event()
        reader: threading.Thread | None = None
        try:
            process.start()
            sender.close()

            def receive() -> None:
                try:
                    received.append((True, receiver.recv()))
                except Exception as exc:  # noqa: BLE001 - only the bounded result crosses the boundary
                    received.append((False, exc))
                finally:
                    read_complete.set()

            reader = threading.Thread(target=receive, name="ask4mo-diarization-result", daemon=True)
            reader.start()
            if not read_complete.wait(timeout_seconds):
                self._stop(process)
                reader.join()
                raise SpeechError("Diarization took too long. Please try again.", category="timeout")
            if not received[0][0]:
                raise SpeechError("Diarization failed.", category="provider_error") from received[0][1]
            status, result = received[0][1]
            process.join(timeout=1)
            if process.is_alive():
                self._stop(process)
                raise SpeechError("Diarization failed.", category="provider_error")
            if status == "model_unavailable":
                raise SpeechError("Diarization is not available right now.", category=status)
            if status == "not_authorized":
                raise SpeechError("Diarization is not available right now.", category=status)
            if status != "ok":
                raise SpeechError("Diarization failed.", category="provider_error")
            return result
        except SpeechError:
            raise
        except Exception as exc:  # noqa: BLE001 - process failures expose only a bounded category
            raise SpeechError("Diarization failed.", category="provider_error") from exc
        finally:
            if process.pid is not None and process.is_alive():
                self._stop(process)
            if reader is not None and reader.is_alive():
                reader.join()
            sender.close()
            receiver.close()

    def run(
        self,
        engine: DiarizationEngine,
        audio: bytes,
        mime_type: str,
        *,
        timeout_seconds: float,
        num_speakers: int | None,
        min_speakers: int,
        max_speakers: int,
    ) -> dict[str, Any]:
        if not self._slots.acquire(blocking=False):
            raise SpeechError("Diarization is busy. Please try again in a moment.", category="busy")
        try:
            path_method = getattr(engine, "diarize_path", None)
            if callable(path_method):
                manager = secure_tempfile(audio, ".audio")
                path = manager.__enter__()
                try:
                    result = self._execute(
                        lambda: path_method(
                            path,
                            mime_type,
                            num_speakers=num_speakers,
                            min_speakers=min_speakers,
                            max_speakers=max_speakers,
                        ),
                        timeout_seconds,
                    )
                finally:
                    manager.__exit__(None, None, None)
                    if path.exists() or path.parent.exists():
                        raise SpeechError("Diarization failed.", category="provider_error")
                return result
            return self._execute(
                lambda: engine.diarize(
                    audio,
                    mime_type,
                    num_speakers=num_speakers,
                    min_speakers=min_speakers,
                    max_speakers=max_speakers,
                ),
                timeout_seconds,
            )
        except SpeechError:
            raise
        except Exception as exc:  # noqa: BLE001 - cleanup and process failures are bounded
            raise SpeechError("Diarization failed.", category="provider_error") from exc
        finally:
            self._slots.release()


class FixtureDiarizationEngine:
    deployment = "fixture"

    def __init__(self, script: Callable[[bytes, str], dict] | None = None) -> None:
        self._script = script or (
            lambda audio, mime_type: {
                "regular": [{"start": 0.2, "end": 1.5, "speaker": "speaker_0"}, {"start": 1.8, "end": 3.9, "speaker": "speaker_1"}],
                "exclusive": [{"start": 0.2, "end": 1.5, "speaker": "speaker_0"}, {"start": 1.8, "end": 3.9, "speaker": "speaker_1"}],
            }
        )
        self.calls = 0

    def diarize(
        self,
        audio: bytes,
        mime_type: str,
        *,
        num_speakers: int | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> dict[str, Any]:
        self.calls += 1
        result = self._script(audio, mime_type) or {}
        return result


DiarizationFixtureEngine = FixtureDiarizationEngine


class LocalPyannoteEngine:
    deployment = "self_hosted"

    def __init__(
        self,
        model_dir: str | None = None,
        *,
        num_speakers: int | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> None:
        self.model_dir = (
            model_dir if model_dir is not None else os.environ.get("SPEECH_DIARIZATION_MODEL_DIR", "")
        )
        self._num_speakers = num_speakers
        self._min_speakers = min_speakers
        self._max_speakers = max_speakers
        self._pipeline = None

    @staticmethod
    def dependency_available() -> bool:
        try:
            return (
                importlib.util.find_spec("pyannote.audio") is not None
                and importlib.util.find_spec("torch") is not None
            )
        except (ImportError, ModuleNotFoundError, ValueError):
            return False

    @staticmethod
    def telemetry_disabled() -> None:
        os.environ["PYANNOTE_METRICS_ENABLED"] = "0"
        try:
            from pyannote.audio.telemetry import set_telemetry_metrics
        except Exception:
            return
        try:
            set_telemetry_metrics(False, save_choice_as_default=True)
        except Exception:
            return

    def model_available(self) -> bool:
        if not self.model_dir:
            return False
        try:
            path = Path(self.model_dir)
            return path.is_dir() and any(path.iterdir())
        except OSError:
            return False

    def _load(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        if not self.dependency_available() or not self.model_available():
            raise ModelUnavailable("pyannote community-1 dependency or operator model directory missing")
        self.telemetry_disabled()
        import torch

        from pyannote.audio import Pipeline

        pipeline = Pipeline.from_pretrained(str(self.model_dir))
        device = os.environ.get("SPEECH_DIARIZATION_DEVICE", "cpu")
        if device and device != "cpu":
            try:
                pipeline.to(torch.device(device))
            except Exception:
                pass
        self._pipeline = pipeline
        return pipeline

    def diarize(
        self,
        audio: bytes,
        mime_type: str,
        *,
        num_speakers: int | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> dict[str, Any]:
        with secure_tempfile(audio, ".audio") as path:
            return self.diarize_path(
                path,
                mime_type,
                num_speakers=num_speakers,
                min_speakers=min_speakers,
                max_speakers=max_speakers,
            )

    def diarize_path(
        self,
        path: str | Path,
        mime_type: str,
        *,
        num_speakers: int | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> dict[str, Any]:
        pipeline = self._load()
        regular: list[dict[str, Any]] = []
        exclusive: list[dict[str, Any]] = []
        outputs = pipeline(
            str(path),
            num_speakers=num_speakers if num_speakers is not None else self._num_speakers,
            min_speakers=min_speakers if min_speakers is not None else self._min_speakers,
            max_speakers=max_speakers if max_speakers is not None else self._max_speakers,
        )
        for turn, speaker in getattr(outputs, "speaker_diarization", []):
            regular.append({"start": float(turn.start), "end": float(turn.end), "speaker": str(speaker)})
        exclusive_output = getattr(outputs, "exclusive_speaker_diarization", None)
        if exclusive_output is None:
            raise EngineError("Exclusive diarization output is unavailable")
        for turn, speaker in exclusive_output:
            exclusive.append({"start": float(turn.start), "end": float(turn.end), "speaker": str(speaker)})
        return {"regular": regular, "exclusive": exclusive}


LocalCommunity1Engine = LocalPyannoteEngine


class PyannoteCommunityDiarizationService:
    provider_name = policy.SELECTED_DIARIZATION_PROVIDER

    def __init__(
        self,
        engine: DiarizationEngine,
        *,
        authorized: Callable[[], bool] | None = None,
        timeout_seconds: float = 300.0,
        runner: DiarizationRunner | None = None,
        max_duration_seconds: int = 7200,
        max_bytes: int = 25 * 1024 * 1024,
        min_speakers: int = 1,
        max_speakers: int = 10,
    ) -> None:
        self._engine = engine
        self._authorized = authorized or (lambda: policy.DIARIZATION_EXECUTION_AUTHORIZED)
        self._timeout = timeout_seconds
        self._runner = runner or DiarizationRunner(1)
        self._max_duration_seconds = max_duration_seconds
        self._max_bytes = max_bytes
        self._min_speakers = min_speakers
        self._max_speakers = max_speakers

    @property
    def is_available(self) -> bool:
        return bool(self._authorized())

    def diarize(
        self,
        data: bytes,
        *,
        mime_type: str,
        num_speakers: int | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
        max_duration_seconds: int | None = None,
    ) -> DiarizationResult:
        if not self._authorized():
            raise SpeechError(
                "Speaker diarization is not available right now.",
                category="not_authorized",
            )
        clean = data or b""
        if not clean:
            raise SpeechError("The recording is empty.", category="empty")
        normalised = (mime_type or "").split(";")[0].strip().lower()
        allowed_mime = constants.SPEECH_ALLOWED_MIME_TYPES
        if normalised not in allowed_mime:
            raise SpeechError("That audio format is not supported for diarization.", category="unsupported_mime")
        if len(clean) > self._max_bytes:
            raise SpeechError("The recording is too large.", category="too_large")
        bound = max_duration_seconds if max_duration_seconds is not None else self._max_duration_seconds
        duration = validate_and_sniff(clean, normalised, max_bytes=self._max_bytes, max_seconds=bound)

        resolved_min = self._min_speakers if min_speakers is None else min_speakers
        resolved_max = self._max_speakers if max_speakers is None else max_speakers
        if resolved_min < 1 or resolved_max < resolved_min or resolved_max > 10:
            raise SpeechError("Invalid speaker count bounds.", category="invalid_bounds")
        if num_speakers is not None and (num_speakers < 1 or num_speakers > 10):
            raise SpeechError("Invalid speaker count.", category="invalid_bounds")

        audio = TransientAudio(bytearray(clean), normalised, duration)
        try:
            out = self._runner.run(
                self._engine,
                audio.view(),
                normalised,
                timeout_seconds=self._timeout,
                num_speakers=num_speakers,
                min_speakers=resolved_min,
                max_speakers=resolved_max,
            )
        finally:
            audio.discard()
        if not isinstance(out, dict):
            raise SpeechError("Diarization failed.", category="provider_error")
        try:
            raw_regular = out["regular"]
            raw_exclusive = out["exclusive"]
            if not isinstance(raw_regular, (list, tuple)) or not isinstance(raw_exclusive, (list, tuple)):
                raise ValueError("invalid turn collection")
            if raw_regular and not raw_exclusive:
                raise ValueError("exclusive turns are required")
            regular = [
                DiarizationTurn(start=float(x.get("start", 0.0)), end=float(x.get("end", 0.0)), speaker=str(x.get("speaker", "unknown")))
                for x in raw_regular
                if isinstance(x, dict)
            ]
            exclusive = [
                DiarizationTurn(start=float(x.get("start", 0.0)), end=float(x.get("end", 0.0)), speaker=str(x.get("speaker", "unknown")))
                for x in raw_exclusive
                if isinstance(x, dict)
            ]
            if len(regular) != len(raw_regular) or len(exclusive) != len(raw_exclusive):
                raise ValueError("invalid turn")
        except Exception as exc:  # noqa: BLE001 - extraction failures are a controlled provider error
            raise SpeechError("Diarization failed.", category="provider_error") from exc
        speakers = {turn.speaker for turn in exclusive}
        return DiarizationResult(
            provider=self.provider_name,
            regular_turns=tuple(turn for turn in regular if turn.end > turn.start + 1e-9),
            exclusive_turns=tuple(turn for turn in exclusive if turn.end > turn.start + 1e-9),
            duration_seconds=round(duration, 2) if duration else None,
            speaker_count=len(speakers) if speakers else None,
            deployment=getattr(self._engine, "deployment", ""),
            authorized=True,
        )


SpeakerDiarizationService = PyannoteCommunityDiarizationService
Community1DiarizationService = PyannoteCommunityDiarizationService
