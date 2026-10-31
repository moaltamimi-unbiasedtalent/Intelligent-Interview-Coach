/** Qualification-only evidence. Never serialize console arguments, bodies or raw URLs. */
import { createHash } from "node:crypto";

export const DIAGNOSTIC_LIMIT = 100;
const stages = new Set(["sign_in_document", "original_bootstrap_refusal", "sign_in_form", "authenticated_account", "/history", "/opportunities", "nonce_rotation_and_spoof_refusal", "negative_injection", "logout_request", "logout_redirect_and_revocation", "complete"]);
const routes = new Set(["/sign-in", "/account", "/history", "/opportunities", "/api/v1/auth/login", "/api/v1/auth/me", "/api/v1/auth/logout", "/api/v1/history/interviews", "/api/v1/opportunities", "/api/v1/health"]);
const resources = new Set(["document", "stylesheet", "image", "media", "font", "script", "xhr", "fetch", "other", "websocket", "manifest", "texttrack", "eventsource"]);
const networkCodes = new Set(["ERR_ABORTED", "ERR_CONNECTION_REFUSED", "ERR_NAME_NOT_RESOLVED", "ERR_CERT_AUTHORITY_INVALID", "ERR_FAILED", "ERR_CONNECTION_RESET", "ERR_TIMED_OUT", "ERR_HTTP2_PROTOCOL_ERROR", "ERR_INCOMPLETE_CHUNKED_ENCODING", "ERR_CONNECTION_CLOSED", "ERR_CONTENT_DECODING_FAILED", "ERR_CONTENT_LENGTH_MISMATCH", "ERR_EMPTY_RESPONSE", "ERR_INVALID_RESPONSE"]);
type Kind = "console" | "page_error" | "request_failed" | "http_error" | "external_request" | "asset_response" | "login_request" | "login_response";
type Fields = Record<string, string | number | boolean>;
type Event = Fields & { event_id: string; group_id: string; kind: Kind; stage: string; elapsed_ms: number };

export function safeSource(raw = "") {
  try {
    const url = new URL(raw);
    const origin = url.origin === "https://app.staging.example.com" ? "app" : url.origin === "https://api.staging.example.com" ? "api" : "external";
    const path = origin === "external" ? "redacted" : routes.has(url.pathname) ? url.pathname : url.pathname.startsWith("/_next/static/") ? "next_static_asset" : url.pathname === "/_next/image" ? "next_image" : "redacted";
    return { origin, path };
  } catch { return { origin: "unknown", path: "redacted" }; }
}

export function consoleClassification(text: string) {
  // Emit authored templates only. Even recognizable errors can append private payloads.
  const status = text.match(/^Failed to load resource: the server responded with a status of ([1-5]\d{2})(?: \(|$)/);
  if (status) return { classification: "http_resource_error", text: `HTTP resource error ${status[1]}` };
  const react = text.match(/^Minified React error #(\d{1,4});/);
  if (react) return { classification: "react_error", text: `Minified React error #${react[1]}` };
  if (/hydration|hydrating/i.test(text)) return { classification: "hydration_error", text: "Hydration error [details redacted]" };
  if (/content security policy|violates.*directive|refused to execute inline script/i.test(text)) return { classification: "csp_error", text: "CSP error [details redacted]" };
  return { classification: "unclassified_error", text: "[redacted console error]" };
}


/** Fixed operation labels and outcomes only; never serialize caught errors or inputs. */
export type BaselineOperation = "inline_refusal" | "policy" | "field_visibility" | "email_fill" | "password_fill" | "submit_click" | "zero_login" | "no_account" | "violation_snapshot";
type BaselineEvidence = { operation: BaselineOperation; outcome: "started" | "passed" | "timeout" | "failed" };
export async function observeBaselineOperation<T>(target: Record<string, unknown>, operation: BaselineOperation, action: () => Promise<T> | T): Promise<T> {
  const evidence: BaselineEvidence = { operation, outcome: "started" };
  target.baseline_operation = evidence;
  try {
    const value = await action();
    evidence.outcome = "passed";
    return value;
  } catch (error) {
    evidence.outcome = error instanceof Error && error.name === "TimeoutError" ? "timeout" : "failed";
    throw error;
  }
}

export function safePageErrorKind(error: unknown): string {
  if (!(error instanceof Error)) return "unknown";
  return ["Error", "TypeError", "ReferenceError", "SyntaxError", "RangeError"].includes(error.name) ? error.name : "other";
}

/** Run inside the page: export only a bounded allowlisted CSP-violation projection. */
export function safeViolationSnapshot(): string[] {
  const allowed = new Set(["script-src:inline", "script-src-elem:inline", "script-src-attr:inline", "script-src:eval", "script-src-elem:eval", "script-src-attr:eval"]);
  return (window as unknown as {cspEvents: string[]}).cspEvents.slice(0, 100).map(value => allowed.has(value) ? value : "other");
}

/** Fixed projections only. Payloads are inspected in memory and never retained. */
export function loginRequestFacts(raw: string | null, contentType: string) {
  let body: unknown;
  try { body = raw !== null && raw.length <= 8192 ? JSON.parse(raw) : null; } catch { body = null; }
  const obj = body !== null && typeof body === "object" && !Array.isArray(body) ? body as Record<string, unknown> : {};
  const email = obj.email, password = obj.password;
  return { json_content_type: /^application\/json(?:\s*;|$)/i.test(contentType), email_present: Object.hasOwn(obj, "email"), password_present: Object.hasOwn(obj, "password"), email_string: typeof email === "string", password_string: typeof password === "string", email_length_valid: typeof email === "string" && email.length >= 3 && email.length <= 320, password_length_valid: typeof password === "string" && password.length >= 1 && password.length <= 200 };
}

export function loginResponseFacts(status: number, raw: string | null) {
  if (status !== 422 || raw === null || raw.length > 4096) return { classification: "unknown", envelope: false };
  try {
    const body: unknown = JSON.parse(raw);
    if (!body || typeof body !== "object" || Array.isArray(body)) return { classification: "unknown", envelope: false };
    const error = (body as Record<string, unknown>).error;
    if (!error || typeof error !== "object" || Array.isArray(error)) return { classification: "unknown", envelope: false };
    const e = error as Record<string, unknown>;
    if (typeof e.message !== "string" || typeof e.request_id !== "string") return { classification: "unknown", envelope: false };
    if (e.code === "invalid_request" && Array.isArray(e.details)) return { classification: "request_schema_envelope", envelope: true };
    if (e.code === "validation_error") return { classification: e.message === "Enter a valid email address." ? "email_validation_envelope" : "application_validation_envelope", envelope: true };
  } catch { /* Unknown response: retain no body or exception. */ }
  return { classification: "unknown", envelope: false };
}

export class BrowserDiagnostics {
  private readonly started: number;
  private readonly events: Event[] = [];
  private readonly groups = new Map<string, { group_id: string; count: number }>();
  private readonly sources = new Map<string, string>();
  private readonly totals: Record<Kind, number> = { console: 0, page_error: 0, request_failed: 0, http_error: 0, external_request: 0, asset_response: 0, login_request: 0, login_response: 0 };
  private consoleCounts = { inline_refusal: 0, expected_401: 0, unexpected: 0 };
  private total = 0;
  private ungrouped = 0;

  constructor(private readonly clock: () => number = () => performance.now()) { this.started = clock(); }

  private source(raw = "") {
    const key = createHash("sha256").update(raw).digest("hex");
    if (!this.sources.has(key) && this.sources.size < DIAGNOSTIC_LIMIT) this.sources.set(key, `source-${this.sources.size + 1}`);
    return { ...safeSource(raw), source_id: this.sources.get(key) ?? "not_retained" };
  }

  private add(kind: Kind, stage: unknown, fields: Fields, identity = "") {
    this.total++;
    this.totals[kind]++;
    // Private equality fingerprint stays in bounded memory; never export it or raw text.
    const key = createHash("sha256").update(kind).update(identity).update(JSON.stringify(fields)).digest("hex");
    let group = this.groups.get(key);
    if (!group && this.groups.size < DIAGNOSTIC_LIMIT) {
      group = { group_id: `group-${this.groups.size + 1}`, count: 0 };
      this.groups.set(key, group);
    }
    if (group) group.count++; else this.ungrouped++;
    if (this.events.length < DIAGNOSTIC_LIMIT) {
      const elapsed = this.clock() - this.started;
      this.events.push({ ...fields, event_id: `event-${this.total}`, group_id: group?.group_id ?? "not_retained", kind, stage: typeof stage === "string" && stages.has(stage) ? stage : "unknown", elapsed_ms: Number.isFinite(elapsed) ? Math.max(0, Math.round(elapsed)) : 0 });
    }
  }

  console(text: string, location: { url?: string; lineNumber?: number; columnNumber?: number }, stage: unknown, bucket: keyof typeof this.consoleCounts) {
    this.consoleCounts[bucket]++;
    const integer = (n?: number) => Number.isInteger(n) && n! >= 0 && n! <= 10_000_000 ? n! : -1;
    this.add("console", stage, { type: "error", bucket, ...consoleClassification(text), ...this.source(location.url), line: integer(location.lineNumber), column: integer(location.columnNumber) }, text);
  }

  pageError(stage: unknown, error?: unknown) { this.add("page_error", stage, { text: "[redacted page error]", error_kind: safePageErrorKind(error) }); }

  request(kind: "request_failed" | "http_error" | "external_request", request: { url: string; method: string; resourceType: string; error?: string; status?: number }, stage: unknown) {
    const fields: Fields = { ...this.source(request.url), method: ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"].includes(request.method) ? request.method : "other", resource_type: resources.has(request.resourceType) ? request.resourceType : "other" };
    if (kind === "request_failed") {
      const code = request.error?.match(/^(?:net::)?(ERR_[A-Z0-9_]+)$/)?.[1];
      fields.failure = code && networkCodes.has(code) ? code : "redacted";
    }
    if (kind === "http_error") fields.status = Number.isInteger(request.status) && request.status! >= 400 && request.status! <= 599 ? request.status! : -1;
    this.add(kind, stage, fields);
  }

  assetResponse(request: { url: string; resourceType: string; status: number }, stage: unknown) {
    const source = safeSource(request.url);
    if (source.origin !== "app" || source.path !== "next_static_asset" || request.resourceType !== "script") return;
    const status = Number.isInteger(request.status) && request.status >= 100 && request.status <= 599 ? request.status : -1;
    this.add("asset_response", stage, { ...this.source(request.url), resource_type: "script", status });
  }

  loginRequest(raw: string | null, contentType: string, stage: unknown) {
    this.add("login_request", stage, loginRequestFacts(raw, contentType));
  }

  loginResponse(status: number, raw: string | null, stage: unknown) {
    this.add("login_response", stage, loginResponseFacts(status, raw));
  }

  snapshot() {
    return { version: 1, limit: DIAGNOSTIC_LIMIT, total_events: this.total, retained_events: this.events.length, dropped_events: this.total - this.events.length, ungrouped_events: this.ungrouped, counts: { ...this.totals }, console_counts: { ...this.consoleCounts }, events: this.events.map(event => ({ ...event })), groups: [...this.groups.values()].map(group => ({ ...group })) };
  }
}
