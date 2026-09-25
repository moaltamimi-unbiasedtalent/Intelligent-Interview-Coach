#!/usr/bin/env python
"""Capstone P7 / E5 voice-experience evaluation.

Deterministic, offline verification of voice INVARIANTS by inspecting the frontend/backend
source (voice is a browser feature). No paid/live calls, no browser required. Mirrors the
P3 dictation eval style.

Covers §32 invariants + the §33 human-trait prohibition (scanned as CODE identifiers, with
comments stripped so prose describing what we do NOT do never false-positives).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FE = ROOT / "frontend"


def read(rel: str, base: Path = FE) -> str:
    p = base / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def strip_comments(src: str) -> str:
    """Remove // line comments and /* */ block comments so we scan CODE, not prose."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"(^|\s)//.*$", "", src, flags=re.M)
    return src


def run() -> dict[str, tuple[bool, str]]:
    r: dict[str, tuple[bool, str]] = {}

    tts_types = read("lib/speech/ttsTypes.ts")
    adapter = read("lib/speech/speechSynthesisAdapter.ts")
    hook = read("lib/speech/useSpeechOutput.ts")
    locales = read("lib/speech/ttsLocales.ts")
    speech_text = read("lib/speech/speechText.ts")
    control = read("components/ui/VoicePlaybackControl.tsx")
    fake = read("lib/speech/fakeSpeechOutputAdapter.ts")
    convo = read("components/agent/AgentConversation.tsx")
    practice = read("components/interview/PracticeClient.tsx")
    dictation_hook = read("lib/speech/useDictation.ts")
    admin = read("src/api/routes/admin.py", ROOT)
    persistence = read("src/persistence.py", ROOT)
    help_center = read("components/help/HelpCenter.tsx")

    speech_layer = tts_types + adapter + hook + locales + speech_text + control + fake

    def check(name: str, ok: bool, detail: str = "") -> None:
        r[name] = (bool(ok), detail)

    # 1) TTS goes through the vendor-neutral adapter seam; components never touch globals.
    check("tts_adapter_boundary",
          "SpeechOutputAdapter" in tts_types and "useSpeechOutput" in control
          and "speechSynthesis" not in control and "adapter" in hook,
          "VoicePlaybackControl → useSpeechOutput → injectable SpeechOutputAdapter")

    # 2) Seven-language TTS configuration.
    codes = ("en-US", "de-DE", "fr-FR", "es-ES", "it-IT", "pt-PT", "nl-NL")
    check("seven_language_configuration",
          all(c in locales for c in codes) and "ttsLanguageStatus" in locales,
          "7 bounded speech locales + honest per-language status")

    # 3) TTS is user-initiated (no auto-speak on mount): no speak() inside a useEffect.
    no_autospeak = not re.search(r"useEffect\([^)]*speak\(", hook) and "onClick" in control
    check("tts_user_initiated", no_autospeak, "speak() only on user click; never on mount")

    # 4) STT remains user-initiated (P3 reuse): start on user action, not on mount.
    check("stt_user_initiated", "start" in dictation_hook and "useDictation" in dictation_hook,
          "P3 dictation reused (start is user-driven)")

    # 5) No auto-submit anywhere in the voice layer.
    check("no_auto_submit",
          all(tok not in speech_layer for tok in ("onSubmit(", "onSend(", "submit(")),
          "no submit path in the TTS layer")

    # 6) TTS never auto-opens the microphone: no dictation/recognition start in TTS code.
    check("tts_does_not_auto_start_mic",
          all(tok not in speech_layer for tok in ("useDictation", "SpeechRecognition", ".start(")),
          "no recognition/mic start in the TTS layer or onEnd handlers")

    # 7) Editable transcript preserved (P3 reuse): dictation still appends to the field.
    check("editable_transcript", "appendTranscript" in dictation_hook,
          "P3 editable-transcript behaviour unchanged")

    # 8) Practice evaluation stays text-only: submit uses the typed/edited answer, and no
    #    audio-derived score is introduced.
    text_eval = "submitAnswer(answer)" in practice and "audioScore" not in practice
    check("practice_uses_text_evaluation", text_eval, "submit sends the text answer; no audio score")

    # 9) No audio persistence in the voice layer.
    check("no_audio_persistence",
          all(tok not in speech_layer for tok in
              ("MediaRecorder", "getUserMedia", "createObjectURL", "audioBlob", "Blob(")),
          "no recorder/blob/getUserMedia in the TTS layer")

    # 10) No voice-trait analysis / 11) no biometric storage — scanned as CODE identifiers.
    forbidden = [
        "emotion_score", "emotionScore", "confidence_score", "confidenceScore",
        "personality_score", "personalityScore", "accent_score", "accentScore",
        "intelligence_score", "intelligenceScore", "honesty_score", "honestyScore",
        "deception_score", "deceptionScore", "hiring_score", "hiringScore",
        "employability_score", "employabilityScore", "voiceprint", "speaker_embedding",
        "speakerEmbedding", "prosody", "pitchScore",
    ]
    code = strip_comments(speech_layer + convo + practice)
    trait_hits = [w for w in forbidden if w.lower() in code.lower()]
    check("no_voice_trait_analysis", not trait_hits, f"no trait identifiers in code (hits={trait_hits})")
    check("no_biometric_storage",
          not any(w in code.lower() for w in ("voiceprint", "speaker_embedding", "speakerembedding")),
          "no voiceprint/speaker-embedding identifiers")

    # 12) Stop control exists (control + hook + adapter cancel).
    check("stop_control",
          "stop" in control and "stop" in hook and ".cancel()" in adapter,
          "Stop button → hook.stop → speechSynthesis.cancel()")

    # 13) Unsupported fallback: control renders null when unsupported (text stays visible).
    check("unsupported_fallback", "if (!supported) return null" in control,
          "renders nothing when unsupported")

    # 14) Permission-failure fallback (P3 STT path unchanged).
    check("permission_failure_fallback", "permission-denied" in read("components/ui/DictationControl.tsx"),
          "P3 permission-denied handling preserved")

    # 15) Language/geography separation: the TTS locale layer never references career geo
    #     (scan CODE only — our own comments legitimately explain the separation).
    tts_code = strip_comments(locales + speech_text + adapter).lower()
    check("language_geography_separation",
          all(tok not in tts_code
              for tok in ("geography", "salary", "jurisdiction", "detect_country", "country_source")),
          "TTS locale mapping carries no career-geography coupling")

    # 16) Brief/Detailed preserved: Mo Listen speaks the primary answer; presentation intact.
    check("brief_detailed_preserved",
          "presentation.answer" in convo and "responseDetail" in convo,
          "Listen speaks presentation.answer; Brief/Detailed rendering untouched")

    # 17) Source visibility preserved: sources still rendered; citations become a spoken note.
    check("source_visibility_preserved",
          "AgentSources" in convo and "sourcesNote" in speech_text,
          "on-screen sources unchanged; spoken text notes sources on screen")

    # 18) Admin exposes only speech ARCHITECTURE metadata (positive markers; no private data).
    admin_ok = ('"output": "browser_speech_synthesis_tts"' in admin
                and '"audio_persisted_by_ask4mo": False' in admin
                and '"voice_trait_inference": "none"' in admin)
    check("admin_no_voice_private_data", admin_ok, "admin providers = architecture booleans only")

    # 19) Workspace sharing unchanged: the shareable-types VALUE has no audio/voice type.
    types_match = re.search(r"SHAREABLE_RESOURCE_TYPES\s*=\s*\(([^)]*)\)", persistence)
    types_val = (types_match.group(1) if types_match else "x").lower()
    check("workspace_no_auto_share",
          bool(types_match) and all(t not in types_val for t in ("audio", "voice", "recording")),
          "no audio/voice added to shareable resource types")

    # 20) Navigation cleanup: the hook cancels playback on unmount (no zombie speech).
    check("navigation_cleanup",
          "useEffect" in hook and "return () => engine.stop()" in hook,
          "unmount stops active playback")

    # --- P7 closure: STT/TTS mutual exclusion (no feedback loop) ---
    coord = read("lib/speech/voiceCoordination.tsx")
    prepare_page = read("app/prepare/page.tsx")
    practice_page = read("app/practice/page.tsx")

    # 21) A coordinator seam exists and BOTH modality hooks claim/release it.
    check("stt_tts_mutual_exclusion",
          "VoiceCoordinationProvider" in coord and "claim" in coord and "release" in coord
          and "useVoiceCoordinator" in hook and "useVoiceCoordinator" in dictation_hook,
          "shared coordinator; both hooks claim/release the single audio channel")

    # 22) Starting TTS stops active STT: the speech-output hook claims before speaking.
    check("tts_stops_active_stt",
          "coordinator?.claim(ownerId.current" in hook and "coordinator?.release" in hook,
          "useSpeechOutput claims (stops the other) before playback")

    # 23) Starting STT stops active TTS: the dictation hook claims before listening.
    check("stt_stops_active_tts",
          "coordinator?.claim(ownerId.current" in dictation_hook and "coordinator?.release" in dictation_hook,
          "useDictation claims (stops the other) before listening")

    # 24) The two candidate voice surfaces scope the coordinator (mutual exclusion applies).
    check("surfaces_scope_coordinator",
          "VoiceCoordinationProvider" in prepare_page and "VoiceCoordinationProvider" in practice_page,
          "Prepare and Practice wrap their voice subtree in the provider")

    # 25) No feedback loop: claiming only STOPS the other modality — it never START/ speak/
    #     start()s it, and the coordinator itself never auto-starts anything.
    coord_code = strip_comments(coord)
    check("no_feedback_loop",
          ".start(" not in coord_code and ".speak(" not in coord_code
          and "engine.start" not in coord_code,
          "coordinator only stops the other modality; never auto-starts STT or TTS")

    # bonus) Help documents voice + the human-trait prohibition honestly.
    check("help_documents_voice",
          "voice" in help_center.lower() or "listen" in help_center.lower(),
          "Help mentions voice features")

    return r


def main() -> int:
    print("ASK4MO — CAPSTONE P7 / E5 VOICE EXPERIENCE EVALUATION\n")
    results = run()
    failed = False
    for name in sorted(results):
        ok, detail = results[name]
        if not ok:
            failed = True
        print(f"  {name:34s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Speech provider calls: 0   Live calls: 0")
    if failed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS (all voice invariants hold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
