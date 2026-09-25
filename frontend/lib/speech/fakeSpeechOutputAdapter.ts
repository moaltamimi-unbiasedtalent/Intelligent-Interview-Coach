/**
 * Deterministic fake SpeechOutputAdapter for tests (Capstone P7 / E5).
 *
 * No browser globals, no audio, no timers by default: `speak` records the text and fires
 * onStart synchronously; playback "ends" only when the test calls `finish()` (so a test can
 * assert the SPEAKING state) or immediately if `autoFinish` is set. Proves the UI wiring
 * (user-initiated playback, stop, state machine) without a real speech engine.
 */

import type {
  SpeechOutputAdapter,
  SpeechOutputErrorKind,
  SpeechOutputHandlers,
  SpeechOutputOptions,
} from "./ttsTypes";

export interface FakeSpeechOutputAdapter extends SpeechOutputAdapter {
  spoken: { text: string; lang?: string }[];
  stops: number;
  finish: () => void;
}

export function createFakeSpeechOutputAdapter(opts?: {
  supported?: boolean;
  hasVoice?: boolean;
  autoFinish?: boolean;
  failWith?: SpeechOutputErrorKind;
}): FakeSpeechOutputAdapter {
  const supported = opts?.supported ?? true;
  const hasVoice = opts?.hasVoice ?? true;
  let current: SpeechOutputHandlers | null = null;
  const adapter: FakeSpeechOutputAdapter = {
    spoken: [],
    stops: 0,
    isSupported: () => supported,
    hasVoiceFor: () => hasVoice,
    speak(text: string, options: SpeechOutputOptions, handlers: SpeechOutputHandlers) {
      if (!supported) {
        handlers.onError?.("unsupported");
        return;
      }
      if (opts?.failWith) {
        handlers.onError?.(opts.failWith);
        return;
      }
      adapter.spoken.push({ text, lang: options.lang });
      current = handlers;
      handlers.onStart?.();
      if (opts?.autoFinish) {
        current = null;
        handlers.onEnd?.();
      }
    },
    stop() {
      adapter.stops += 1;
      current = null;
    },
    finish() {
      current?.onEnd?.();
      current = null;
    },
  };
  return adapter;
}
