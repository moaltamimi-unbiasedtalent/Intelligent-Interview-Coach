import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";

function mockFetch(impl: () => Promise<Response> | Response) {
  vi.stubGlobal("fetch", vi.fn(impl));
}

function jsonResponse(body: unknown, init: ResponseInit & { requestId?: string } = {}) {
  const headers = new Headers({ "content-type": "application/json" });
  if (init.requestId) headers.set("x-request-id", init.requestId);
  return new Response(JSON.stringify(body), { status: init.status ?? 200, headers });
}

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("returns a typed health response on success", async () => {
    mockFetch(() =>
      jsonResponse({ status: "ok", service: "intelligent-interview-coach", version: "0.1.0" }),
    );
    const health = await api.health();
    expect(health.status).toBe("ok");
    expect(health.service).toBe("intelligent-interview-coach");
  });

  it("returns a typed capabilities response", async () => {
    mockFetch(() =>
      jsonResponse({
        career_intelligence: true,
        interview_practice: true,
        knowledge_base: true,
        evaluation: true,
        live_interview_enabled: false,
        agentic_rag: false,
        agent_memory: false,
        human_in_the_loop: false,
      }),
    );
    const caps = await api.capabilities();
    expect(caps.live_interview_enabled).toBe(false);
  });

  it("turns a network failure into a safe ApiError (no raw cause)", async () => {
    mockFetch(() => {
      throw new Error("ECONNREFUSED 127.0.0.1:8000 secret-internal-detail");
    });
    await expect(api.health()).rejects.toBeInstanceOf(ApiError);
    try {
      await api.health();
    } catch (e) {
      const err = e as ApiError;
      expect(err.kind).toBe("network");
      expect(err.userMessage).toMatch(/couldn't connect/i);
      // The raw cause must never be surfaced.
      expect(err.message).not.toContain("ECONNREFUSED");
      expect(err.userMessage).not.toContain("secret-internal-detail");
    }
  });

  it("maps a 503 error envelope to a safe unavailable error", async () => {
    mockFetch(() =>
      jsonResponse(
        { error: { code: "not_configured", message: "This feature needs a model.", request_id: "req_1" } },
        { status: 503 },
      ),
    );
    try {
      await api.capabilities();
      throw new Error("should have thrown");
    } catch (e) {
      const err = e as ApiError;
      expect(err.status).toBe(503);
      expect(err.kind).toBe("unavailable");
      expect(err.requestId).toBe("req_1");
      expect(err.userMessage).not.toContain("Traceback");
    }
  });
});
