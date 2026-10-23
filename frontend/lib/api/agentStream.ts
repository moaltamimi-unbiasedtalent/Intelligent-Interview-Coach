/** 04C: bounded SSE parser. No eval, HTML rendering, write retries or raw-event forwarding. */
import type { AgentRunResponse } from "./types";

export interface AgentStreamCallbacks {
  onRun?: (id: string) => void;
  onProgress?: (event: string) => void;
}

export async function readAgentStream(response: Response, callbacks: AgentStreamCallbacks): Promise<AgentRunResponse> {
  if (!response.body) throw new Error("Stream unavailable.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: AgentRunResponse | undefined;
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      buffer = buffer.replace(/\r\n/g, "\n");
      if (buffer.length > 2_000_000) throw new Error("Stream frame too large.");
      let end: number;
      while ((end = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        const kind = frame.split("\n").find((x) => x.startsWith("event:"))?.slice(6).trim();
        const data = frame.split("\n").filter((x) => x.startsWith("data:")).map((x) => x.slice(5).trimStart()).join("\n");
        if (!data) continue;
        const parsed = JSON.parse(data) as Record<string, unknown>;
        if (kind === "run" && typeof parsed.run_id === "string" && /^[a-f0-9]{32}$/.test(parsed.run_id)) callbacks.onRun?.(parsed.run_id);
        if (kind === "progress" && typeof parsed.event_type === "string") callbacks.onProgress?.(parsed.event_type);
        if (kind === "stopping") callbacks.onProgress?.("stopping");
        if (kind === "error") throw new Error("The preparation request could not complete.");
        if (kind === "result") {
          if (typeof parsed.run_id !== "string" || typeof parsed.status !== "string" || !Array.isArray(parsed.conversation)) throw new Error("Invalid stream result.");
          result = parsed as unknown as AgentRunResponse;
        }
      }
      if (done) break;
    }
    if (!result) throw new Error("Connection ended before completion. Restore the saved run instead of resending.");
    return result;
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
