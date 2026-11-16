from __future__ import annotations

import multiprocessing
from pathlib import Path
import time

import pytest

from src.speech.audio import live_temp_file_count
from src.speech.diarization import (
    DiarizationRunner,
    FixtureDiarizationEngine,
    PyannoteCommunityDiarizationService,
)
from src.speech.runtime import fixture_wav
from src.speech_service import SpeechError


def _service(engine, **kwargs):
    return PyannoteCommunityDiarizationService(engine, authorized=lambda: True, **kwargs)


def test_timeout_terminates_the_worker_and_cleans_parent_owned_audio():
    context = multiprocessing.get_context("fork")
    started = context.Event()
    paths = context.Queue()

    class SlowPathEngine:
        deployment = "fixture"

        def diarize(self, audio, mime_type, **kwargs):
            raise AssertionError("path execution should be used")

        def diarize_path(self, path, mime_type, **kwargs):
            paths.put(str(path))
            started.set()
            time.sleep(30)

    runner = DiarizationRunner(1)
    service = _service(SlowPathEngine(), timeout_seconds=0.1, runner=runner)
    before = live_temp_file_count()
    with pytest.raises(SpeechError) as error:
        service.diarize(fixture_wav(), mime_type="audio/wav")

    assert error.value.category == "timeout"
    assert started.is_set()
    path = Path(paths.get(timeout=1))
    assert not path.exists() and not path.parent.exists()
    assert live_temp_file_count() == before
    assert _service(FixtureDiarizationEngine(), runner=runner).diarize(
        fixture_wav(), mime_type="audio/wav"
    ).exclusive_turns
    paths.close()


@pytest.mark.parametrize(
    "output",
    [
        {"regular": [{"start": 0.1, "end": 0.4, "speaker": "speaker_0"}]},
        {"regular": [{"start": "invalid", "end": 0.4, "speaker": "speaker_0"}], "exclusive": []},
    ],
)
def test_nonempty_regular_output_without_valid_exclusive_turns_is_a_provider_error(output):
    service = _service(FixtureDiarizationEngine(lambda audio, mime: output))
    with pytest.raises(SpeechError) as error:
        service.diarize(fixture_wav(), mime_type="audio/wav")
    assert error.value.category == "provider_error"


def test_both_empty_diarization_outputs_are_valid():
    result = _service(
        FixtureDiarizationEngine(lambda audio, mime: {"regular": [], "exclusive": []})
    ).diarize(fixture_wav(), mime_type="audio/wav")
    assert result.regular_turns == () and result.exclusive_turns == ()
    assert result.speaker_count is None


@pytest.mark.parametrize(
    "mime_type",
    ["audio/flac", "audio/aac", "audio/mp3", "audio/x-m4a", "application/octet-stream"],
)
def test_formats_outside_the_shared_validator_allowlist_are_rejected(mime_type):
    with pytest.raises(SpeechError) as error:
        _service(FixtureDiarizationEngine()).diarize(fixture_wav(), mime_type=mime_type)
    assert error.value.category == "unsupported_mime"


def test_configured_byte_limit_is_forwarded_to_shared_validation():
    default_limit = 25 * 1024 * 1024
    configured_limit = 26 * 1024 * 1024
    wav = fixture_wav()
    data = wav + b"\x00" * (default_limit + 1 - len(wav))
    service = _service(FixtureDiarizationEngine(), max_bytes=configured_limit)
    result = service.diarize(data, mime_type="audio/wav")
    assert result.exclusive_turns
