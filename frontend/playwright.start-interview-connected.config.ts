import { defineConfig, devices } from "@playwright/test";
if (process.env.JOURNEY_MODE !== "real" || !process.env.BASE_URL || !process.env.JOURNEY_INVITATIONS_FILE || !process.env.JOURNEY_API_URL || !process.env.JOURNEY_OUTPUT_DIR) {
  throw new Error("An isolated real-stack journey is required");
}
export default defineConfig({
  outputDir: process.env.JOURNEY_OUTPUT_DIR, testDir: "./start_interview_connected_e2e", workers: 1, retries: 0,
  timeout: 180_000, expect: { timeout: 15_000 },
  use: { baseURL: process.env.BASE_URL, trace: "off", screenshot: "off", video: "off" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
