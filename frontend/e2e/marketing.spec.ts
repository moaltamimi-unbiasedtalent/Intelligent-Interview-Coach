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

test("home tells an Opportunity-centred story (P10B Wave 7)", async ({ page }) => {
  await page.goto("/");
  // The product is framed as one connected system per job, with the Opportunity journey.
  await expect(page.getByRole("heading", { name: /one connected system/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /create an opportunity/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /company intelligence/i }).first()).toBeVisible();
  // Differentiation is stated factually (W9.10 replaced the comparative "not another generic interview
  // generator" jab with a neutral heading; the four differentiators beneath it are unchanged).
  await expect(page.getByRole("heading", { name: /what makes ask4mo different/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /built around your job/i })).toBeVisible();
});

test("public home makes no fabricated or unsupported provider claims (P10B Wave 7)", async ({ page }) => {
  await page.goto("/");
  const body = (await page.locator("body").innerText()).toLowerCase();
  // No employee-review provider is claimed as integrated on the public site.
  expect(body).not.toContain("glassdoor");
  expect(body).not.toContain("kununu");
  // No fabricated social proof or unsupported absolutes.
  for (const banned of ["testimonial", "trusted by", "5-star", "100% accurate", "guaranteed", "bias-free"]) {
    expect(body).not.toContain(banned);
  }
});

test("product page explains the Opportunity workflow (P10B Wave 7)", async ({ page }) => {
  await page.goto("/product");
  await expect(page.getByRole("heading", { name: /one connected system/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /understand the company/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Get started/i }).first()).toBeVisible();
});

test("trust page states Wave 5/6 boundaries (P10B Wave 7)", async ({ page }) => {
  await page.goto("/trust");
  await expect(page.getByText(/Your Opportunity is private/i)).toBeVisible();
  await expect(page.getByText(/not integrated/i)).toBeVisible();
  await expect(page.getByText(/AI suggestions are not facts/i)).toBeVisible();
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
