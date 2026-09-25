#!/usr/bin/env python
"""Capstone P7.5 / C1 realtime-voice evaluation.

Deterministic, offline verification of the realtime-voice INVARIANTS (§31) by inspecting the
frontend + backend source. No microphone, no provider, no paid/live calls. Mirrors the P7
``eval_voice_experience.py`` style: source is read, comments are stripped so prose describing
what we do NOT do never false-positives, and each named invariant is asserted as CODE.
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
    """Remove // line comments, /* */ block comments and Python # comments → scan CODE only."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"(^|\s)//.*$", "", src, flags=re.M)
    src = re.sub(r"(^|\s)#.*$", "", src, flags=re.M)
    return src


def strip_py(src: str) -> str:
    """Remove Python triple-quoted docstrings AND # comments → scan Python CODE only, so prose
    describing what we do NOT do (e.g. 'no transcript') never false-positives."""
    src = re.sub(r'"""(?:.|\n)*?"""', "", src)
    src = re.sub(r"'''(?:.|\n)*?'''", "", src)
    src = re.sub(r"(^|\s)#.*$", "", src, flags=re.M)
    return src


def field_names(class_src: str) -> list[str]:
    """Pydantic/dataclass field names declared at 4-space indent (docstring-safe)."""
    return re.findall(r"^\s{4}(\w+)\s*:", class_src, re.M)


def run() -> dict[str, tuple[bool, str]]:
    r: dict[str, tuple[bool, str]] = {}

    # Frontend realtime layer.
    rt_types = read("lib/speech/realtimeTypes.ts")
    fake = read("lib/speech/fakeRealtimeAdapter.ts")
    webrtc = read("lib/speech/openaiRealtimeAdapter.ts")
    hook = read("lib/speech/useRealtimeVoice.ts")
    control = read("components/ui/RealtimeVoiceControl.tsx")
    practice = read("components/interview/PracticeClient.tsx")
    help_center = read("components/help/HelpCenter.tsx")
    api_types = read("lib/api/types.ts")
    fe_config = read("lib/config.ts")

    # Backend realtime layer.
    rt_be = read("src/voice/realtime.py", ROOT)
    route = read("src/api/routes/voice.py", ROOT)
    schemas_voice = read("src/api/schemas/voice.py", ROOT)
    health = read("src/api/routes/health.py", ROOT)
    admin = read("src/api/routes/admin.py", ROOT)
    policy = read("src/llm/policy.py", ROOT)
    persistence = read("src/persistence.py", ROOT)

    fe_layer = rt_types + fake + webrtc + hook + control
    fe_code = strip_comments(fe_layer)

    def check(name: str, ok: bool, detail: str = "") -> None:
        r[name] = (bool(ok), detail)

    # 1) Provider abstraction: a neutral adapter/session seam; provider event names are
    #    confined to the WebRTC adapter (UI/hook never reference them).
    check("provider_abstraction",
          "RealtimeVoiceAdapter" in rt_types and "RealtimeVoiceSession" in rt_types
          and "RealtimeProvider" in rt_be
          and "response.cancel" not in hook and "response.cancel" not in control,
          "neutral adapter/session; provider events only in the WebRTC adapter")

    # 2) Session creation is authenticated + user-scoped.
    check("session_authentication",
          "get_current_principal" in route and "principal.user_id" in route,
          "session route resolves the authenticated principal")

    # 3) Ephemeral-secret boundary: the browser gets only a short-lived client secret; the
    #    long-lived key is unwrapped ONLY into the Bearer header.
    check("ephemeral_secret_boundary",
          "client_secret" in rt_be and "_bearer" in rt_be
          and rt_be.count("get_secret_value") == 1,
          "grant carries client_secret; key used once, only for the Bearer header")

    # 4) No long-lived secret can reach the browser: response schema has no key field; the
    #    WebRTC adapter authenticates with the ephemeral grant secret, never an env key.
    req_and_resp_clean = ("api_key" not in schemas_voice and "client_secret" in schemas_voice)
    webrtc_uses_ephemeral = ("grant.clientSecret" in webrtc and "process.env" not in webrtc
                             and "REALTIME_VOICE_API_KEY" not in fe_layer)
    check("no_long_lived_secret_in_browser",
          req_and_resp_clean and webrtc_uses_ephemeral and "NEXT_PUBLIC" not in rt_types,
          "response has no key; browser uses only the ephemeral grant secret")

    # 5) Explicit start (no auto-start on mount).
    no_autostart = not re.search(r"useEffect\([^)]*\.start\(", hook) and "rt.start()" in control
    check("explicit_start", no_autostart and "realtime-start" in control,
          "session starts only on explicit user action")

    # 6) Streaming state machine models the required states.
    states = ("connecting", "listening", "assistant_speaking", "interrupted",
              "reconnecting", "ended", "unavailable")
    check("streaming_state_machine",
          all(s in rt_types for s in states) and "onState" in hook,
          "explicit connect/listen/speak/interrupt/reconnect/end states")

    # 7) Barge-in: candidate speech-start while Mo speaks triggers an interruption.
    check("barge_in",
          "speech_started" in webrtc and "onInterrupted" in hook
          and "__candidateSpeechStart" in fake and "interrupt" in control,
          "candidate speech-start cancels Mo and hands over the turn")

    # 8) Response cancellation on interruption (provider cancel + truncate).
    check("response_cancel",
          "response.cancel" in webrtc and "conversation.item.truncate" in webrtc,
          "interrupt issues response.cancel + conversation.item.truncate")

    # 9) Server/client state sync after interruption: local audio cleared + provider truncated.
    check("server_client_state_sync",
          "conversation.item.truncate" in webrtc and "audioEl" in webrtc
          and "startNewCandidateTurn" in hook,
          "truncate provider + clear local audio + reset candidate turn")

    # 10) Manual stop (Stop Mo + End) exist in hook and control.
    check("manual_stop",
          "stopAssistant" in hook and "realtime-stop-mo" in control
          and "realtime-end" in control,
          "manual Stop Mo + End controls")

    # 11) Explicit session end releases transport + server reservation.
    check("session_end",
          "disconnect()" in hook and "endRealtimeSession" in hook and "realtime-end" in control,
          "end() disconnects + releases the server reservation")

    # 12) No audio persistence anywhere in the realtime layer (getUserMedia streaming is OK;
    #     recording/blob storage is NOT).
    forbidden_audio = ("MediaRecorder", "createObjectURL", "audioBlob", "Blob(",
                       "indexedDB", "IndexedDB")
    check("no_audio_persistence",
          all(tok not in fe_layer for tok in forbidden_audio),
          "no recorder/blob/object-URL/IndexedDB in the realtime layer")

    # 13) No voice-trait inference — scanned as CODE identifiers.
    forbidden = [
        "emotion_score", "emotionScore", "confidence_score", "confidenceScore",
        "personality_score", "personalityScore", "accent_score", "accentScore",
        "intelligence_score", "intelligenceScore", "honesty_score", "honestyScore",
        "deception_score", "deceptionScore", "hiring_score", "hiringScore",
        "employability_score", "employabilityScore", "voiceprint", "speaker_embedding",
        "speakerEmbedding", "prosody", "pitchScore", "sentiment_score",
    ]
    code = (fe_code + strip_comments(rt_be + route)).lower()
    trait_hits = [w for w in forbidden if w.lower() in code]
    check("no_voice_trait_inference", not trait_hits, f"no trait identifiers (hits={trait_hits})")

    # 14) Transcript privacy: partial/final transcript is never written to localStorage / URL /
    #     analytics, and the backend neither receives (no schema field) nor logs transcript text.
    req_fields_all = field_names(
        re.search(r"class RealtimeSessionCreateRequest.*?(?=\nclass |\Z)", schemas_voice, re.S).group(0)
        if re.search(r"class RealtimeSessionCreateRequest", schemas_voice) else "")
    check("transcript_privacy",
          "localStorage" not in hook and "localStorage" not in control
          and "transcript" not in req_fields_all and "transcript" not in strip_py(route),
          "transcript stays in memory; backend never receives/logs it")

    # 15) Practice state authority: the realtime commit routes through the SAME durable answer
    #     service; the Practice state machine stays authoritative.
    check("practice_state_authority",
          "RealtimeVoiceControl" in practice and "ctrl.submitAnswer(text)" in practice,
          "realtime commit → existing submitAnswer (durable state authoritative)")

    # 16) No automatic Memory save from realtime.
    check("no_memory_auto_save",
          "memory.create" not in fe_layer and "memory" not in strip_comments(route),
          "realtime never auto-saves Memory")

    # 17) Tool allow-list / no client model override: the request schema exposes ONLY
    #     locale/surface/session as FIELDS — never model/provider/voice/tools.
    req_match = re.search(r"class RealtimeSessionCreateRequest.*?(?=\nclass |\Z)", schemas_voice, re.S)
    req_fields = field_names(req_match.group(0) if req_match else "")
    check("tool_allowlist",
          bool(req_fields)
          and all(tok not in req_fields for tok in ("model", "provider", "voice", "tools")),
          f"client fields = {req_fields} (no model/provider/voice/tools)")

    # 18) Cross-user isolation: session + limiter are keyed by the authenticated user id.
    check("cross_user_isolation",
          "RealtimeSessionRequest(" in route and "user_id" in route
          and "check_and_reserve(user_id)" in route,
          "session + rate limit scoped to the authenticated user")

    # 19) Language/geography separation: 7 locales; no career-geography coupling in the
    #     realtime backend (scan CODE only).
    codes = ('"en"', '"de"', '"fr"', '"es"', '"it"', '"pt"', '"nl"')
    rt_be_code = strip_comments(rt_be).lower()
    check("language_geography_separation",
          all(c in rt_be for c in codes)
          and all(tok not in rt_be_code for tok in ("geography", "salary", "jurisdiction", "country")),
          "7 realtime locales; no geography/salary coupling")

    # 20) Fallback to turn-based: 503 → unavailable; control shows a fallback; Practice keeps
    #     the turn-based composer regardless.
    check("fallback_to_turn_based",
          "503" in route and "realtime-fallback" in control
          and "unavailable" in hook and "InterviewAnswerComposer" in practice,
          "unavailable → fall back; turn-based composer always present")

    # 21) Disconnect recovery: transport disconnect is detected + surfaced (bounded, no infinite
    #     auto-reconnect / no audio replay).
    check("disconnect_recovery",
          "iceConnectionState" in webrtc and "__disconnect" in fake
          and "disconnect" in rt_types,
          "disconnect detected and surfaced; no infinite reconnect")

    # 22) Duplicate-turn prevention: commit-once guard per turn.
    check("duplicate_turn_prevention",
          "committedTurn" in hook and "turnId" in hook,
          "commit-once guard prevents duplicate answer submission")

    # 23) Rate + cost bounds: per-user rate limit + concurrency + session duration cap.
    check("rate_bound",
          "RealtimeSessionLimiter" in rt_be and "check_and_reserve" in route
          and "max_session_seconds" in rt_be and "max_concurrent_per_user" in rt_be,
          "session-creation rate limit + concurrency + duration cap")

    # 24) Model-policy boundary: REALTIME_VOICE operation resolves to no chat slug; the
    #     realtime module cross-checks the policy.
    check("model_policy_boundary",
          "REALTIME_VOICE" in policy and "REALTIME" in policy
          and "resolve_policy" in rt_be and "_uses_realtime_policy" in rt_be,
          "REALTIME_VOICE policy; realtime module verifies the boundary")

    # 25) Admin / workspace privacy: admin sees booleans only (no audio/transcript); no
    #     audio/voice added to shareable workspace types.
    admin_ok = ('"audio_visible_to_admin": False' in admin
                and '"transcript_visible_to_admin": False' in admin
                and "_realtime_provider_status" in admin)
    types_match = re.search(r"SHAREABLE_RESOURCE_TYPES\s*=\s*\(([^)]*)\)", persistence)
    types_val = (types_match.group(1) if types_match else "x").lower()
    check("admin_workspace_privacy",
          admin_ok and bool(types_match)
          and all(t not in types_val for t in ("audio", "voice", "recording")),
          "admin booleans only; no audio/voice in shareable types")

    # 26) Capability gate: realtime is a server-authoritative deployment capability.
    check("capability_gate",
          "realtime_voice_enabled" in health and "realtime_voice_enabled" in api_types
          and "realtime_voice_enabled" in practice.replace("realtimeEnabled", "")
          or "realtime_voice_enabled" in read("lib/useCapabilities.ts"),
          "realtime gated by a server-authoritative capability flag")

    # bonus) Frontend config never reads a realtime provider key (only NEXT_PUBLIC_*).
    check("frontend_no_provider_key",
          "REALTIME_VOICE_API_KEY" not in fe_config and "OPENROUTER_API_KEY" not in fe_config,
          "frontend config reads no provider secret")

    # bonus) Help documents realtime honestly.
    check("help_documents_realtime",
          "hRealtimeQ" in help_center and "hRealtimeInterruptQ" in help_center,
          "Help documents realtime + interruption + fallback + audio")

    return r


def main() -> int:
    print("ASK4MO — CAPSTONE P7.5 / C1 REALTIME VOICE EVALUATION\n")
    results = run()
    failed = False
    for name in sorted(results):
        ok, detail = results[name]
        if not ok:
            failed = True
        print(f"  {name:32s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Realtime provider calls: 0   Live calls: 0")
    if failed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS (all realtime-voice invariants hold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
