import { readFileSync } from "node:fs";
import path from "node:path";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { DICTATION_LANGUAGES, DictationControl } from "@/components/ui/DictationControl";
import { CATALOGS, translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";
import { BrowserSpeechAdapter, mapError } from "@/lib/speech/browserAdapter";
import { FakeSpeechAdapter } from "./_fakeSpeech";

/**
 * 04F: browser dictation disclosure and verification (engineering evidence only).
 * Nothing here is a legal review, a native-language review or a measurement of recognition quality.
 */

function Harness({ adapter }: { adapter: FakeSpeechAdapter }) {
  const [value, setValue] = useState("");
  return <DictationControl value={value} onChange={setValue} adapter={adapter} lang="en-US" onLangChange={() => {}} />;
}

afterEach(() => {
  try { window.localStorage.clear(); } catch { /* ignore */ }
});

describe("disclosure is shown before first microphone use and stays re-readable", () => {
  it("is visible and tied to the microphone button BEFORE the first click", () => {
    const adapter = new FakeSpeechAdapter();
    render(<Harness adapter={adapter} />);
    const notice = screen.getByTestId("dictation-browser-notice");
    expect(notice).toHaveTextContent(/may send your voice to its provider/);
    expect(notice).toHaveTextContent(/does not store your audio/);
    // Nothing has started yet: the notice precedes any recognition.
    expect(adapter.started).toBe(false);
    // Assistive technology hears the disclosure with the control (accessible description).
    const mic = screen.getByRole("button", { name: "Start dictation" });
    expect(mic).toHaveAccessibleDescription(notice.textContent ?? "");
  });

  it("stays visible while listening, after stop and after an error", async () => {
    const adapter = new FakeSpeechAdapter();
    render(<Harness adapter={adapter} />);
    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    expect(screen.getByTestId("dictation-browser-notice")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Stop dictation" }));
    expect(screen.getByTestId("dictation-browser-notice")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    act(() => adapter.emitError("permission-denied"));
    expect(screen.getByTestId("dictation-browser-notice")).toBeInTheDocument();
  });

  it("is not shown (and no microphone control exists) when unsupported: an explicit note is shown instead", () => {
    render(<Harness adapter={new FakeSpeechAdapter({ supported: false })} />);
    expect(screen.queryByRole("button", { name: /dictation/i })).not.toBeInTheDocument();
    expect(screen.getByTestId("dictation-unsupported")).toHaveTextContent(/isn’t available in this browser/);
  });
});

describe("error states are never silent", () => {
  it("shows a localised message for a language the browser reports unsupported", async () => {
    const adapter = new FakeSpeechAdapter();
    render(<Harness adapter={adapter} />);
    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    act(() => adapter.emitError("language-not-supported"));
    expect(screen.getByRole("status")).toHaveTextContent(/can’t recognise speech in the selected dictation language/);
    // The generic message is NOT what the candidate gets for this case.
    expect(screen.getByRole("status")).not.toHaveTextContent(/stopped unexpectedly/);
  });

  it("maps the browser's raw error codes to safe kinds", () => {
    expect(mapError("not-allowed")).toBe("permission-denied");
    expect(mapError("service-not-allowed")).toBe("permission-denied");
    expect(mapError("audio-capture")).toBe("no-microphone");
    expect(mapError("no-speech")).toBe("no-speech");
    expect(mapError("network")).toBe("network");
    expect(mapError("language-not-supported")).toBe("language-not-supported");
    expect(mapError("aborted")).toBe("aborted");
    expect(mapError("something-new")).toBe("error");
    expect(mapError(undefined)).toBe("error");
  });

  it("the production adapter surfaces language-not-supported from a mocked SpeechRecognition", () => {
    class Mock {
      static last: Mock;
      lang = "";
      continuous = false;
      interimResults = false;
      maxAlternatives = 1;
      onstart: (() => void) | null = null;
      onend: (() => void) | null = null;
      onerror: ((e: { error?: string }) => void) | null = null;
      onresult: ((e: unknown) => void) | null = null;
      start() { Mock.last = this; this.onstart?.(); }
      stop() { this.onend?.(); }
      abort() {}
    }
    const w = window as unknown as { SpeechRecognition?: unknown };
    w.SpeechRecognition = Mock;
    try {
      const kinds: string[] = [];
      const adapter = new BrowserSpeechAdapter();
      adapter.start({ lang: "nl-NL" }, { onError: (k) => kinds.push(k) });
      expect(Mock.last.lang).toBe("nl-NL");
      Mock.last.onerror?.({ error: "language-not-supported" });
      expect(kinds).toEqual(["language-not-supported"]);
    } finally {
      delete w.SpeechRecognition;
    }
  });
});

describe("every interface language carries the full dictation copy", () => {
  const KEYS = [
    "start", "stop", "listening", "heard", "languageLabel", "unsupported", "permissionDenied", "noMicrophone",
    "noSpeech", "network", "languageNotSupported", "error", "disabledByPolicy", "browserNotice",
  ];
  it("has every key, non-empty, in all locales; non-English text differs from English", () => {
    for (const code of SUPPORTED_LOCALE_CODES) {
      for (const k of KEYS) {
        const text = translate(code, `dictation.${k}`);
        expect(text, `${code} dictation.${k}`).not.toBe(`dictation.${k}`);
        expect(text.trim().length, `${code} dictation.${k}`).toBeGreaterThan(0);
        if (code !== "en") expect(text, `${code} dictation.${k} untranslated`).not.toBe(translate("en", `dictation.${k}`));
      }
    }
  });
  it("the disclosure names Ask4Mo and carries no unfilled placeholder in every locale", () => {
    for (const code of SUPPORTED_LOCALE_CODES) {
      const text = translate(code, "dictation.browserNotice");
      expect(text).toContain("Ask4Mo");
      expect(text).not.toMatch(/\{\w+\}/);
    }
  });
  it("offers exactly the seven speech languages (Russian is not a dictation language)", () => {
    expect(DICTATION_LANGUAGES.map((l) => l.code)).toEqual(["en-US", "de-DE", "fr-FR", "es-ES", "it-IT", "pt-PT", "nl-NL"]);
    expect(Object.keys(CATALOGS)).toContain("ru");
  });
});

describe("browser dictation sends no audio to Ask4Mo servers (source evidence)", () => {
  const root = path.resolve(__dirname, "..");
  const FILES = ["lib/speech/browserAdapter.ts", "lib/speech/useDictation.ts", "lib/speech/types.ts", "components/ui/DictationControl.tsx"];
  const FORBIDDEN = [/\bfetch\s*\(/, /XMLHttpRequest/, /WebSocket/, /sendBeacon/, /MediaRecorder/, /getUserMedia/, /AudioContext/, /\bBlob\b/, /FormData/, /RTCPeerConnection/, /localStorage\.setItem\([^)]*(transcript|chunk|interim)/];
  for (const f of FILES) {
    it(`${f} has no network, recorder or capture primitive`, () => {
      const src = readFileSync(path.join(root, f), "utf8")
        // ignore comments so prose such as "never persists audio" cannot hide or trigger a hit
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/(^|[^:])\/\/.*$/gm, "$1");
      for (const re of FORBIDDEN) expect(src, `${f} matches ${re}`).not.toMatch(re);
    });
  }
  it("the frontend API client has no transcription or synthesis call (server speech stays gated)", () => {
    const client = readFileSync(path.join(root, "lib/api/client.ts"), "utf8");
    expect(client).not.toMatch(/\/speech\/transcriptions/);
    expect(client).not.toMatch(/\/speech\/synthesis/);
    // The only speech call is the read-only capability lookup used by the policy hook.
    expect(client.match(/"\/speech\/[a-z]+"/g)).toEqual(["\"/speech/capabilities\""]);
  });
});
