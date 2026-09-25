"""Capstone P7/E5 voice experience — deterministic invariant gate + human-trait prohibition.

Runs the offline voice evaluation (source-scanning) and asserts the whole invariant set
passes, including the §33 prohibition on any voice-based human-trait inference. No browser,
no paid/live calls.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_voice_experience_eval_gate_passes():
    r = subprocess.run([sys.executable, "scripts/eval_voice_experience.py"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


def test_no_voice_trait_inference_identifiers_in_speech_layer():
    """Belt-and-braces: forbidden human-trait identifiers never appear as CODE in the voice
    layer (comments stripped so prose describing what we do NOT do is allowed)."""
    import re

    fe = ROOT / "frontend"
    files = [
        "lib/speech/ttsTypes.ts", "lib/speech/speechSynthesisAdapter.ts",
        "lib/speech/useSpeechOutput.ts", "lib/speech/ttsLocales.ts",
        "lib/speech/speechText.ts", "components/ui/VoicePlaybackControl.tsx",
        "lib/speech/fakeSpeechOutputAdapter.ts",
    ]
    forbidden = [
        "emotionscore", "confidencescore", "personalityscore", "accentscore",
        "intelligencescore", "honestyscore", "deceptionscore", "hiringscore",
        "employabilityscore", "voiceprint", "speaker_embedding", "speakerembedding",
    ]
    for rel in files:
        src = (fe / rel).read_text(encoding="utf-8")
        src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        src = re.sub(r"(^|\s)//.*$", "", src, flags=re.M)
        low = src.lower()
        for term in forbidden:
            assert term not in low, f"{rel} contains forbidden trait identifier '{term}'"
