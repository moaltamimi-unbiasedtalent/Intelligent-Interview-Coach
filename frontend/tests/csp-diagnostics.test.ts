import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { BrowserDiagnostics, consoleClassification, DIAGNOSTIC_LIMIT, observeBaselineOperation, safePageErrorKind, safeSource, safeViolationSnapshot } from "../csp/diagnostics";

const privateText = "candidate-canary@example.invalid password-canary cookie-canary token-canary private-candidate-answer";
const privateUrl = `https://user:password-canary@app.staging.example.com/private-candidate-answer?token=token-canary#cookie-canary`;

describe("CSP evidence privacy boundary", () => {
  it("retains every authored journey stage, including pre-fix bootstrap refusal", () => {
    const source = readFileSync("csp/hydration.spec.ts", "utf8");
    const authored = [...source.matchAll(/result.stage = "([^"]+)"/g)].map(match => match[1]);
    authored.push("/history", "/opportunities");
    const d = new BrowserDiagnostics();
    for (const stage of authored) d.pageError(stage);
    expect(d.snapshot().events.map(event => event.stage)).toEqual(authored);
  });
  it.each([
    privateText,
    `Failed to load resource: the server responded with a status of 503 (${privateText})`,
    `Minified React error #418; visit https://example.invalid/?args[]=${privateText}`,
    `Hydration failed ${privateText}`,
    `Refused to execute inline script ${privateText}`,
  ])("never retains private text, including suffixes of recognized errors", text => {
    const d = new BrowserDiagnostics();
    d.console(text, { url: privateUrl, lineNumber: 3, columnNumber: 4 }, privateText, "unexpected");
    d.request("request_failed", { url: privateUrl, method: privateText, resourceType: privateText, error: privateText }, privateText);
    d.request("http_error", { url: privateUrl, method: "GET", resourceType: "fetch", status: 503 }, "/history");
    d.pageError(privateText);
    const serialized = JSON.stringify(d.snapshot());
    for (const canary of privateText.split(" ")) expect(serialized).not.toContain(canary);
    expect(serialized).not.toContain("https://user");
    expect(serialized).not.toContain("?token");
    expect(d.snapshot().events[0].stage).toBe("unknown");
  });

  it("projects only known routes, never arbitrary hosts, assets, query strings or fragments", () => {
    expect(safeSource("https://app.staging.example.com/history?token=private#private")).toEqual({ origin: "app", path: "/history" });
    expect(safeSource("https://api.staging.example.com/api/v1/history/interviews")).toEqual({ origin: "api", path: "/api/v1/history/interviews" });
    expect(safeSource("https://app.staging.example.com/_next/static/private.js")).toEqual({ origin: "app", path: "next_static_asset" });
    expect(safeSource("https://private-candidate.example/history")).toEqual({ origin: "external", path: "redacted" });
    expect(safeSource(privateText)).toEqual({ origin: "unknown", path: "redacted" });
  });

  it("retains useful error codes without retaining their unrestricted payloads", () => {
    expect(consoleClassification("Minified React error #418; private details")).toEqual({ classification: "react_error", text: "Minified React error #418" });
    expect(consoleClassification("Failed to load resource: the server responded with a status of 404 (private)").text).toBe("HTTP resource error 404");
    expect(consoleClassification("custom private details").text).toBe("[redacted console error]");
    const d = new BrowserDiagnostics();
    d.request("request_failed", { url: privateUrl, method: "GET", resourceType: "script", error: "net::ERR_CONNECTION_REFUSED" }, "sign_in_document");
    expect(d.snapshot().events[0].failure).toBe("ERR_CONNECTION_REFUSED");
  });

  it("distinguishes repeated messages and source identities using only opaque references", () => {
    const d = new BrowserDiagnostics();
    for (const text of [privateText, privateText, "a different private message"]) d.console(text, { url: privateUrl }, "/history", "unexpected");
    d.console(privateText, { url: "https://app.staging.example.com/another-private-path" }, "/history", "unexpected");
    const result = d.snapshot();
    expect(result.groups.map(g => g.count)).toEqual([2, 1, 1]);
    expect(result.events.map(e => e.source_id)).toEqual(["source-1", "source-1", "source-1", "source-2"]);
    expect(JSON.stringify(result)).not.toContain("another-private-path");
  });

  it("bounds retained events/groups/sources but keeps accurate counts beyond the boundary", () => {
    const d = new BrowserDiagnostics();
    for (let i = 0; i < DIAGNOSTIC_LIMIT + 7; i++) d.console(`private-${i}`, { url: `https://app.staging.example.com/private-${i}` }, "/history", "unexpected");
    d.console("private-0", { url: "https://app.staging.example.com/private-0" }, "/history", "unexpected");
    const result = d.snapshot();
    expect(result.total_events).toBe(DIAGNOSTIC_LIMIT + 8);
    expect(result.retained_events).toBe(DIAGNOSTIC_LIMIT);
    expect(result.groups).toHaveLength(DIAGNOSTIC_LIMIT);
    expect(result.groups[0].count).toBe(2);
    expect(result.ungrouped_events).toBe(7);
    expect(result.dropped_events).toBe(8);
    expect(result.console_counts.unexpected).toBe(DIAGNOSTIC_LIMIT + 8);
    expect(result.counts.console).toBe(DIAGNOSTIC_LIMIT + 8);
  });

  it("keeps all console buckets and request failures separate without changing assertions", () => {
    const d = new BrowserDiagnostics();
    for (const bucket of ["inline_refusal", "expected_401", "unexpected"] as const) d.console(privateText, {}, "sign_in_form", bucket);
    d.request("http_error", { url: privateUrl, method: "POST", resourceType: "fetch", status: 401 }, "sign_in_form");
    d.request("external_request", { url: privateUrl, method: "GET", resourceType: "image" }, "/history");
    expect(d.snapshot().console_counts).toEqual({ inline_refusal: 1, expected_401: 1, unexpected: 1 });
    expect(d.snapshot().counts).toEqual({ console: 3, page_error: 0, request_failed: 0, http_error: 1, external_request: 1 });
  });

  it("records journey-relative time and safe locations, and snapshots cannot mutate counters", () => {
    let now = 1000;
    const d = new BrowserDiagnostics(() => now);
    now = 1017.7;
    d.console(privateText, { url: privateUrl, lineNumber: 2, columnNumber: 3 }, "/opportunities", "unexpected");
    expect(d.snapshot().events[0]).toMatchObject({ elapsed_ms: 18, stage: "/opportunities", line: 2, column: 3 });
    const copy = d.snapshot();
    copy.events[0].stage = privateText; copy.groups[0].count = 0; copy.console_counts.unexpected = 0;
    expect(d.snapshot().groups[0].count).toBe(1);
    expect(d.snapshot().console_counts.unexpected).toBe(1);
    expect(d.snapshot().events[0].stage).toBe("/opportunities");
  });

  it("keeps failure-path evidence available without swallowing a failed assertion", () => {
    const d = new BrowserDiagnostics();
    let evidence;
    expect(() => {
      try { d.console(privateText, {}, "nonce_rotation_and_spoof_refusal", "unexpected"); expect(d.snapshot().console_counts.unexpected).toBe(0); }
      finally { evidence = d.snapshot(); }
    }).toThrow();
    expect(evidence!.console_counts.unexpected).toBe(1);
    expect(evidence!.events[0].stage).toBe("nonce_rotation_and_spoof_refusal");
  });
});


describe("baseline operation evidence", () => {
  it("bounds and allowlists violation snapshots without exposing canary content", () => {
    (window as unknown as {cspEvents: string[]}).cspEvents = ["script-src-elem:inline", privateText, ...Array(110).fill(privateText)];
    const snapshot = safeViolationSnapshot();
    expect(snapshot).toHaveLength(100);
    expect(snapshot[0]).toBe("script-src-elem:inline");
    expect(snapshot[1]).toBe("other");
    for (const canary of privateText.split(" ")) expect(JSON.stringify(snapshot)).not.toContain(canary);
  });
  it("records the selected operation and preserves its result", async () => {
    const result: Record<string, unknown> = {};
    const value = await observeBaselineOperation(result, "field_visibility", async () => true);
    expect(value).toBe(true);
    expect(result.baseline_operation).toEqual({ operation: "field_visibility", outcome: "passed" });
  });
  it.each(["email_fill", "password_fill", "submit_click", "zero_login", "no_account"] as const)("retains only bounded failure metadata for %s and rethrows", async operation => {
    const result: Record<string, unknown> = {};
    const error = new Error(privateText);
    error.name = "TimeoutError";
    await expect(observeBaselineOperation(result, operation, () => { throw error; })).rejects.toBe(error);
    expect(result.baseline_operation).toEqual({ operation, outcome: "timeout" });
    for (const canary of privateText.split(" ")) expect(JSON.stringify(result)).not.toContain(canary);
  });
  it("does not turn unexpected failures into success", async () => {
    const result: Record<string, unknown> = {};
    const error = new Error(privateText);
    await expect(observeBaselineOperation(result, "submit_click", () => { throw error; })).rejects.toBe(error);
    expect(result.baseline_operation).toEqual({ operation: "submit_click", outcome: "failed" });
  });
  it("keeps page-error types allowlisted and never serializes messages or custom names", () => {
    const d = new BrowserDiagnostics();
    const error = new TypeError(privateText);
    d.pageError("original_bootstrap_refusal", error);
    error.name = privateText;
    d.pageError("original_bootstrap_refusal", error);
    expect(safePageErrorKind(null)).toBe("unknown");
    expect(d.snapshot().events.map(event => event.error_kind)).toEqual(["TypeError", "other"]);
    for (const canary of privateText.split(" ")) expect(JSON.stringify(d.snapshot())).not.toContain(canary);
  });
});
