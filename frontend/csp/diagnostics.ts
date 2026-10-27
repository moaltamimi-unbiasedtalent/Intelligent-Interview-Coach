/** Qualification-only evidence. Never serialize console arguments, bodies or raw URLs. */
import { createHash } from "node:crypto";

export const DIAGNOSTIC_LIMIT = 100;
const stages = new Set(["sign_in_document", "original_bootstrap_refusal", "sign_in_form", "authenticated_account", "/history", "/opportunities", "nonce_rotation_and_spoof_refusal", "negative_injection", "logout_request", "logout_redirect_and_revocation", "complete"]);
const routes = new Set(["/sign-in", "/account", "/history", "/opportunities", "/api/v1/auth/login", "/api/v1/auth/me", "/api/v1/auth/logout", "/api/v1/history/interviews", "/api/v1/opportunities", "/api/v1/health"]);
const resources = new Set(["document", "stylesheet", "image", "media", "font", "script", "xhr", "fetch", "other", "websocket", "manifest", "texttrack", "eventsource"]);
const networkCodes = new Set(["ERR_ABORTED", "ERR_CONNECTION_REFUSED", "ERR_NAME_NOT_RESOLVED", "ERR_CERT_AUTHORITY_INVALID", "ERR_FAILED", "ERR_CONNECTION_RESET", "ERR_TIMED_OUT"]);
type Kind = "console" | "page_error" | "request_failed" | "http_error" | "external_request";
type Fields = Record<string, string | number>;
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

export class BrowserDiagnostics {
  private readonly started: number;
  private readonly events: Event[] = [];
  private readonly groups = new Map<string, { group_id: string; count: number }>();
  private readonly sources = new Map<string, string>();
  private readonly totals: Record<Kind, number> = { console: 0, page_error: 0, request_failed: 0, http_error: 0, external_request: 0 };
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

  pageError(stage: unknown) { this.add("page_error", stage, { text: "[redacted page error]" }); }

  request(kind: "request_failed" | "http_error" | "external_request", request: { url: string; method: string; resourceType: string; error?: string; status?: number }, stage: unknown) {
    const fields: Fields = { ...this.source(request.url), method: ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"].includes(request.method) ? request.method : "other", resource_type: resources.has(request.resourceType) ? request.resourceType : "other" };
    if (kind === "request_failed") {
      const code = request.error?.match(/^(?:net::)?(ERR_[A-Z_]+)$/)?.[1];
      fields.failure = code && networkCodes.has(code) ? code : "redacted";
    }
    if (kind === "http_error") fields.status = Number.isInteger(request.status) && request.status! >= 400 && request.status! <= 599 ? request.status! : -1;
    this.add(kind, stage, fields);
  }

  snapshot() {
    return { version: 1, limit: DIAGNOSTIC_LIMIT, total_events: this.total, retained_events: this.events.length, dropped_events: this.total - this.events.length, ungrouped_events: this.ungrouped, counts: { ...this.totals }, console_counts: { ...this.consoleCounts }, events: this.events.map(event => ({ ...event })), groups: [...this.groups.values()].map(group => ({ ...group })) };
  }
}
