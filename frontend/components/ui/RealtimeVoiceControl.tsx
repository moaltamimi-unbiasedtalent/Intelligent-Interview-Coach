"use client";

// RealtimeVoiceControl — the candidate-facing live-voice surface (Capstone P7.5, C1).
//
// Renders the explicit Start control, the session state, a live transcript (Mo + You), the
// barge-in / stop / end controls, and the explicit "Use this answer" commit. Fully operable
// without hearing audio: every state is shown as text, controls are keyboard-reachable, and
// status is announced via aria-live. When realtime is unsupported/unavailable it shows a calm
// message and the caller keeps turn-based voice + typing available (never a dead end).

import { useT } from "@/components/i18n/I18nProvider";
import type { RealtimeVoiceAdapter, RealtimeVoiceState } from "@/lib/speech/realtimeTypes";
import { useRealtimeVoice } from "@/lib/speech/useRealtimeVoice";

export interface RealtimeVoiceControlProps {
  onCommit: (text: string) => void | Promise<void>;
  surface?: "practice" | "prepare";
  locale?: string;
  interviewSessionId?: string | null;
  adapter?: RealtimeVoiceAdapter; // injected in tests; defaults to the WebRTC adapter
  disabled?: boolean;
  className?: string;
}

const STATE_KEY: Record<RealtimeVoiceState, string> = {
  idle: "voice.realtimeReady",
  connecting: "voice.realtimeConnecting",
  ready: "voice.realtimeReady",
  listening: "voice.realtimeListening",
  assistant_speaking: "voice.realtimeAssistantSpeaking",
  interrupted: "voice.realtimeInterrupted",
  reconnecting: "voice.realtimeReconnecting",
  ended: "voice.realtimeEnded",
  unavailable: "voice.realtimeUnavailable",
  error: "voice.realtimeError",
};

export function RealtimeVoiceControl({
  onCommit,
  surface = "practice",
  locale,
  interviewSessionId,
  adapter,
  disabled,
  className,
}: RealtimeVoiceControlProps) {
  const t = useT();
  const rt = useRealtimeVoice({ adapter, locale, surface, interviewSessionId, onCommit });

  // Unsupported browser: don't offer live voice; the caller keeps turn-based + typing.
  if (!rt.supported) {
    return (
      <p className={className} data-testid="realtime-unsupported" role="note">
        {t("voice.realtimeNotSupported")}
      </p>
    );
  }

  const statusText = t(STATE_KEY[rt.state]);
  const showFallback = rt.state === "unavailable" || rt.state === "error";

  return (
    <section
      className={className}
      aria-label={t("voice.realtimeStatusLabel")}
      data-testid="realtime-voice"
      data-state={rt.state}
    >
      {!rt.active && rt.state !== "unavailable" && rt.state !== "error" ? (
        <div>
          <p className="text-sm text-muted-foreground">{t("voice.realtimeDescription")}</p>
          <button
            type="button"
            onClick={() => void rt.start()}
            disabled={disabled}
            data-testid="realtime-start"
            className="mt-2 inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium"
          >
            <span aria-hidden>🎙️</span> {t("voice.realtimeStart")}
          </button>
        </div>
      ) : null}

      {/* Live status — always announced to assistive tech. */}
      <p
        role="status"
        aria-live="polite"
        data-testid="realtime-status"
        className="mt-2 text-sm font-medium"
      >
        {statusText}
      </p>

      {rt.active ? (
        <>
          {/* Live transcript (visible, not audio-only). */}
          <div
            className="mt-3 space-y-2 rounded-md border p-3 text-sm"
            data-testid="realtime-transcript"
            aria-label={t("voice.realtimeTranscript")}
          >
            {rt.assistantTranscript ? (
              <p data-testid="realtime-mo-line">
                <span className="font-semibold">{t("voice.realtimeMo")}: </span>
                {rt.assistantTranscript}
              </p>
            ) : null}
            {rt.candidateTranscript ? (
              <p data-testid="realtime-you-line">
                <span className="font-semibold">{t("voice.realtimeYou")}: </span>
                {rt.candidateTranscript}
              </p>
            ) : null}
          </div>

          {/* Controls: barge-in, manual stop, commit, end. */}
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={rt.interrupt}
              data-testid="realtime-interrupt"
              className="rounded-md border px-3 py-1.5 text-sm"
            >
              {t("voice.realtimeInterrupt")}
            </button>
            <button
              type="button"
              onClick={rt.stopAssistant}
              data-testid="realtime-stop-mo"
              className="rounded-md border px-3 py-1.5 text-sm"
            >
              {t("voice.realtimeStopMo")}
            </button>
            {rt.candidateFinal && !rt.committed ? (
              <button
                type="button"
                onClick={() => void rt.commit()}
                data-testid="realtime-commit"
                className="rounded-md border px-3 py-1.5 text-sm font-medium"
              >
                {t("voice.realtimeUseAnswer")}
              </button>
            ) : null}
            <button
              type="button"
              onClick={rt.end}
              data-testid="realtime-end"
              className="rounded-md border px-3 py-1.5 text-sm"
            >
              {t("voice.realtimeEnd")}
            </button>
          </div>

          {rt.committed ? (
            <p className="mt-2 text-sm text-green-700" data-testid="realtime-committed" role="status">
              {t("voice.realtimeCommitted")}
            </p>
          ) : null}
        </>
      ) : null}

      {showFallback ? (
        <div className="mt-2" data-testid="realtime-fallback">
          <p className="text-sm">
            {rt.error === "mic-permission" ? t("voice.realtimeMicDenied") : t("voice.realtimeError")}
          </p>
          <p className="text-sm text-muted-foreground">{t("voice.realtimeFallback")}</p>
        </div>
      ) : null}
    </section>
  );
}
