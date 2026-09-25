import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { VoicePlaybackControl } from "@/components/ui/VoicePlaybackControl";
import { createFakeSpeechOutputAdapter } from "@/lib/speech/fakeSpeechOutputAdapter";
import { toSpeechText } from "@/lib/speech/speechText";
import { SUPPORTED_TTS_LOCALES, TTS_LOCALE, toSpeechLocale, ttsLanguageStatus } from "@/lib/speech/ttsLocales";

function ui(node: React.ReactNode) {
  return <I18nProvider initialLocale="en">{node}</I18nProvider>;
}

// --- speech-text sanitiser (§24/§25) ----------------------------------------

describe("toSpeechText", () => {
  it("strips markdown syntax but keeps the words and caveats", () => {
    const out = toSpeechText("**Bold** and _italic_ and `code`. Note: advertised salary is not verified.");
    expect(out).toContain("Bold and italic and code.");
    expect(out).toContain("advertised salary is not verified");
    expect(out).not.toContain("**");
    expect(out).not.toContain("`");
  });

  it("replaces links/URLs with the label and never reads the URL", () => {
    const out = toSpeechText("See [ESCO](https://esco.example/data) for details. https://raw.example/x");
    expect(out).toContain("ESCO");
    expect(out).not.toContain("https://");
  });

  it("turns citation markers into a spoken sources note", () => {
    const out = toSpeechText("Median pay is competitive [1][2].");
    expect(out).toContain("Sources are available on screen");
    expect(out).not.toContain("[1]");
  });
});

// --- locale mapping (§10) ----------------------------------------------------

describe("tts locales", () => {
  it("maps all seven product locales to a bounded speech locale", () => {
    expect(SUPPORTED_TTS_LOCALES).toEqual(["en", "de", "fr", "es", "it", "pt", "nl"]);
    expect(TTS_LOCALE.de).toBe("de-DE");
    expect(toSpeechLocale("de")).toBe("de-DE");
    expect(toSpeechLocale("zz")).toBe("en-US"); // safe fallback
  });

  it("reports honest per-language status (configured/tested; live UNVALIDATED)", () => {
    const status = ttsLanguageStatus();
    expect(status).toHaveLength(7);
    expect(status.every((s) => s.configured && s.deterministicallyTested)).toBe(true);
    expect(status.every((s) => s.liveHumanQualityTested === false)).toBe(true);
  });
});

// --- VoicePlaybackControl (§7/§21/§23) ---------------------------------------

describe("VoicePlaybackControl", () => {
  it("renders nothing when speech synthesis is unavailable (text stays visible)", () => {
    const adapter = createFakeSpeechOutputAdapter({ supported: false });
    const { container } = render(ui(<VoicePlaybackControl text="Hello" adapter={adapter} />));
    expect(container.textContent).toBe("");
  });

  it("is user-initiated: speaks the sanitised text only on click, then Stop stops", async () => {
    const adapter = createFakeSpeechOutputAdapter();
    render(ui(<VoicePlaybackControl text="**Hi** there [1]" lang="de-DE" adapter={adapter} />));
    // Nothing spoken until the user clicks (no auto-play on mount).
    expect(adapter.spoken).toHaveLength(0);

    await userEvent.click(screen.getByRole("button", { name: /listen/i }));
    expect(adapter.spoken).toHaveLength(1);
    expect(adapter.spoken[0].text).toContain("Hi there");
    expect(adapter.spoken[0].text).not.toContain("**");
    expect(adapter.spoken[0].lang).toBe("de-DE");

    // While speaking the button flips to Stop; clicking it stops playback.
    const stopBtn = screen.getByRole("button", { name: /stop/i });
    await userEvent.click(stopBtn);
    expect(adapter.stops).toBe(1);
  });

  it("fires onSpeakStart so a surface can stop the mic (§21)", async () => {
    const adapter = createFakeSpeechOutputAdapter();
    let started = 0;
    render(ui(<VoicePlaybackControl text="Hi" adapter={adapter} onSpeakStart={() => (started += 1)} />));
    await userEvent.click(screen.getByRole("button", { name: /listen/i }));
    expect(started).toBe(1);
  });
});
