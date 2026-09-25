import { expect, test, type Page } from "@playwright/test";

// Capstone P8 §55: public `/` vs authenticated `/app` migration. No redirect loops; deep
// links preserved; post-login lands on /app.

const ACCOUNT = {
  user_id: 1, email: "user@example.com", display_name: null, platform_role: "user",
  tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: [], response_detail: "brief",
  interface_locale: "en", conversation_language: "en",
};

function mockAuth(page: Page, opts: { signedIn?: boolean } = {}) {
  const state = { signedIn: opts.signedIn ?? false };
  return page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (b: unknown, s = 200) =>
      route.fulfill({ status: s, contentType: "application/json",
                     headers: { "x-request-id": "r" }, body: JSON.stringify(b) });
    if (url.includes("/auth/login")) { state.signedIn = true; return json({ message: "ok" }); }
    if (url.includes("/auth/me")) {
      return state.signedIn ? json(ACCOUNT)
        : json({ error: { code: "unauthorized", message: "x", request_id: "r" } }, 401);
    }
    return json({});
  });
}

test("anonymous / shows the marketing home (not the app)", async ({ page }) => {
  await mockAuth(page, { signedIn: false });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Prepare for the interview that matters/i })).toBeVisible();
  // Marketing chrome: no app primary nav.
  await expect(page.getByRole("navigation", { name: "Primary" })).toHaveCount(0);
  // No redirect loop — we stayed on /.
  await expect(page).toHaveURL(/\/$/);
});

test("unauthenticated /app redirects to sign-in preserving next", async ({ page }) => {
  await mockAuth(page, { signedIn: false });
  await page.goto("/app");
  await expect(page).toHaveURL(/\/sign-in\?next=%2Fapp/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("authenticated visitor on / sees a link back into the app", async ({ page }) => {
  await mockAuth(page, { signedIn: true });
  await page.goto("/");
  const go = page.getByRole("link", { name: /Go to your workspace/i });
  await expect(go).toBeVisible();
  await expect(go).toHaveAttribute("href", "/app");
});

test("authenticated /app renders the candidate home", async ({ page }) => {
  await mockAuth(page, { signedIn: true });
  await page.goto("/app");
  await expect(page.getByText("Ask More. Be More.")).toBeVisible();
  // App chrome present (brand links to /app).
  await expect(page.getByRole("link", { name: "Ask4Mo — home" })).toHaveAttribute("href", "/app");
});

test("deep link to a protected route still works when authenticated", async ({ page }) => {
  await mockAuth(page, { signedIn: true });
  await page.goto("/progress");
  await expect(page).toHaveURL(/\/progress$/);
});
