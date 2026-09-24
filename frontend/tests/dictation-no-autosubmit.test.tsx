import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { AgentComposer } from "@/components/agent/AgentComposer";
import { InterviewAnswerComposer } from "@/components/interview/InterviewAnswerComposer";
import { FakeSpeechAdapter } from "./_fakeSpeech";

/**
 * CRITICAL SAFETY INVARIANT (P3 §6): dictation NEVER auto-submits. Proven on BOTH
 * production surfaces — a final transcript populates the editable field, and the submit
 * handler fires ONLY on an explicit click.
 */

describe("Surface 1 — Prepare (AgentComposer)", () => {
  it("speech → editable transcript, NO auto-submit; explicit Send submits", async () => {
    const adapter = new FakeSpeechAdapter();
    const onSend = vi.fn();
    render(<AgentComposer onSend={onSend} busy={false} dictationAdapter={adapter} />);

    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    act(() => adapter.emitFinal("prepare me for a PM interview"));

    // Transcript is in the editable field...
    expect(screen.getByLabelText("Message Mo")).toHaveValue("prepare me for a PM interview");
    // ...and nothing was sent.
    expect(onSend).not.toHaveBeenCalled();

    // Explicit click is the only submit path.
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend).toHaveBeenCalledWith("prepare me for a PM interview");
  });

  it("transcript remains editable before sending", async () => {
    const adapter = new FakeSpeechAdapter();
    const onSend = vi.fn();
    render(<AgentComposer onSend={onSend} busy={false} dictationAdapter={adapter} />);
    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    act(() => adapter.emitFinal("draft"));
    await userEvent.type(screen.getByLabelText("Message Mo"), " edited");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledWith("draft edited");
  });
});

describe("Surface 2 — Practice (InterviewAnswerComposer)", () => {
  function Harness({ adapter, onSubmit }: { adapter: FakeSpeechAdapter; onSubmit: () => void }) {
    const [value, setValue] = useState("");
    return (
      <InterviewAnswerComposer
        value={value}
        onChange={setValue}
        onSubmit={onSubmit}
        busy={false}
        dictationAdapter={adapter}
      />
    );
  }

  it("speech → editable transcript, NO auto-submit; explicit Submit submits", async () => {
    const adapter = new FakeSpeechAdapter();
    const onSubmit = vi.fn();
    render(<Harness adapter={adapter} onSubmit={onSubmit} />);

    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    act(() => adapter.emitFinal("my structured answer"));

    expect(screen.getByLabelText("Your answer")).toHaveValue("my structured answer");
    expect(onSubmit).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Submit answer" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("preserves manually typed text when dictation is added", async () => {
    const adapter = new FakeSpeechAdapter();
    const onSubmit = vi.fn();
    render(<Harness adapter={adapter} onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("Your answer"), "typed first.");
    await userEvent.click(screen.getByRole("button", { name: "Start dictation" }));
    act(() => adapter.emitFinal("then spoken"));
    expect(screen.getByLabelText("Your answer")).toHaveValue("typed first. then spoken");
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
