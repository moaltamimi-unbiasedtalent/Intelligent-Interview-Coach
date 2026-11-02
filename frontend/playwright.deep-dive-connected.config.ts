import { defineConfig, devices } from "@playwright/test";

if (
  !process.env.BASE_URL || !process.env.STORY_API_URL || !process.env.STORY_ACCOUNTS_FILE ||
  !process.env.DEEP_DIVE_STATE_DIR || !["create", "read"].includes(process.env.DEEP_DIVE_PHASE || "")
) throw new Error("Disposable Deep Dive harness required");

export default defineConfig({
  testDir: "./deep_dive_connected_e2e",
  outputDir: process.env.DEEP_DIVE_STATE_DIR + "/results",
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  use: { baseURL: process.env.BASE_URL, trace: "off", screenshot: "off", video: "off" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
