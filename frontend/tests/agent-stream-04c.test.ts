import { afterEach, expect, it, vi } from "vitest";
import { api } from "@/lib/api/client";
import { readAgentStream } from "@/lib/api/agentStream";

const rid = "a".repeat(32);
const result = { run_id: rid, status: "completed", conversation: [], response: "Safe answer" };
function response(chunks: string[]) {
  return new Response(new ReadableStream({ start(controller) {
    const encoder = new TextEncoder();
    for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
    controller.close();
  } }), { headers: { "content-type": "text/event-stream" } });
}
afterEach(() => vi.unstubAllGlobals());

it("parses split frames, CRLF and heartbeats and returns only a completed result", async () => {
  const onRun = vi.fn(), onProgress = vi.fn();
  const text = `event: run\r\ndata: {"run_id":"${rid}"}\r\n\r\n: keep-alive\r\n\r\nevent: progress\r\ndata: {"event_type":"tool_completed"}\r\n\r\nevent: result\r\ndata: ${JSON.stringify(result)}\r\n\r\n`;
  const r = await readAgentStream(response([text.slice(0, 17), text.slice(17, 91), text.slice(91)]), { onRun, onProgress });
  expect(r.run_id).toBe(rid);
  expect(onRun).toHaveBeenCalledWith(rid);
  expect(onProgress).toHaveBeenCalledWith("tool_completed");
});

it("never retries a start when the stream disconnects after run admission", async () => {
  const fetch = vi.fn().mockResolvedValue(response([`event: run\ndata: {"run_id":"${rid}"}\n\n`]));
  vi.stubGlobal("fetch", fetch);
  await expect(api.agent.startStream({ goal: "Hello" }, {})).rejects.toThrow(/Restore/);
  expect(fetch).toHaveBeenCalledTimes(1);
});

it("falls back once only for an explicitly unsupported stream route", async () => {
  const fetch = vi.fn().mockResolvedValueOnce(new Response("", { status: 501 }))
    .mockResolvedValueOnce(new Response(JSON.stringify(result), { headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", fetch);
  const r = await api.agent.startStream({ goal: "Hello" }, {});
  expect(r.run_id).toBe(rid);
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(fetch.mock.calls[1][0]).toMatch(/\/agent\/run$/);
});

it("does not fall back on forbidden, budget, validation or provider failures", async () => {
  for (const status of [401, 403, 422, 429, 503]) {
    const fetch = vi.fn().mockResolvedValue(new Response("{}", { status, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetch);
    await expect(api.agent.startStream({ goal: "Hello" }, {})).rejects.toBeDefined();
    expect(fetch).toHaveBeenCalledTimes(1);
  }
});

it("rejects malformed or oversized frames", async () => {
  await expect(readAgentStream(response(['event: result\ndata: {}\n\n']), {})).rejects.toThrow(/Invalid/);
  await expect(readAgentStream(response(['x'.repeat(2_000_001)]), {})).rejects.toThrow(/large/);
});
