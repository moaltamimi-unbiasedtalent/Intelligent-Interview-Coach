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
  it("puts the selected report generation in the consent body, never in fetch options", async () => {
    mockFetch(() => jsonResponse({ share_id: 1, status: "active" }));
    const controller = new AbortController();
    await api.shares.create(7, "interview_report", "9", true, {
      expectedReportGeneration: "1".repeat(32), signal: controller.signal,
    });
    const [, options] = vi.mocked(fetch).mock.calls[0];
    expect(JSON.parse(options!.body as string)).toEqual({ workspace_id: 7, resource_type: "interview_report",
      resource_id: "9", consent: true, expected_report_generation: "1".repeat(32) });
    expect(options).not.toHaveProperty("expectedReportGeneration");
    expect(options!.signal).toBe(controller.signal);
  });

  it("keeps ordinary story sharing body unchanged", async () => {
    mockFetch(() => jsonResponse({ share_id: 1, status: "active" }));
    await api.shares.create(7, "story", "5", true);
    expect(JSON.parse(vi.mocked(fetch).mock.calls[0][1]!.body as string)).toEqual({
      workspace_id: 7, resource_type: "story", resource_id: "5", consent: true,
    });
  });

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
      // P10B-W9.1: a failed fetch while the browser is online is "unreachable" (an Ask4Mo /
      // backend / CORS problem) — NOT "network", and it must never blame the user's connection.
      expect(err.kind).toBe("unreachable");
      expect(err.userMessage).toMatch(/ask4mo/i);
      expect(err.userMessage).not.toMatch(/check your (internet|connection)/i);
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
