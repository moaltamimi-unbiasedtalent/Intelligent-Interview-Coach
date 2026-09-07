import { expect, test } from "@playwright/test";

// Next.js frontend smoke. The backend is not required: useCapabilities falls back
// to safe defaults (Live disabled) when it can't be reached, which is exactly the
// "capability false" path we assert. No paid provider calls.

test("home loads with the Precision Coach headline", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Prepare for the interview that matters/i }),
  ).toBeVisible();
});

test("home primary CTA navigates to Prepare", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Start" }).click();
  await expect(page).toHaveURL(/\/prepare$/);
  await expect(page.getByRole("heading", { name: "Senior Product Manager" })).toBeVisible();
});

test("primary navigation reaches the four candidate routes", async ({ page }) => {
  await page.goto("/");
  for (const [label, path] of [
    ["Practice", "/practice"],
    ["Progress", "/progress"],
    ["History", "/history"],
    ["Prepare", "/prepare"],
  ] as const) {
    await page.getByRole("link", { name: label }).first().click();
    await expect(page).toHaveURL(new RegExp(`${path}$`));
  }
});

test("prepare workspace is responsive (mobile shows a context tab)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 780 });
  await page.goto("/prepare");
  // Mobile: a Coach / Preparation tab set is present.
  await expect(page.getByRole("tab", { name: "Coach" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Preparation" })).toBeVisible();

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/prepare");
  // Desktop: the context rail content is shown directly.
  await expect(page.getByText("Priorities to prepare")).toBeVisible();
});

test("practice page is distraction-free and offers Type/Record", async ({ page }) => {
  await page.goto("/practice");
  await expect(
    page.getByRole("heading", { name: /aligned executives behind a roadmap/i }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /^type$/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /^record$/i })).toBeVisible();
});

test("Live is not offered when the backend capability is unavailable", async ({ page }) => {
  await page.goto("/practice");
  await expect(page.getByText(/aligned executives/i)).toBeVisible();
  await expect(page.getByText(/Live conversation practice/i)).toHaveCount(0);
});

test("no camera or microphone permission is requested on load", async ({ page }) => {
  await page.addInitScript(() => {
    (window as unknown as { __mediaRequested: boolean }).__mediaRequested = false;
    const md = navigator.mediaDevices;
    if (md && md.getUserMedia) {
      const orig = md.getUserMedia.bind(md);
      md.getUserMedia = (c?: MediaStreamConstraints) => {
        (window as unknown as { __mediaRequested: boolean }).__mediaRequested = true;
        return orig(c as MediaStreamConstraints);
      };
    }
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Start" }).click();
  await page.goto("/practice");
  const requested = await page.evaluate(
    () => (window as unknown as { __mediaRequested: boolean }).__mediaRequested,
  );
  expect(requested).toBe(false);
});
