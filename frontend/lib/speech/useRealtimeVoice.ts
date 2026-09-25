"use client";

// useRealtimeVoice — the realtime voice session state machine (Capstone P7.5, C1).
//
// Owns: explicit start/end, the connect→ready→listening/assistant_speaking→interrupted state
// machine, evolving partial/final transcripts, barge-in, manual stop, commit-ONCE of the
// final candidate transcript through the caller's contract, coordinator claim/release for the
// WHOLE session (so realtime and P7 STT/TTS never run together), and clean fallback on any
// failure. It fetches the grant from the server (never a long-lived key) and holds no audio.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/errors";
import { api } from "../api/client";
import { openAiRealtimeAdapter } from "./openaiRealtimeAdapter";
import type {
  RealtimeErrorKind,
  RealtimeVoiceAdapter,
  RealtimeVoiceSession,
  RealtimeVoiceState,
} from "./realtimeTypes";
import { useVoiceCoordinator } from "./voiceCoordination";

export interface UseRealtimeVoiceOptions {
  adapter?: RealtimeVoiceAdapter;
  locale?: string;
  surface?: "practice" | "prepare";
  interviewSessionId?: string | null;
  // Commit contract: called at most ONCE per candidate turn with the final transcript. The
  // caller (e.g. Practice) routes it through the existing application answer service.
  onCommit?: (text: string) => void | Promise<void>;
}

export interface UseRealtimeVoice {
  supported: boolean;
  state: RealtimeVoiceState;
  active: boolean;
  error: RealtimeErrorKind | null;
  assistantTranscript: string;
  candidateTranscript: string;
  candidateFinal: boolean;
  committed: boolean;
  start: () => Promise<void>;
  interrupt: () => void;
  stopAssistant: () => void;
  commit: () => Promise<void>;
  end: () => void;
}

const INACTIVE: RealtimeVoiceState[] = ["idle", "ended", "unavailable", "error"];

// Default adapter resolution. A browser test may install a deterministic adapter on
// `window.__ask4moRealtimeAdapter` (E2E injects a fake so no mic/provider is needed); in
// production nothing sets that global, so the real WebRTC adapter is always used.
function resolveDefaultAdapter(): RealtimeVoiceAdapter {
  if (typeof window !== "undefined") {
    const injected = (window as unknown as { __ask4moRealtimeAdapter?: RealtimeVoiceAdapter })
      .__ask4moRealtimeAdapter;
    if (injected) return injected;
  }
  return openAiRealtimeAdapter;
}

export function useRealtimeVoice(
  options: UseRealtimeVoiceOptions,
): UseRealtimeVoice {
  const { adapter, locale, surface = "practice", interviewSessionId, onCommit } = options;
  const engine = useMemo<RealtimeVoiceAdapter>(
    () => adapter ?? resolveDefaultAdapter(),
    [adapter],
  );

  const [supported] = useState<boolean>(() => {
    try {
      return engine.isSupported();
    } catch {
      return false;
    }
  });
  const [state, setState] = useState<RealtimeVoiceState>("idle");
  const [error, setError] = useState<RealtimeErrorKind | null>(null);
  const [assistantTranscript, setAssistantTranscript] = useState("");
  const [candidateTranscript, setCandidateTranscript] = useState("");
  const [candidateFinal, setCandidateFinal] = useState(false);
  const [committed, setCommitted] = useState(false);

  const sessionRef = useRef<RealtimeVoiceSession | null>(null);
  const coordinator = useVoiceCoordinator();
  const ownerId = useRef<symbol>(Symbol("realtime-voice"));
  // Per-turn accumulation + commit-once guards.
  const candidateBuf = useRef("");
  const assistantBuf = useRef("");
  const turnId = useRef(0);
  const committedTurn = useRef<number | null>(null);
  const endingRef = useRef(false);

  const releaseChannel = useCallback(() => {
    coordinator?.release(ownerId.current);
  }, [coordinator]);

  const end = useCallback(() => {
    if (endingRef.current) return;
    endingRef.current = true;
    try {
      sessionRef.current?.disconnect();
    } catch {
      /* ignore */
    }
    sessionRef.current = null;
    releaseChannel();
    // Best-effort release of the server-side reservation (fire-and-forget).
    void api.voice.endRealtimeSession().catch(() => undefined);
    setState((s) => (s === "unavailable" || s === "error" ? s : "ended"));
    endingRef.current = false;
  }, [releaseChannel]);

  const startNewCandidateTurn = useCallback(() => {
    turnId.current += 1;
    candidateBuf.current = "";
    setCandidateTranscript("");
    setCandidateFinal(false);
    setCommitted(false);
  }, []);

  const start = useCallback(async () => {
    setError(null);
    if (!supported) {
      setError("unsupported");
      setState("unavailable");
      return;
    }
    // Claim the single audio channel for the whole session: this STOPS any active P7
    // dictation/playback and, if the candidate later starts P7 STT/TTS, that will end this
    // realtime session (mutual exclusion, no full-duplex clash with P7).
    coordinator?.claim(ownerId.current, () => end());
    setState("connecting");
    setAssistantTranscript("");
    assistantBuf.current = "";
    startNewCandidateTurn();

    let grant;
    try {
      grant = await api.voice.realtimeSession({
        locale,
        surface,
        interview_session_id: interviewSessionId ?? null,
      });
    } catch (e) {
      // 503 → unavailable (fall back to turn-based). Anything else → credential/error.
      const kind: RealtimeErrorKind =
        e instanceof ApiError && e.status === 503
          ? "unavailable"
          : e instanceof ApiError && e.status === 429
            ? "unavailable"
            : "credential";
      setError(kind);
      setState(kind === "unavailable" ? "unavailable" : "error");
      releaseChannel();
      return;
    }

    const session = engine.createSession(
      {
        provider: grant.provider,
        model: grant.model,
        voice: grant.voice,
        locale: grant.locale,
        clientSecret: grant.client_secret,
        expiresAt: grant.expires_at,
        sessionId: grant.session_id,
        baseUrl: grant.base_url,
        maxSessionSeconds: grant.max_session_seconds,
        idleTimeoutSeconds: grant.idle_timeout_seconds,
      },
      {
        onState: (s) => setState(s),
        onError: (kind) => {
          setError(kind);
          releaseChannel();
        },
        onInterrupted: () => {
          // Barge-in acknowledged; a fresh candidate turn begins.
          startNewCandidateTurn();
        },
        onTranscript: (evt) => {
          if (evt.role === "assistant") {
            if (evt.isFinal) {
              assistantBuf.current = evt.text || assistantBuf.current;
              setAssistantTranscript(assistantBuf.current);
            } else {
              assistantBuf.current += evt.text;
              setAssistantTranscript(assistantBuf.current);
            }
            return;
          }
          // candidate
          if (evt.isFinal) {
            const finalText = (evt.text && evt.text.trim()) || candidateBuf.current;
            candidateBuf.current = finalText;
            setCandidateTranscript(finalText);
            setCandidateFinal(true);
          } else {
            candidateBuf.current += evt.text;
            setCandidateTranscript(candidateBuf.current);
          }
        },
      },
    );
    sessionRef.current = session;
    await session.connect();
  }, [
    supported,
    coordinator,
    end,
    startNewCandidateTurn,
    locale,
    surface,
    interviewSessionId,
    releaseChannel,
    engine,
  ]);

  const interrupt = useCallback(() => {
    sessionRef.current?.interrupt();
  }, []);

  const stopAssistant = useCallback(() => {
    sessionRef.current?.stopAssistant();
  }, []);

  const commit = useCallback(async () => {
    const text = candidateBuf.current.trim();
    // Commit-ONCE per turn: guard against double-submit from repeated clicks / re-renders /
    // a reconnect replaying the same final transcript.
    if (!text || committedTurn.current === turnId.current) return;
    committedTurn.current = turnId.current;
    setCommitted(true);
    await onCommit?.(text);
  }, [onCommit]);

  useEffect(() => {
    // Cancel the session on unmount (no zombie realtime after navigation). The owner symbol
    // is stable for the component's lifetime; capture it for the cleanup closure.
    const owner = ownerId.current;
    return () => {
      try {
        sessionRef.current?.disconnect();
      } catch {
        /* ignore */
      }
      sessionRef.current = null;
      coordinator?.release(owner);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const active = !INACTIVE.includes(state);
  return {
    supported,
    state,
    active,
    error,
    assistantTranscript,
    candidateTranscript,
    candidateFinal,
    committed,
    start,
    interrupt,
    stopAssistant,
    commit,
    end,
  };
}
