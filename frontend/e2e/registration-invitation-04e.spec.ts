import { expect, test, type Page } from "@playwright/test";

// 04E: invitation-only registration in the real Next.js app, with CONTROLLED API responses at the network layer. The server's own refusal logic (hashed single-use codes,
// uniform refusal, no enumeration, expiry, revocation, concurrency, OIDC) is proven by tests/test_invitations_04e.py and tests/test_invitations_oidc_04e.py against a real
// database. Nothing here contacts a provider or sends an email.

const UNIFORM_OK = { message: "If that email can be registered, we've sent a verification link." };
const REFUSAL = { error: { code: "invitation_required", message: "server english text that must never be shown", request_id: "req_e2e" } };

async function mock(page: Page, opts: { validCode?: string } = {}) {
  const seen: Record<string, unknown>[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_e2e" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me")) return json({ error: { code: "unauthorized", message: "Authentication required.", request_id: "req_e2e" } }, 401);
    if (url.includes("/auth/register") && method === "POST") {
      const body = JSON.parse(route.request().postData() ?? "{}");
      seen.push(body);
      // The mock mirrors the server rule only to drive the UI: a missing or wrong code is ONE refusal, whatever the email.
      return opts.validCode && body.invitation_code === opts.validCode ? json(UNIFORM_OK, 201) : json(REFUSAL, 403);
    }
    return json({});
  });
  return seen;
}

async function submit(page: Page) {
  await page.getByLabel("Email", { exact: true }).fill("new@example.com");
  await page.getByLabel(/^Password/).fill("correcthorsebattery");
  await page.getByRole("button", { name: /create account/i }).click();
}

test("uninvited registration is refused with one calm localized message and no confirmation", async ({ page }) => {
  await mock(page);
  await page.goto("/register");
  await expect(page.getByLabel("Invitation code")).toBeVisible();
  await submit(page);
  await expect(page.getByRole("alert").filter({ hasText: "private beta" })).toContainText("A valid invitation is required to register during the private beta");
  await expect(page.getByText("server english text that must never be shown")).toHaveCount(0);
  await expect(page.getByText(/verification link/i)).toHaveCount(0);
});

test("an invited registration with a typed code succeeds with the uniform confirmation", async ({ page }) => {
  const seen = await mock(page, { validCode: "good-code" });
  await page.goto("/register");
  await page.getByLabel("Invitation code").fill("good-code");
  await submit(page);
  await expect(page.getByText(/verification link/i)).toBeVisible();
  expect(seen[0]).toMatchObject({ invitation_code: "good-code", email: "new@example.com" });
});

test("an invitation link prefills the code, removes it from the address bar and stores nothing", async ({ page }) => {
  const seen = await mock(page, { validCode: "link-code_42" });
  await page.goto("/register#invitation=link-code_42");
  await expect(page.getByLabel("Invitation code")).toHaveValue("link-code_42");
  await expect.poll(() => new URL(page.url()).hash).toBe("");
  expect(page.url()).not.toContain("link-code_42");
  const stored = await page.evaluate(() => JSON.stringify({ l: { ...localStorage }, s: { ...sessionStorage }, c: document.cookie }));
  expect(stored).not.toContain("link-code_42");
  await submit(page);
  await expect(page.getByText(/verification link/i)).toBeVisible();
  expect(seen[0]).toMatchObject({ invitation_code: "link-code_42" });
});

test("the refusal is localized in the interface language (German)", async ({ page, baseURL }) => {
  await page.context().addCookies([{ name: "ask4mo_locale", value: "de", url: baseURL ?? "http://localhost:3000" }]);
  await mock(page);
  await page.goto("/register");
  await expect(page.getByLabel("Einladungscode")).toBeVisible();
  await page.getByLabel("E-Mail", { exact: false }).first().fill("neu@example.com");
  await page.getByLabel(/^Passwort/).fill("correcthorsebattery");
  await page.getByRole("button", { name: /konto erstellen|registrieren/i }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Einladung" })).toContainText("gültige Einladung");
});
