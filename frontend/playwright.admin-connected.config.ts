import { defineConfig, devices } from "@playwright/test";

if (!process.env.BASE_URL || !process.env.ADMIN_API_URL || !process.env.ADMIN_ACCOUNTS_FILE) {
  throw new Error("The isolated Admin connected harness is required");
}
export default defineConfig({
  testDir: "./connected_e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  workers: 1,
  retries: 0,
  use: { baseURL: process.env.BASE_URL, trace: "off", screenshot: "off", video: "off" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
