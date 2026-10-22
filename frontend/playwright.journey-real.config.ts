import { defineConfig, devices } from "@playwright/test";

/**
 * 04D: the Candidate journey against a REAL stack (the local launcher scripts/e2e/journey_stack.py, or a hosted staging stack).
 * No web server is started here: BASE_URL must already serve the web app, and the API it talks to must be the one the web build points at
 * (NEXT_PUBLIC_API_BASE_URL). Required environment: JOURNEY_MODE=real, BASE_URL, JOURNEY_INVITATIONS_FILE; optional JOURNEY_LANGUAGES, JOURNEY_API_URL,
 * JOURNEY_VARIANT. See the docs at the top of scripts/e2e/journey_stack.py.
 */
const BASE_URL = process.env.BASE_URL;
if (!BASE_URL) throw new Error("BASE_URL is required for the real-stack journey");

export default defineConfig({
  testDir: "./e2e",
  testMatch: /candidate-(journey|provider)-04d\.spec\.ts/,
  timeout: 180_000,
  expect: { timeout: 15_000 },
  workers: 1,
  fullyParallel: false,
  retries: 0,
  use: { baseURL: BASE_URL, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
