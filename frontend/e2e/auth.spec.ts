import { expect, test, type Page } from "@playwright/test";

// Real Next.js → API browser flow for authentication, with CONTROLLED responses
// mocked at the network layer (page.route). No backend, no paid provider calls.
// A closure flag simulates the server-side session so sign-in/out changes /auth/me.

const ACCOUNT = {
  user_id: 1,
  email: "user@example.com",
  display_name: null,
  platform_role: "user",
  tier: "basic",
  status: "active",
  email_verified: true,
  providers: ["password"],
  auth_method: "session",
  capabilities: ["current_market_research"],
};

async function mockAuth(page: Page, opts: { signedIn?: boolean } = {}) {
  const state = { signedIn: opts.signedIn ?? false };
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        headers: { "x-request-id": "req_e2e" },
        body: JSON.stringify(body),
      });

    if (url.includes("/auth/me")) {
      return state.signedIn
        ? json(ACCOUNT)
        : json({ error: { code: "unauthorized", message: "Authentication required.", request_id: "req_e2e" } }, 401);
    }
    if (url.includes("/auth/login") && method === "POST") {
      state.signedIn = true;
      return json({ message: "Signed in." });
    }
    if (url.includes("/auth/logout")) {
      state.signedIn = false;
      return json({ message: "Signed out." });
    }
    if (url.includes("/auth/register")) {
      return json(
        { message: "If that email can be registered, we've sent a verification link." },
        201,
      );
    }
    // Any other API call: benign empty success.
    return json({});
  });
  return state;
}

test("unauthenticated visitor is redirected from a protected route to sign in", async ({ page }) => {
  await mockAuth(page, { signedIn: false });
  await page.goto("/progress");
  await expect(page).toHaveURL(/\/sign-in\?next=%2Fprogress/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("sign-in flow authenticates and returns to the requested page", async ({ page }) => {
  await mockAuth(page, { signedIn: false });
  await page.goto("/sign-in?next=%2Fprogress");
  await page.getByLabel("Email").fill("user@example.com");
  await page.getByLabel("Password").fill("correcthorsebattery");
  await page.getByRole("button", { name: /sign in/i }).click();
  // After login the guard bounces the auth page to the requested destination.
  await expect(page).toHaveURL(/\/progress/);
});

test("register page shows the uniform, non-enumerating confirmation", async ({ page }) => {
  await mockAuth(page, { signedIn: false });
  await page.goto("/register");
  await page.getByLabel("Email").fill("new@example.com");
  await page.getByLabel(/^Password/).fill("correcthorsebattery");
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page.getByText(/verification link/i)).toBeVisible();
});

test("account page shows the signed-in account and can sign out", async ({ page }) => {
  await mockAuth(page, { signedIn: true });
  await page.goto("/account");
  await expect(page.getByRole("heading", { name: "Your account" })).toBeVisible();
  await expect(page.getByText("user@example.com")).toBeVisible();
  // Scope to the page body (the header also has a Sign out control).
  await page.locator("#main").getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/sign-in/);
});

test("the header shows Sign in when signed out", async ({ page }) => {
  await mockAuth(page, { signedIn: false });
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Sign in" }).first()).toBeVisible();
});
