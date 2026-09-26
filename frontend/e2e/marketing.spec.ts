import { expect, test, type Page } from "@playwright/test";

// Capstone P8 §54: public marketing site. A public visitor (no session) can reach Home,
// Product, Pricing, Trust and the policy pages; CTAs route correctly; pricing is truthful
// (no billing); locale switching works; mobile renders. No backend/provider calls needed —
// marketing is public and renders with an unresolved session.

test("public Home renders the hero and primary CTAs", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Prepare for the interview that matters/i }),
  ).toBeVisible();
  // Get started routes to registration (a real free path).
  const cta = page.getByRole("link", { name: /Get started/i }).first();
  await expect(cta).toBeVisible();
  // Footer states no billing (truthful).
  await expect(page.getByText(/No online payments are processed/i)).toBeVisible();
});

test("marketing nav reaches Product, Pricing and Trust", async ({ page }) => {
  await page.goto("/");
  for (const [name, path] of [
    ["Product", "/product"],
    ["Pricing", "/pricing"],
    ["Trust", "/trust"],
  ] as const) {
    const link = page.getByRole("navigation", { name: "Marketing" }).getByRole("link", { name });
    await expect(link).toHaveAttribute("href", path);
  }
});

test("Pricing is truthful: plans shown, no billing, no card fields", async ({ page }) => {
  await page.goto("/pricing");
  await expect(page.getByTestId("plan-basic")).toContainText("€0");
  await expect(page.getByTestId("plan-premium")).toContainText("€19.99");
  // Premium is a preview request, never a purchase.
  await expect(page.getByTestId("plan-note-premium")).toContainText(/cannot be purchased online/i);
  await expect(page.getByTestId("no-billing-note")).toBeVisible();
  // No fake checkout: no "Buy now"/"Subscribe now" and no card input anywhere.
  await expect(page.getByRole("button", { name: /buy now|subscribe now/i })).toHaveCount(0);
  await expect(page.locator('input[type="number"], input[autocomplete="cc-number"]')).toHaveCount(0);
});

test("policy pages carry the engineering-draft banner", async ({ page }) => {
  for (const path of ["/privacy", "/terms", "/ai-transparency"]) {
    await page.goto(path);
    await expect(page.getByTestId("legal-draft-banner")).toBeVisible();
  }
});

test("Trust page lists factual controls", async ({ page }) => {
  await page.goto("/trust");
  await expect(page.getByText(/Private by default/i).first()).toBeVisible();
  await expect(page.getByText(/No audio storage/i)).toBeVisible();
});

test("Get started routes to register; Sign in routes to sign-in", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: /Get started/i }).first().click();
  await expect(page).toHaveURL(/\/register$/);
  await page.goto("/");
  await page.getByRole("link", { name: "Sign in" }).first().click();
  await expect(page).toHaveURL(/\/sign-in$/);
});

test("locale cookie localizes the marketing interface", async ({ page, baseURL }) => {
  await page.context().addCookies([
    { name: "ask4mo_locale", value: "de", url: baseURL ?? "http://localhost:3000" },
  ]);
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
  await expect(page.getByRole("navigation", { name: "Marketing" })
    .getByRole("link", { name: "Produkt" })).toBeVisible();
});

test("marketing home renders on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Prepare for the interview that matters/i }),
  ).toBeVisible();
  // No horizontal overflow (AC-19): body is not wider than the viewport.
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  expect(overflow).toBe(false);
});
