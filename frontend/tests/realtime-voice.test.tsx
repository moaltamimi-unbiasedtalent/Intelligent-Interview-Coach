import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { RealtimeVoiceControl } from "@/components/ui/RealtimeVoiceControl";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { createFakeRealtimeAdapter } from "@/lib/speech/fakeRealtimeAdapter";
import { useRealtimeVoice } from "@/lib/speech/useRealtimeVoice";
import { VoiceCoordinationProvider } from "@/lib/speech/voiceCoordination";

// Capstone P7.5 / C1 realtime voice. Fake adapter + spied grant fetch → ZERO paid/live calls.

const GRANT = {
  provider: "fake_realtime",
  model: "gpt-realtime",
  voice: "alloy",
  locale: "en",
  client_secret: "ephemeral-fake-1",
  expires_at: Date.now() / 1000 + 60,
  session_id: "rt_fake_1",
  base_url: "https://example.test/v1",
  max_session_seconds: 300,
  idle_timeout_seconds: 60,
};

function mockGrant() {
  return vi.spyOn(api.voice, "realtimeSession").mockResolvedValue({ ...GRANT });
}

function Wrap({ children }: { children: ReactNode }) {
  return (
    <I18nProvider initialLocale="en">
      <VoiceCoordinationProvider>{children}</VoiceCoordinationProvider>
    </I18nProvider>
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("realtime voice control", () => {
  it("renders a fallback note and no Start when unsupported", () => {
    const adapter = createFakeRealtimeAdapter({ supported: false });
    render(
      <Wrap>
        <RealtimeVoiceControl adapter={adapter} onCommit={vi.fn()} />
      </Wrap>,
    );
    expect(screen.getByTestId("realtime-unsupported")).toBeInTheDocument();
    expect(screen.queryByTestId("realtime-start")).not.toBeInTheDocument();
  });

  it("starts explicitly and reaches ready", async () => {
    mockGrant();
    const adapter = createFakeRealtimeAdapter();
    render(
      <Wrap>
        <RealtimeVoiceControl adapter={adapter} onCommit={vi.fn()} />
      </Wrap>,
    );
    await userEvent.click(screen.getByTestId("realtime-start"));
    await waitFor(() => expect(screen.getByTestId("realtime-status")).toHaveTextContent("Live voice ready"));
    expect(adapter.sessions).toHaveLength(1);
  });

  // §32 — the core interruption test.
  it("cancels Mo on candidate barge-in and commits the answer exactly once", async () => {
    mockGrant();
    vi.spyOn(api.voice, "endRealtimeSession").mockResolvedValue({ status: "ended" });
    const onCommit = vi.fn();
    const adapter = createFakeRealtimeAdapter();
    render(
      <Wrap>
        <RealtimeVoiceControl adapter={adapter} onCommit={onCommit} />
      </Wrap>,
    );
    await userEvent.click(screen.getByTestId("realtime-start"));
    await waitFor(() => expect(adapter.sessions).toHaveLength(1));
    const session = adapter.sessions[0];

    // Mo starts speaking and streams a transcript.
    act(() => {
      session.__assistantSpeaking();
      session.__assistantTranscript("Tell me about a challenge.", true);
    });
    await waitFor(() => expect(screen.getByTestId("realtime-status")).toHaveTextContent("Mo is speaking"));
    expect(screen.getByTestId("realtime-mo-line")).toHaveTextContent("Tell me about a challenge.");

    // Candidate barges in WHILE Mo is speaking → Mo output cancelled/truncated.
    act(() => session.__candidateSpeechStart());
    expect(session.assistantCancels).toBe(1);
    expect(session.interrupts).toBe(1);

    // Candidate answers; transcript becomes final and reviewable.
    act(() => session.__candidateTranscript("I once led a stalled migration.", true));
    await waitFor(() => expect(screen.getByTestId("realtime-you-line")).toHaveTextContent("I once led a stalled migration."));

    // Commit → the answer is submitted through the caller's contract EXACTLY once.
    await userEvent.click(screen.getByTestId("realtime-commit"));
    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith("I once led a stalled migration.");
    // The commit button is gone (no second, duplicate submission).
    expect(screen.queryByTestId("realtime-commit")).not.toBeInTheDocument();
    expect(screen.getByTestId("realtime-committed")).toBeInTheDocument();
  });

  it("falls back cleanly when the server reports unavailable (503)", async () => {
    vi.spyOn(api.voice, "realtimeSession").mockRejectedValue(
      new ApiError({ kind: "unavailable", status: 503, code: "realtime_unavailable", message: "n/a" }),
    );
    const adapter = createFakeRealtimeAdapter();
    render(
      <Wrap>
        <RealtimeVoiceControl adapter={adapter} onCommit={vi.fn()} />
      </Wrap>,
    );
    await userEvent.click(screen.getByTestId("realtime-start"));
    await waitFor(() => expect(screen.getByTestId("realtime-fallback")).toBeInTheDocument());
    expect(screen.getByTestId("realtime-status")).toHaveTextContent("Live voice is unavailable");
  });
});

describe("useRealtimeVoice commit-once", () => {
  it("commits at most once per candidate turn", async () => {
    mockGrant();
    vi.spyOn(api.voice, "endRealtimeSession").mockResolvedValue({ status: "ended" });
    const onCommit = vi.fn();
    const adapter = createFakeRealtimeAdapter();
    const { result } = renderHook(() => useRealtimeVoice({ adapter, onCommit }), { wrapper: Wrap });

    await act(async () => {
      await result.current.start();
    });
    const session = adapter.sessions[0];
    act(() => session.__candidateTranscript("final answer text", true));

    await act(async () => {
      await result.current.commit();
      await result.current.commit(); // second call must be a no-op (duplicate guard)
    });
    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith("final answer text");
  });

  it("resets the commit guard for a new turn after interruption", async () => {
    mockGrant();
    vi.spyOn(api.voice, "endRealtimeSession").mockResolvedValue({ status: "ended" });
    const onCommit = vi.fn();
    const adapter = createFakeRealtimeAdapter();
    const { result } = renderHook(() => useRealtimeVoice({ adapter, onCommit }), { wrapper: Wrap });

    await act(async () => {
      await result.current.start();
    });
    const session = adapter.sessions[0];

    act(() => session.__candidateTranscript("first answer", true));
    await act(async () => {
      await result.current.commit();
    });

    // A new turn begins (barge-in) → a fresh answer can commit again (new turn id).
    act(() => {
      session.__assistantSpeaking();
      session.__candidateSpeechStart();
      session.__candidateTranscript("second answer", true);
    });
    await act(async () => {
      await result.current.commit();
    });
    expect(onCommit).toHaveBeenCalledTimes(2);
    expect(onCommit).toHaveBeenLastCalledWith("second answer");
  });
});
