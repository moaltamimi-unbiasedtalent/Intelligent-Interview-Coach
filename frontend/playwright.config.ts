import { defineConfig, devices } from "@playwright/test";

/**
 * Next.js browser smoke suite. Starts the production build locally (reused if
 * already running). No paid provider calls; the backend is not required for these
 * shell/nav/responsive checks (capabilities are stubbed at the network layer in
 * the specs that need them).
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  // A small smoke suite against one local server — run serially for stability.
  workers: 1,
  fullyParallel: false,
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:3000",
    trace: "on-first-retry",
  },
  webServer: {
    command: "npm run build && npm run start -- --port 3000",
    url: "http://localhost:3000",
    // §35: CI must NOT reuse an existing server — a stale :3000 process could mask a
    // bad build. `!process.env.CI` is false in CI, so Playwright starts (and owns) a
    // freshly built instance there. Local devs may reuse a running dev server.
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
