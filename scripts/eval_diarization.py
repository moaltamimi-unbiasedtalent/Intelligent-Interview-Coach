#!/usr/bin/env python
"""Offline contract evaluation for the governed pyannote Community-1 speaker diarization adapter."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tests.conftest  # noqa: E402,F401

from src.speech import policy
from src.speech.audio import live_temp_file_count, secure_tempfile
from src.speech.diarization import FixtureDiarizationEngine, LocalPyannoteEngine, PyannoteCommunityDiarizationService
from src.speech_service import SpeechError

AUTH = lambda: True  # noqa: E731


def raises(fn, category=None):
    try:
        fn()
    except SpeechError as exc:
        return category is None or exc.category == category
    return False


def main() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    wav = None
    import io, wave, struct
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<h", 0) * 16000)
    wav = buf.getvalue()

    check("authorization_constant_false", not policy.DIARIZATION_EXECUTION_AUTHORIZED)
    eng = FixtureDiarizationEngine()
    svc = PyannoteCommunityDiarizationService(eng, authorized=AUTH)
    result = svc.diarize(wav, mime_type="audio/wav")
    check("fixture_contract", result.provider == "pyannote_community_1" and result.speaker_count == 2 and len(result.exclusive_turns) == 2)
    check("not_authorized_runs_nothing", raises(lambda: PyannoteCommunityDiarizationService(FixtureDiarizationEngine()).diarize(wav, mime_type="audio/wav"), "not_authorized"))
    check("local_engine_never_downloads", not LocalPyannoteEngine(str(Path(tempfile.gettempdir()) / "ask4mo-community1-missing")).model_available())
    before = live_temp_file_count()
    with secure_tempfile(b"x"):
        pass
    check("transient_audio_cleanup", live_temp_file_count() == before)

    failed = [name for name, ok, _ in checks if not ok]
    print(f"eval_diarization: {len(checks) - len(failed)}/{len(checks)}")
    for name, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'} {name} {detail}")
    print("RESULT:", "PASS" if not failed else "FAIL")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())