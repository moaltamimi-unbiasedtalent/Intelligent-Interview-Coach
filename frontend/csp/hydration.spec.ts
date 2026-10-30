import { test, expect } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";
import { version as playwrightVersion } from "@playwright/test/package.json";
import { BrowserDiagnostics, observeBaselineOperation, safeViolationSnapshot } from "./diagnostics";
const account = JSON.parse(readFileSync(process.env.CSP_CREDENTIALS!, "utf8"));
const api = "https://api.staging.example.com/api/v1";
const before = process.env.CSP_PHASE === "before";

test("CSP real edge: baseline refusal or secure hydrated synthetic journey", async ({ page, context }) => {
  const result: Record<string, unknown> = { phase: before ? "before" : "after", passed: false };
  const external = { length: 0 }, pageErrors = { length: 0 }, consoleErrors = { length: 0 };
  const diagnostics = new BrowserDiagnostics();
  result.tooling = { node: process.version, playwright: playwrightVersion, browser: context.browser()?.version() ?? "unavailable" };
  let inlineRefusals = 0, loginRequests = 0, expectedUnauthenticatedErrors = 0;
  await context.route("**/*", route => {
    const url = new URL(route.request().url());
    if (!["https://app.staging.example.com", "https://api.staging.example.com"].includes(url.origin)) {
      external.length++;
      diagnostics.request("external_request", { url: route.request().url(), method: route.request().method(), resourceType: route.request().resourceType() }, result.stage);
      return route.abort();
    }
    return route.continue(); // Real API and every image request remain untouched.
  });
  page.on("request", request => { if (request.url() === api + "/auth/login") loginRequests++; });
  page.on("pageerror", error => { pageErrors.length++; diagnostics.pageError(result.stage, error); });
  page.on("requestfailed", request => diagnostics.request("request_failed", { url: request.url(), method: request.method(), resourceType: request.resourceType(), error: request.failure()?.errorText }, result.stage));
  page.on("response", response => {
    diagnostics.assetResponse({ url: response.url(), resourceType: response.request().resourceType(), status: response.status() }, result.stage);
    if (response.status() >= 400) diagnostics.request("http_error", { url: response.url(), method: response.request().method(), resourceType: response.request().resourceType(), status: response.status() }, result.stage);
  });
  page.on("console", message => {
    if (message.type() !== "error") return;
    const text = message.text();
    let bucket: "inline_refusal" | "expected_401" | "unexpected";
    if (/inline script/i.test(text) && /violat|refus/i.test(text)) { inlineRefusals++; bucket = "inline_refusal"; }
    else if (/^Failed to load resource: the server responded with a status of 401(?: \(|$)/.test(text)) { expectedUnauthenticatedErrors++; bucket = "expected_401"; }
    else { consoleErrors.length++; bucket = "unexpected"; }
    diagnostics.console(text, message.location(), result.stage, bucket);
  });
  await page.addInitScript(() => {
    (window as unknown as {cspEvents: string[]}).cspEvents = [];
    document.addEventListener("securitypolicyviolation", event => {
      const directive = ["script-src", "script-src-elem", "script-src-attr", "connect-src", "img-src", "style-src", "font-src", "media-src", "default-src"].includes(event.effectiveDirective) ? event.effectiveDirective : "other";
      const blocked = ["inline", "eval"].includes(event.blockedURI) ? event.blockedURI : "redacted";
      (window as unknown as {cspEvents: string[]}).cspEvents.push(directive + ":" + blocked);
    });
  });
  try {
    result.stage = "sign_in_document";
    const response = (await page.goto("/sign-in?next=%2Faccount", {waitUntil: "domcontentloaded"}))!;
    const policy = response.headers()["content-security-policy"];
    expect(response.headers()["content-security-policy-report-only"]).toBeUndefined();
    result.effective_policy = policy;
    result.security_headers = Object.fromEntries(["strict-transport-security", "permissions-policy", "x-frame-options", "x-content-type-options", "referrer-policy", "cache-control"].map(name => [name, response.headers()[name]]));
    expect((await response.headersArray()).filter(h => h.name.toLowerCase() === "content-security-policy")).toHaveLength(1);
    for (const [header, value] of [["strict-transport-security", "max-age=31536000; includeSubDomains; preload"], ["permissions-policy", "camera=(), geolocation=(), microphone=(self)"], ["x-frame-options", "DENY"], ["x-content-type-options", "nosniff"], ["referrer-policy", "strict-origin-when-cross-origin"]]) expect(response.headers()[header]).toContain(value);
    expect(policy).toContain("connect-src 'self' https://api.staging.example.com wss://api.staging.example.com");
    for (const d of ["object-src 'none'", "form-action 'self'", "frame-ancestors 'none'"]) expect(policy).toContain(d);
    if (before) {
      result.stage = "original_bootstrap_refusal";
      result.baseline_operation = { operation: "inline_refusal", outcome: "started" };
      await expect.poll(() => inlineRefusals).toBeGreaterThan(0);
      result.baseline_operation = { operation: "policy", outcome: "started" };
      expect(policy).toContain("script-src 'self';");
      expect(policy).not.toContain("'nonce-");
      result.baseline_operation = { operation: "violation_snapshot", outcome: "started" };
      result.baseline_violation_snapshot = await page.evaluate(safeViolationSnapshot);
      const fieldsVisible = await observeBaselineOperation(result, "field_visibility", async () => await page.getByLabel("Email", {exact: true}).isVisible() && await page.getByLabel("Password", {exact: true}).isVisible());
      result.form_fields_visible = fieldsVisible;
      if (fieldsVisible) {
        await observeBaselineOperation(result, "email_fill", () => page.getByLabel("Email", {exact: true}).fill(account.email));
        await observeBaselineOperation(result, "password_fill", () => page.getByLabel("Password", {exact: true}).fill(account.password));
        await observeBaselineOperation(result, "submit_click", () => page.getByRole("button", {name: /^sign in$/i}).click());
      }
      result.baseline_operation = { operation: "zero_login", outcome: "started" };
      expect(loginRequests).toBe(0);
      result.baseline_operation = { operation: "no_account", outcome: "started" };
      expect(await page.getByRole("heading", {name: "Your account"}).count()).toBe(0);
      result.hydrated_sign_in = false;
      result.bootstrap_inline_refusals = inlineRefusals;
      result.violation_events = await observeBaselineOperation(result, "violation_snapshot", () => page.evaluate(() => (window as unknown as {cspEvents: string[]}).cspEvents));
    } else {
    result.stage = "sign_in_form";
    await page.getByLabel("Email", {exact: true}).fill(account.email);
    await page.getByLabel("Password", {exact: true}).fill(account.password);
    await page.getByRole("button", {name: /^sign in$/i}).click();
      result.stage = "authenticated_account";
      await expect(page).toHaveURL(/\/account$/);
      await expect(page.getByRole("heading", {name: "Your account"})).toBeVisible();
      expect(loginRequests).toBe(1);
      const cookie = (await context.cookies(api)).find(c => c.name === "ask4mo_session")!;
      expect(Boolean(cookie)).toBe(true);
      expect({secure: cookie.secure, httpOnly: cookie.httpOnly, sameSite: cookie.sameSite}).toEqual({secure: true, httpOnly: true, sameSite: "Lax"});
      result.secure_session = true;
      result.cookie_flags = {secure: cookie.secure, httpOnly: cookie.httpOnly, sameSite: cookie.sameSite};
      const nonce = policy.match(/'nonce-([^']+)'/)![1];
      expect(nonce).toMatch(/^[A-Za-z0-9+/]{43}=$/);
      expect(policy.split(";").find(s => s.trim().startsWith("script-src "))).not.toMatch(/unsafe-inline|unsafe-eval|\*/);
      expect(response.headers()["cache-control"]).toContain("no-store");
      const scriptNonces = await page.locator("script:not([src]):not([type='application/ld+json'])").evaluateAll(nodes => nodes.map(n => (n as HTMLScriptElement).nonce));
      expect(scriptNonces.length).toBeGreaterThan(1);
      expect(scriptNonces.every(n => n === nonce)).toBe(true);
      result.inline_scripts_nonced = scriptNonces.length;
      result.cache_control = response.headers()["cache-control"];
      // Preserve actual image requests; only wait for the UI content this CSP test owns.
      result.authenticated_reads = [];
      for (const [path, endpoint] of [["/history", "/history/interviews"], ["/opportunities", "/opportunities"]]) {
        result.stage = path;
        const data = page.waitForResponse(response => new URL(response.url()).pathname === "/api/v1" + endpoint && response.request().method() === "GET");
        await page.goto(path, {waitUntil: "domcontentloaded"});
        const status = (await data).status();
        expect(status).toBe(200);
        (result.authenticated_reads as {path: string, status: number}[]).push({path, status});
        await expect(page.locator("h1")).toBeVisible();
        await expect(page.locator("h1")).not.toHaveText(/sign in|not found|error/i);
      }
      result.stage = "nonce_rotation_and_spoof_refusal";
      const spoofedDocument = "https://app.staging.example.com/account";
      await page.route(spoofedDocument, route => route.continue({headers: {...route.request().headers(), "x-nonce": "attacker", "content-security-policy": "script-src 'unsafe-inline'"}}));
      const next = (await page.goto("/account", {waitUntil: "domcontentloaded"}))!;
      await expect(page.getByRole("heading", {name: "Your account"})).toBeVisible();
      const nextPolicy = next.headers()["content-security-policy"];
      expect(nextPolicy).not.toBe(policy);
      expect(nextPolicy).not.toContain("attacker");
      result.nonce_rotated = true;
      result.spoofed_request_refused = true;
      await page.unroute(spoofedDocument);
      expect(inlineRefusals).toBe(0);
      expect(consoleErrors).toHaveLength(0);
      expect(pageErrors).toHaveLength(0);
      result.hydrated_sign_in = true;
      result.bootstrap_inline_refusals = 0;
      // A nonce-less payload and a nonce replayed from a previous document stay blocked.
      result.stage = "negative_injection";
      await page.evaluate(old => {
        for (const value of [undefined, old]) {
          const script = document.createElement("script");
          if (value) script.nonce = value;
          script.textContent = "window.__cspInjected = true";
          document.body.appendChild(script);
        }
      }, nonce);
      await expect.poll(() => page.evaluate(() => (window as unknown as {cspEvents: string[]}).cspEvents.length)).toBe(2);
      expect(await page.evaluate(() => "__cspInjected" in window)).toBe(false);
      result.negative_injection_blocked = true;
      result.violation_events = await page.evaluate(() => (window as unknown as {cspEvents: string[]}).cspEvents);
      result.stage = "logout_request";
      const loggedOut = page.waitForResponse(response => new URL(response.url()).pathname === "/api/v1/auth/logout" && response.request().method() === "POST");
      await page.locator("#main").getByRole("button", {name: "Sign out", exact: true}).click();
      const logoutStatus = (await loggedOut).status();
      expect(logoutStatus).toBe(200);
      result.logout_response_status = logoutStatus;
      result.stage = "logout_redirect_and_revocation";
      await expect.poll(() => new URL(page.url()).pathname).toBe("/sign-in");
      await expect(page.getByLabel("Email", {exact: true})).toBeVisible();
      const afterLogout = await page.evaluate(async url => (await fetch(url, {credentials: "include"})).status, api + "/auth/me");
      expect(afterLogout).toBe(401);
      expect((await context.cookies(api)).some(cookie => cookie.name === "ask4mo_session")).toBe(false);
      result.session_after_logout = afterLogout;
      result.session_cookie_cleared = true;
      result.logout_path = new URL(page.url()).pathname;
      expect(inlineRefusals).toBe(2); // Exactly the two intentional negative payloads.
      expect(consoleErrors).toHaveLength(0);
      expect(pageErrors).toHaveLength(0);
      result.negative_injection_refusals = 2;
      result.logout = true;
    }
    expect(external).toHaveLength(0);
    result.external_attempts = external.length;
    result.stage = "complete";
    result.login_requests = loginRequests;
    result.console_error_count = consoleErrors.length;
    result.expected_unauthenticated_http_errors = expectedUnauthenticatedErrors;
    result.page_error_count = pageErrors.length;
    result.passed = true;
  } catch (error) {
    if (before && result.baseline_operation && typeof result.baseline_operation === "object") {
      const current = result.baseline_operation as { operation: string; outcome: string };
      if (current.outcome === "started") current.outcome = error instanceof Error && error.name === "TimeoutError" ? "timeout" : "failed";
    }
    throw error;
  } finally {
    result.diagnostics = diagnostics.snapshot();
    result.observed_external_attempts = external.length;
    result.observed_expected_unauthenticated_http_errors = expectedUnauthenticatedErrors;
    result.observed_inline_refusals = inlineRefusals;
    result.observed_login_requests = loginRequests;
    result.unexpected_console_errors = consoleErrors.length;
    result.observed_page_errors = pageErrors.length;
    writeFileSync(process.env.CSP_BROWSER_SUMMARY!, JSON.stringify(result, null, 2));
  }
});
