import { defineConfig, devices } from "@playwright/test";

if (!process.env.BASE_URL) throw new Error("BASE_URL required");
export default defineConfig({
  testDir: "./candidate_connected_e2e", testMatch: "candidate-invitation.spec.ts", workers: 1, retries: 0,
  timeout: 180_000, expect: { timeout: 15_000 },
  use: { baseURL: process.env.BASE_URL, trace: "off" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
