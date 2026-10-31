import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { BrowserDiagnostics, consoleClassification, DIAGNOSTIC_LIMIT, observeBaselineOperation, safePageErrorKind, safeSource, safeViolationSnapshot, loginRequestFacts, loginResponseFacts } from "../csp/diagnostics";

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

  it("records only bounded static script response metadata and allowlisted network failures", () => {
    const d = new BrowserDiagnostics();
    const url = `https://app.staging.example.com/_next/static/${privateText}.js?token=token-canary`;
    d.assetResponse({ url, resourceType: "script", status: 503 }, "sign_in_form");
    d.assetResponse({ url: privateUrl, resourceType: "script", status: 200 }, "sign_in_form");
    d.assetResponse({ url, resourceType: "image", status: 200 }, "sign_in_form");
    d.request("request_failed", { url, method: "GET", resourceType: "script", error: "net::ERR_HTTP2_PROTOCOL_ERROR" }, "sign_in_form");
    d.request("request_failed", { url, method: "GET", resourceType: "script", error: `net::ERR_FAILED ${privateText}` }, "sign_in_form");
    const result = d.snapshot();
    expect(result.counts.asset_response).toBe(1);
    expect(result.events[0]).toMatchObject({ path: "next_static_asset", status: 503 });
    expect(result.events[1].failure).toBe("ERR_HTTP2_PROTOCOL_ERROR");
    expect(result.events[2].failure).toBe("redacted");
    for (const canary of privateText.split(" ")) expect(JSON.stringify(result)).not.toContain(canary);
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
    expect(d.snapshot().counts).toEqual({ console: 3, page_error: 0, request_failed: 0, http_error: 1, external_request: 1, asset_response: 0, login_request: 0, login_response: 0 });
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


describe("synthetic login diagnostic privacy", () => {
  it("projects request presence, types and lengths without values", () => {
    const d = new BrowserDiagnostics();
    d.loginRequest(JSON.stringify({ email: privateText, password: privateText }), "application/json; charset=utf-8", "sign_in_form");
    d.loginRequest(JSON.stringify({ email: 1 }), "text/plain", "sign_in_form");
    expect(d.snapshot().events[0]).toMatchObject({ json_content_type: true, email_present: true, password_present: true, email_string: true, password_string: true });
    expect(d.snapshot().events[1]).toMatchObject({ json_content_type: false, email_present: true, password_present: false, email_string: false, password_string: false });
    for (const canary of privateText.split(" ")) expect(JSON.stringify(d.snapshot())).not.toContain(canary);
    expect(loginRequestFacts("{", "application/json").email_present).toBe(false);
    expect(loginRequestFacts("x".repeat(8193), "application/json").password_present).toBe(false);
  });
  it("classifies only established safe 422 envelopes", () => {
    const envelope = (code: string, message: string, details?: unknown) => JSON.stringify({ error: { code, message, request_id: privateText, details, extra: privateText } });
    expect(loginResponseFacts(422, envelope("invalid_request", "Request validation failed.", []))).toEqual({ classification: "request_schema_envelope", envelope: true });
    expect(loginResponseFacts(422, envelope("validation_error", "Enter a valid email address."))).toEqual({ classification: "email_validation_envelope", envelope: true });
    expect(loginResponseFacts(422, envelope("validation_error", privateText))).toEqual({ classification: "application_validation_envelope", envelope: true });
    for (const raw of [privateText, "{}", envelope("unknown", privateText), "x".repeat(4097)]) expect(loginResponseFacts(422, raw)).toEqual({ classification: "unknown", envelope: false });
    expect(loginResponseFacts(200, envelope("invalid_request", privateText, []))).toEqual({ classification: "unknown", envelope: false });
    const d = new BrowserDiagnostics();
    for (let i = 0; i < DIAGNOSTIC_LIMIT + 5; i++) d.loginResponse(422, envelope("validation_error", privateText), "sign_in_form");
    expect(d.snapshot().retained_events).toBe(DIAGNOSTIC_LIMIT);
    expect(d.snapshot().dropped_events).toBe(5);
    for (const canary of privateText.split(" ")) expect(JSON.stringify(d.snapshot())).not.toContain(canary);
  });
});
