"use client";

/**
 * Voice playback control — "Listen" / "Stop" (Capstone P7 / E5).
 *
 * A small, reusable, user-initiated TTS button over the vendor-neutral SpeechOutputAdapter
 * (browser by default; a fake in tests via the `adapter` prop). It speaks ONLY the
 * candidate-visible text passed to it, after deterministic speech-text sanitisation
 * (`toSpeechText`), never records audio, never opens the microphone, and derives no
 * human-trait signal. Renders nothing when speech synthesis is unavailable, so the visible
 * text remains the guaranteed path. Playback is always interruptible and is cancelled on
 * unmount.
 */

import { useT } from "@/components/i18n/I18nProvider";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import { toSpeechText } from "@/lib/speech/speechText";
import type { SpeechOutputAdapter } from "@/lib/speech/ttsTypes";
import { useSpeechOutput } from "@/lib/speech/useSpeechOutput";

export function VoicePlaybackControl({
  text,
  lang,
  label,
  adapter,
  className,
  onSpeakStart,
}: {
  /** The candidate-VISIBLE text to speak. */
  text: string;
  /** BCP-47 speech locale (from the conversation language). */
  lang?: string;
  /** Primary action label (e.g. "Listen" / "Listen to the question"). */
  label?: string;
  /** Injected for tests; defaults to the browser adapter. */
  adapter?: SpeechOutputAdapter;
  className?: string;
  /** Fired when playback starts — a surface may use it to stop active dictation (§21). */
  onSpeakStart?: () => void;
}) {
  const t = useT();
  const { supported, speaking, status, error, speak, stop } = useSpeechOutput({ adapter, lang });

  // Unsupported → render nothing; the text is already visible on screen (§23 fallback).
  if (!supported) return null;

  const listenLabel = label ?? t("voice.listen");
  const onClick = () => {
    if (speaking) {
      stop();
      return;
    }
    onSpeakStart?.();
    speak(toSpeechText(text));
  };

  const statusText =
    error ? t("voice.unavailable") : speaking ? t("voice.speaking") : status === "stopped" ? t("voice.stopped") : "";

  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        aria-pressed={speaking}
        aria-label={speaking ? t("voice.stop") : listenLabel}
        onClick={onClick}
      >
        <span aria-hidden="true">{speaking ? "◼" : "▶"}</span>
        <span>{speaking ? t("voice.stop") : listenLabel}</span>
      </Button>
      <span role="status" aria-live="polite" className="sr-only">
        {statusText}
      </span>
    </span>
  );
}
