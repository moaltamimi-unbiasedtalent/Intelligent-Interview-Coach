import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { DictationControl } from "@/components/ui/DictationControl";
import { VoicePlaybackControl } from "@/components/ui/VoicePlaybackControl";
import { api } from "@/lib/api/client";
import { createFakeSpeechOutputAdapter } from "@/lib/speech/fakeSpeechOutputAdapter";
import { resetSpeechPolicyCache } from "@/lib/speech/useSpeechPolicy";
import { FakeSpeechAdapter } from "./_fakeSpeech";

function ui(node: React.ReactNode) {
  return <I18nProvider initialLocale="en">{node}</I18nProvider>;
}

const CAPS = {
  server_stt_languages: [],
  server_tts_languages: [],
  browser_stt_allowed: true,
  browser_tts_allowed: true,
  product_languages: ["en", "de", "fr", "es", "it", "pt", "nl"],
  excluded_languages: ["ru"],
  audio_persisted: false,
  browser_disclosure: "x",
};

beforeEach(() => resetSpeechPolicyCache());
afterEach(() => vi.restoreAllMocks());

describe("governed browser speech (W12.4E)", () => {
  it("keeps the existing behaviour when the backend cannot be reached (offline, signed out)", async () => {
    vi.spyOn(api, "speechCapabilities").mockRejectedValue(new Error("offline"));
    render(ui(<DictationControl value="" onChange={() => {}} adapter={new FakeSpeechAdapter()} />));
    expect(screen.getByRole("button", { name: "Start dictation" })).toBeInTheDocument();
    render(ui(<VoicePlaybackControl text="Hello" adapter={createFakeSpeechOutputAdapter()} />));
    await waitFor(() => expect(screen.getByRole("button", { name: /Listen/ })).toBeInTheDocument());
  });

  it("shows the point-of-use disclosure that the browser may send the voice to its provider", async () => {
    vi.spyOn(api, "speechCapabilities").mockResolvedValue(CAPS);
    render(ui(<DictationControl value="" onChange={() => {}} adapter={new FakeSpeechAdapter()} />));
    const note = await screen.findByTestId("dictation-browser-notice");
    expect(note).toHaveTextContent(/browser.s speech service/i);
    expect(note).toHaveTextContent(/does not store your audio/i);
  });

  it("hides browser dictation when an administrator disabled it, and typing stays", async () => {
    vi.spyOn(api, "speechCapabilities").mockResolvedValue({ ...CAPS, browser_stt_allowed: false });
    render(
      ui(
        <div>
          <textarea aria-label="field" />
          <DictationControl value="" onChange={() => {}} adapter={new FakeSpeechAdapter()} />
        </div>,
      ),
    );
    expect(await screen.findByTestId("dictation-disabled-by-policy")).toHaveTextContent(/switched off/i);
    expect(screen.queryByRole("button", { name: "Start dictation" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("field")).toBeInTheDocument();
  });

  it("hides speech output when an administrator disabled it", async () => {
    vi.spyOn(api, "speechCapabilities").mockResolvedValue({ ...CAPS, browser_tts_allowed: false });
    render(ui(<VoicePlaybackControl text="Hello there" adapter={createFakeSpeechOutputAdapter()} />));
    await waitFor(() => expect(screen.queryByRole("button", { name: /Listen/ })).not.toBeInTheDocument());
  });
});
