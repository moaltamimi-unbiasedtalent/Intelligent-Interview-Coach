import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { DictationControl } from "@/components/ui/DictationControl";
import { appendTranscript } from "@/lib/speech/useDictation";
import { FakeSpeechAdapter } from "./_fakeSpeech";

function Harness({ adapter, initial = "" }: { adapter: FakeSpeechAdapter; initial?: string }) {
  const [value, setValue] = useState(initial);
  return (
    <div>
      <textarea aria-label="field" value={value} onChange={(e) => setValue(e.target.value)} />
      <DictationControl value={value} onChange={setValue} adapter={adapter} />
    </div>
  );
}

afterEach(() => {
  try { window.localStorage.clear(); } catch { /* ignore */ }
});

describe("appendTranscript", () => {
  it("preserves existing text and adds a single separating space", () => {
    expect(appendTranscript("", "hello")).toBe("hello");
    expect(appendTranscript("hello", "world")).toBe("hello world");
    expect(appendTranscript("hello ", "world")).toBe("hello world");
    expect(appendTranscript("typed", "  spoken  ")).toBe("typed spoken");
    expect(appendTranscript("keep this", "")).toBe("keep this");
  });
});

describe("DictationControl", () => {
  it("renders nothing when speech is unsupported (typing remains)", () => {
    const adapter = new FakeSpeechAdapter({ supported: false });
    render(<Harness adapter={adapter} />);
    expect(screen.queryByRole("button", { name: /dictation/i })).not.toBeInTheDocument();
    expect(screen.getByLabelText("field")).toBeInTheDocument();
  });

  it("toggles listening and exposes accessible state", async () => {
    const adapter = new FakeSpeechAdapter();
    render(<Harness adapter={adapter} />);
    const mic = screen.getByRole("button", { name: "Start dictation" });
    expect(mic).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(mic);
    expect(adapter.started).toBe(true);
    expect(screen.getByRole("button", { name: "Stop dictation" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("status")).toHaveTextContent(/Listening/);
  });

  it("shows interim as preview WITHOUT changing the field", async () => {
    const adapter = new FakeSpeechAdapter();
    render(<Harness adapter={adapter} initial="typed" />);
    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    act(() => adapter.emitInterim("interim words"));
    expect(screen.getByRole("status")).toHaveTextContent(/Heard: interim words/);
    // The field is unchanged by interim text.
    expect(screen.getByLabelText("field")).toHaveValue("typed");
  });

  it("appends a FINAL transcript to existing typed text", async () => {
    const adapter = new FakeSpeechAdapter();
    render(<Harness adapter={adapter} initial="typed" />);
    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    act(() => adapter.emitFinal("spoken answer"));
    expect(screen.getByLabelText("field")).toHaveValue("typed spoken answer");
  });

  it("stops on toggle", async () => {
    const adapter = new FakeSpeechAdapter();
    render(<Harness adapter={adapter} />);
    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    await userEvent.click(screen.getByRole("button", { name: "Stop dictation" }));
    expect(adapter.stopCalls).toBe(1);
  });

  it("surfaces a safe message on permission denied and preserves typed text", async () => {
    const adapter = new FakeSpeechAdapter();
    render(<Harness adapter={adapter} initial="keep me" />);
    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    act(() => adapter.emitError("permission-denied"));
    expect(screen.getByRole("status")).toHaveTextContent(/Microphone access was blocked/);
    expect(screen.getByLabelText("field")).toHaveValue("keep me");
    // Still able to type.
    await userEvent.type(screen.getByLabelText("field"), " typed more");
    expect(screen.getByLabelText("field")).toHaveValue("keep me typed more");
  });

  it("offers the bounded Ask4Mo language set with human-readable names", () => {
    const adapter = new FakeSpeechAdapter();
    render(
      <DictationControl value="" onChange={() => {}} adapter={adapter} lang="en-US" onLangChange={() => {}} />,
    );
    expect(screen.getByLabelText("Dictation language")).toBeInTheDocument();
    for (const name of ["English", "German", "French", "Spanish", "Italian", "Portuguese", "Dutch"]) {
      expect(screen.getByRole("option", { name })).toBeInTheDocument();
    }
    // Bounded: exactly the supported set, no arbitrary options.
    expect(screen.getAllByRole("option")).toHaveLength(7);
  });

  it("does not write transcripts to localStorage", async () => {
    const adapter = new FakeSpeechAdapter();
    render(<Harness adapter={adapter} />);
    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    act(() => adapter.emitFinal("sensitive spoken content"));
    const dump = JSON.stringify({ ...window.localStorage });
    expect(dump).not.toContain("sensitive spoken content");
  });
});
