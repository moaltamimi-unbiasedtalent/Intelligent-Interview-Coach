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
  // 04D: ONE statement about price and purchase on every candidate surface (free, invitation-only private beta; nothing can be purchased; no price).
  await expect(page.getByTestId("home-beta-pricing")).toContainText("free, invitation-only private beta");
  await expect(page.getByTestId("home-beta-pricing")).toContainText("no price applies");
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

test("the retired How it works route redirects into the combined Product page", async ({ page }) => {
  await page.goto("/getting-started");
  await expect(page).toHaveURL(/\/product#how-it-works$/);
  await expect(page.locator("#how-it-works")).toBeVisible();
});

test("Pricing shows Basic as free and Premium as not available yet, with no purchase path (W12.4D-P3)", async ({ page }) => {
  await page.goto("/pricing");
  await expect(page.getByTestId("plan-basic")).toContainText("Free in the beta");
  await expect(page.getByTestId("plan-premium")).toContainText("Not available yet");
  // 04D: no price figure anywhere on the page, and the same single statement as every other candidate surface.
  await expect(page.getByTestId("premium-beta-statement")).toContainText("Nothing can be purchased and no price applies");
  await expect(page.getByTestId("pricing-billing-note")).toHaveText(await page.getByTestId("premium-beta-statement").innerText());
  expect(await page.getByTestId("pricing-plans").innerText()).not.toMatch(/[€$£]\s?\d/);
  await expect(page.getByTestId("plan-premium").getByRole("link")).toHaveCount(0);            // nothing to click: no purchase path
  await expect(page.locator('a[href*="plan=premium"], a[href*="checkout"]')).toHaveCount(0);
  await expect(page.getByTestId("plan-overview")).toBeVisible();
  // Card entry belongs to the payment provider, not the marketing page.
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
  await expect(page.getByRole("heading", { name: /Your Opportunity is private/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /No audio storage/i })).toBeVisible();
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
  // The detailed product features and workflow live together on Product, not as duplicate homepage sections.
  await expect(page.getByRole("heading", { name: /create an opportunity/i })).toHaveCount(0);
  await expect(page.locator('a[href="/product#how-it-works"]').first()).toBeVisible();
  await expect(page.locator('a[href="/product"]').first()).toBeVisible();
  await expect(page.getByRole("heading", { name: /company intelligence/i })).toHaveCount(0);
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
  await expect(page.getByRole("heading", { name: /interview preparation, built around your next opportunity/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /company intelligence/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /what makes ask4mo different/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /built around your job/i })).toBeVisible();
  // V4.3: the workflow is the interactive seven-stage map (Opportunity > Company research > Evidence > Preparation > Practice > Feedback > Progress).
  await expect(page.getByTestId("workflow-map")).toBeVisible();
  await expect(page.getByRole("tab")).toHaveCount(7);
  await expect(page.getByRole("tab", { name: /company research/i })).toBeVisible();
  await expect(page.getByTestId("workflow-sequence")).toContainText("Opportunity");
  await expect(page.getByRole("link", { name: /Get started/i }).first()).toBeVisible();
});

test("trust page states Wave 5/6 boundaries (P10B Wave 7)", async ({ page }) => {
  await page.goto("/trust");
  await expect(page.getByRole("heading", { name: /Your Opportunity is private/i })).toBeVisible();
  await page.getByTestId("trust-group-ai").locator("summary").click();
  await expect(page.getByText(/not integrated/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: /AI suggestions are not facts/i })).toBeVisible();
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
