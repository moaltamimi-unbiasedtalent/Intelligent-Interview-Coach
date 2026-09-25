// Realtime voice adapter — WebRTC to an OpenAI-Realtime-shaped provider (Capstone P7.5).
//
// HONEST STATUS: architecture-complete but LIVE-UNVALIDATED. No authorised realtime key
// exists in this project, so this has never made a real call. The WebRTC + event flow follows
// the documented OpenAI Realtime API; all provider-specific event names are confined to this
// file (the UI depends only on RealtimeVoiceAdapter/RealtimeVoiceSession).
//
// Boundaries: the browser uses ONLY the ephemeral `grant.clientSecret` (never a long-lived
// key); audio streams browser↔provider (Ask4Mo is not in the path); nothing is recorded or
// persisted. Barge-in uses `response.cancel` + `conversation.item.truncate`.

import type {
  RealtimeSessionGrant,
  RealtimeVoiceAdapter,
  RealtimeVoiceHandlers,
  RealtimeVoiceSession,
  RealtimeVoiceState,
} from "./realtimeTypes";

function browserSupportsRealtime(): boolean {
  if (typeof window === "undefined" || typeof navigator === "undefined") return false;
  const hasPc = typeof (window as unknown as { RTCPeerConnection?: unknown }).RTCPeerConnection
    === "function";
  const hasMedia = !!(navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia
    === "function");
  return hasPc && hasMedia;
}

export const openAiRealtimeAdapter: RealtimeVoiceAdapter = {
  isSupported: browserSupportsRealtime,

  createSession(
    grant: RealtimeSessionGrant,
    handlers: RealtimeVoiceHandlers,
  ): RealtimeVoiceSession {
    let state: RealtimeVoiceState = "idle";
    let pc: RTCPeerConnection | null = null;
    let dc: RTCDataChannel | null = null;
    let micStream: MediaStream | null = null;
    let audioEl: HTMLAudioElement | null = null;
    let disposed = false;

    const set = (s: RealtimeVoiceState) => {
      state = s;
      handlers.onState?.(s);
    };

    const send = (event: Record<string, unknown>) => {
      try {
        if (dc && dc.readyState === "open") dc.send(JSON.stringify(event));
      } catch {
        // Never surface transport internals; a failed control event degrades gracefully.
      }
    };

    // Translate provider events → provider-neutral handler calls. Unknown events ignored.
    const onProviderEvent = (raw: string) => {
      let evt: { type?: string; delta?: string; transcript?: string };
      try {
        evt = JSON.parse(raw);
      } catch {
        return;
      }
      switch (evt.type) {
        case "response.audio_transcript.delta":
          if (typeof evt.delta === "string")
            handlers.onTranscript?.({ role: "assistant", text: evt.delta, isFinal: false });
          break;
        case "response.audio_transcript.done":
          if (typeof evt.transcript === "string")
            handlers.onTranscript?.({ role: "assistant", text: evt.transcript, isFinal: true });
          break;
        case "output_audio_buffer.started":
          handlers.onAssistantAudioStart?.();
          set("assistant_speaking");
          break;
        case "output_audio_buffer.stopped":
        case "response.done":
          handlers.onAssistantAudioEnd?.();
          if (state === "assistant_speaking") set("ready");
          break;
        case "input_audio_buffer.speech_started":
          // Candidate started speaking. If Mo is mid-response this is a barge-in.
          if (state === "assistant_speaking") sessionInterrupt();
          else set("listening");
          break;
        case "conversation.item.input_audio_transcription.delta":
          if (typeof evt.delta === "string")
            handlers.onTranscript?.({ role: "candidate", text: evt.delta, isFinal: false });
          break;
        case "conversation.item.input_audio_transcription.completed":
          if (typeof evt.transcript === "string")
            handlers.onTranscript?.({ role: "candidate", text: evt.transcript, isFinal: true });
          break;
        case "error":
          handlers.onError?.("provider");
          break;
        default:
          break;
      }
    };

    // Barge-in: cancel the in-flight response and truncate the already-played audio so the
    // provider's conversation state matches what the candidate actually heard.
    function sessionInterrupt() {
      send({ type: "response.cancel" });
      send({ type: "conversation.item.truncate" });
      if (audioEl) {
        try {
          audioEl.pause();
        } catch {
          /* ignore */
        }
      }
      handlers.onAssistantAudioEnd?.();
      handlers.onInterrupted?.();
      set("interrupted");
    }

    const cleanup = () => {
      disposed = true;
      try {
        micStream?.getTracks().forEach((t) => t.stop());
      } catch {
        /* ignore */
      }
      try {
        dc?.close();
      } catch {
        /* ignore */
      }
      try {
        pc?.close();
      } catch {
        /* ignore */
      }
      if (audioEl) {
        try {
          audioEl.srcObject = null;
          audioEl.remove();
        } catch {
          /* ignore */
        }
      }
      micStream = null;
      dc = null;
      pc = null;
      audioEl = null;
    };

    return {
      async connect() {
        if (!browserSupportsRealtime()) {
          handlers.onError?.("unsupported");
          set("error");
          return;
        }
        set("connecting");
        try {
          micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch {
          handlers.onError?.("mic-permission");
          set("error");
          return;
        }
        try {
          pc = new RTCPeerConnection();
          pc.oniceconnectionstatechange = () => {
            const st = pc?.iceConnectionState;
            if ((st === "disconnected" || st === "failed") && !disposed) {
              handlers.onError?.("disconnect");
              handlers.onDisconnected?.();
              set("error");
            }
          };
          // Remote audio (Mo's voice) → a hidden audio element.
          audioEl = document.createElement("audio");
          audioEl.autoplay = true;
          pc.ontrack = (e) => {
            if (audioEl) audioEl.srcObject = e.streams[0] ?? null;
          };
          micStream.getTracks().forEach((t) => pc?.addTrack(t, micStream as MediaStream));

          dc = pc.createDataChannel("oai-events");
          dc.onmessage = (e) => onProviderEvent(String(e.data));

          const offer = await pc.createOffer();
          await pc.setLocalDescription(offer);

          const url = `${grant.baseUrl.replace(/\/$/, "")}/realtime?model=${encodeURIComponent(grant.model)}`;
          const resp = await fetch(url, {
            method: "POST",
            body: offer.sdp,
            headers: {
              Authorization: `Bearer ${grant.clientSecret}`,
              "Content-Type": "application/sdp",
            },
          });
          if (!resp.ok) {
            handlers.onError?.(resp.status === 401 ? "credential" : "connection");
            set("error");
            cleanup();
            return;
          }
          const answer = { type: "answer" as RTCSdpType, sdp: await resp.text() };
          await pc.setRemoteDescription(answer);
          set("ready");
        } catch {
          handlers.onError?.("connection");
          set("error");
          cleanup();
        }
      },

      interrupt() {
        if (disposed) return;
        sessionInterrupt();
      },

      stopAssistant() {
        if (disposed) return;
        send({ type: "response.cancel" });
        if (audioEl) {
          try {
            audioEl.pause();
          } catch {
            /* ignore */
          }
        }
        handlers.onAssistantAudioEnd?.();
        if (state === "assistant_speaking") set("ready");
      },

      disconnect() {
        if (state === "ended") return;
        cleanup();
        set("ended");
      },

      getState() {
        return state;
      },
    };
  },
};
