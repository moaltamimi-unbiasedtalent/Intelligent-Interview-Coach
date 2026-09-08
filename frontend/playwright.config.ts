import { defineConfig, devices } from "@playwright/test";

/**
 * Next.js browser smoke suite. Starts the production build locally (reused if
 * already running). No paid provider calls; the backend is not required for these
 * shell/nav/responsive checks (capabilities are stubbed at the network layer in
 * the specs that need them).
 */
// The port is env-overridable (E2E_PORT) so the suite can run on a free port when
// :3000 is occupied by an unrelated local process; the default is unchanged (3000).
const E2E_PORT = process.env.E2E_PORT || "3000";
const E2E_URL = process.env.BASE_URL || `http://localhost:${E2E_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  // A small smoke suite against one local server — run serially for stability.
  workers: 1,
  fullyParallel: false,
  use: {
    baseURL: E2E_URL,
    trace: "on-first-retry",
  },
  webServer: {
    command: `npm run build && npm run start -- --port ${E2E_PORT}`,
    url: E2E_URL,
    // §35: CI must NOT reuse an existing server — a stale process could mask a bad
    // build. `!process.env.CI` is false in CI, so Playwright starts (and owns) a
    // freshly built instance there. Local devs may reuse a running dev server.
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
