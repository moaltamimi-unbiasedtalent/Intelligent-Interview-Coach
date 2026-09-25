import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { DictationControl } from "@/components/ui/DictationControl";
import { VoicePlaybackControl } from "@/components/ui/VoicePlaybackControl";
import { VoiceCoordinationProvider } from "@/lib/speech/voiceCoordination";
import { createFakeSpeechOutputAdapter } from "@/lib/speech/fakeSpeechOutputAdapter";
import { FakeSpeechAdapter } from "./_fakeSpeech";

// P7 closure §4: on one surface, Ask4Mo STT and Ask4Mo TTS are never actively running at
// the same time. Starting one stops the other; neither submits; text is preserved.

function Harness({ stt, tts }: { stt: FakeSpeechAdapter; tts: ReturnType<typeof createFakeSpeechOutputAdapter> }) {
  const [value, setValue] = useState("my typed answer");
  return (
    <I18nProvider initialLocale="en">
      <VoiceCoordinationProvider>
        <DictationControl value={value} onChange={setValue} adapter={stt} />
        <VoicePlaybackControl text="Focus on measurable impact." adapter={tts} />
        <span data-testid="val">{value}</span>
      </VoiceCoordinationProvider>
    </I18nProvider>
  );
}

describe("voice concurrency (STT/TTS mutual exclusion)", () => {
  it("starting TTS stops active dictation; transcript preserved; no submit", async () => {
    const stt = new FakeSpeechAdapter();
    const tts = createFakeSpeechOutputAdapter();
    render(<Harness stt={stt} tts={tts} />);

    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    expect(stt.started).toBe(true);
    expect(screen.getByRole("button", { name: "Stop dictation" })).toBeInTheDocument();

    // Start playback → active dictation is stopped first, then TTS speaks.
    await userEvent.click(screen.getByRole("button", { name: "Listen" }));
    expect(stt.stopCalls).toBe(1); // dictation was stopped
    expect(tts.spoken).toHaveLength(1); // playback started
    // Dictation is no longer listening (mic button returns to "Start").
    expect(screen.getByRole("button", { name: "Start dictation" })).toBeInTheDocument();
    // Text is preserved (stopping a modality never clears typed/recognised text).
    expect(screen.getByTestId("val").textContent).toBe("my typed answer");
  });

  it("starting dictation stops active TTS; transcript preserved; no auto-restart", async () => {
    const stt = new FakeSpeechAdapter();
    const tts = createFakeSpeechOutputAdapter();
    render(<Harness stt={stt} tts={tts} />);

    await userEvent.click(screen.getByRole("button", { name: "Listen" }));
    expect(tts.spoken).toHaveLength(1);
    // While speaking, the control flips to Stop.
    expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();

    // Start dictation → active TTS is stopped first, then recognition starts.
    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    expect(tts.stops).toBe(1); // playback was stopped
    expect(stt.started).toBe(true); // dictation started
    // TTS did NOT auto-restart (still one utterance total).
    expect(tts.spoken).toHaveLength(1);
    expect(screen.getByTestId("val").textContent).toBe("my typed answer");
  });

  it("unsupported TTS renders nothing and never blocks dictation", async () => {
    const stt = new FakeSpeechAdapter();
    const tts = createFakeSpeechOutputAdapter({ supported: false });
    render(<Harness stt={stt} tts={tts} />);
    expect(screen.queryByRole("button", { name: "Listen" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    expect(stt.started).toBe(true);
  });
});
