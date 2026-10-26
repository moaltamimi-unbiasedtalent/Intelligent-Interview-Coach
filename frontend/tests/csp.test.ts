import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { middleware } from "../middleware";
import { pagePolicy } from "../lib/security/csp";

const nonce = "A".repeat(43) + "=";
describe("enforced rendering CSP", () => {
  it("keeps exact application/API origins and existing security directives", () => {
    const policy = pagePolicy(nonce, "https://api.staging.example.com/api/v1");
    expect(policy).toContain(`script-src 'self' 'nonce-${nonce}'`);
    expect(policy).toContain("connect-src 'self' https://api.staging.example.com wss://api.staging.example.com");
    for (const directive of ["object-src 'none'", "frame-ancestors 'none'", "form-action 'self'", "base-uri 'self'", "script-src-attr 'none'"]) expect(policy).toContain(directive);
    const scripts = policy.split(";").find(s => s.trim().startsWith("script-src "))!;
    expect(scripts).not.toMatch(/unsafe-inline|unsafe-eval|\*/);
    expect(policy).not.toContain("connect-src *");
  });
  it.each(["https://a:b@api.example.com/api/v1", "https://api.example.com/?x=1", "https://api.example.com/#x", "http://external.example.com", "javascript:alert(1)"])("rejects unsafe public origin %s", api => {
    expect(() => pagePolicy(nonce, api)).toThrow();
  });
  it("supports existing loopback development/API-mocked topology without relaxing scripts", () => {
    expect(pagePolicy(nonce, "http://localhost:8000/api/v1")).toContain("http://localhost:8000 ws://localhost:8000");
  });
  it.each(["", "attacker", "A".repeat(43) + "; script-src *"])("rejects a malformed nonce", value => expect(() => pagePolicy(value, "https://api.example.com")).toThrow());
  it("replaces forged request values, propagates the rendering policy and never reuses a nonce", () => {
    const request = new NextRequest("https://app.staging.example.com/account", { headers: {"x-nonce": "attacker", "Content-Security-Policy": "script-src 'unsafe-inline'"} });
    const a = middleware(request), b = middleware(request);
    const csp = a.headers.get("Content-Security-Policy")!;
    expect(csp).not.toBe(b.headers.get("Content-Security-Policy"));
    expect(csp).not.toContain("attacker");
    expect(a.headers.get("x-middleware-request-content-security-policy")).toBe(csp);
    const value = a.headers.get("x-middleware-request-x-nonce")!;
    expect(value).toMatch(/^[A-Za-z0-9+/]{43}=$/);
    expect(csp).toContain(`'nonce-${value}'`);
    expect(a.headers.get("Cache-Control")).toContain("no-store");
  });
});
