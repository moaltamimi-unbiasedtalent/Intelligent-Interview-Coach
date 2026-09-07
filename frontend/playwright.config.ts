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
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:3000",
    trace: "on-first-retry",
  },
  webServer: {
    command: "npm run build && npm run start -- --port 3000",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
