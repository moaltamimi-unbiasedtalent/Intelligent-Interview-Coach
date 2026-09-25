/**
 * Browser SpeechSynthesis adapter (Capstone P7 / E5).
 *
 * Wraps the Web Speech `speechSynthesis` API behind the vendor-neutral
 * SpeechOutputAdapter seam. It speaks candidate-visible text only, never records or
 * persists audio, never listens, and derives no human-trait signal. A matching voice for
 * the requested language is auto-selected when one is installed; otherwise the platform
 * default voice is used (best-effort). All browser access is guarded so an unsupported or
 * failing environment degrades to a safe error, never a crash.
 *
 * PRIVACY NOTE (honest): Ask4Mo hands the visible text to the browser/OS/vendor speech
 * engine. How that engine synthesises audio (locally or via a vendor service) is
 * browser/OS-dependent; Ask4Mo does not control or store it. Ask4Mo stores no audio.
 */

import type {
  SpeechOutputAdapter,
  SpeechOutputHandlers,
  SpeechOutputOptions,
} from "./ttsTypes";

function synth(): SpeechSynthesis | null {
  if (typeof window === "undefined") return null;
  const s = window.speechSynthesis;
  return s && typeof window.SpeechSynthesisUtterance === "function" ? s : null;
}

function pickVoice(s: SpeechSynthesis, lang?: string, voiceURI?: string): SpeechSynthesisVoice | null {
  let voices: SpeechSynthesisVoice[] = [];
  try {
    voices = s.getVoices() ?? [];
  } catch {
    return null;
  }
  if (voiceURI) {
    const exact = voices.find((v) => v.voiceURI === voiceURI);
    if (exact) return exact;
  }
  if (lang) {
    const prefix = lang.slice(0, 2).toLowerCase();
    return (
      voices.find((v) => v.lang?.toLowerCase() === lang.toLowerCase()) ??
      voices.find((v) => v.lang?.toLowerCase().startsWith(prefix)) ??
      null
    );
  }
  return null;
}

export const browserSpeechSynthesisAdapter: SpeechOutputAdapter = {
  isSupported(): boolean {
    return synth() !== null;
  },

  hasVoiceFor(lang: string): boolean {
    const s = synth();
    if (!s) return false;
    try {
      // A voice may be present; if the list is empty (not yet loaded) we still allow
      // speaking with the platform default, so absence of a match is not fatal.
      return s.getVoices().length === 0 || pickVoice(s, lang) !== null;
    } catch {
      return false;
    }
  },

  speak(text: string, options: SpeechOutputOptions, handlers: SpeechOutputHandlers): void {
    const s = synth();
    if (!s) {
      handlers.onError?.("unsupported");
      return;
    }
    const clean = (text ?? "").trim();
    if (!clean) {
      handlers.onEnd?.();
      return;
    }
    try {
      s.cancel(); // never overlap utterances
      const u = new window.SpeechSynthesisUtterance(clean);
      if (options.lang) u.lang = options.lang;
      const voice = pickVoice(s, options.lang, options.voiceURI);
      if (voice) u.voice = voice;
      u.onstart = () => handlers.onStart?.();
      u.onend = () => handlers.onEnd?.();
      u.onpause = () => handlers.onPause?.();
      u.onresume = () => handlers.onResume?.();
      u.onerror = () => handlers.onError?.("synthesis-error");
      s.speak(u);
    } catch {
      handlers.onError?.("error");
    }
  },

  stop(): void {
    const s = synth();
    try {
      s?.cancel();
    } catch {
      /* best-effort */
    }
  },

  pause(): void {
    const s = synth();
    try {
      s?.pause();
    } catch {
      /* best-effort */
    }
  },

  resume(): void {
    const s = synth();
    try {
      s?.resume();
    } catch {
      /* best-effort */
    }
  },
};
