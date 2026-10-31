import { defineConfig, devices } from "@playwright/test";
if (!process.env.BASE_URL || !process.env.STORY_API_URL || !process.env.STORY_ACCOUNTS_FILE || !process.env.STORY_OUTPUT_DIR) throw new Error("Isolated story Practice harness required");
export default defineConfig({ outputDir: process.env.STORY_OUTPUT_DIR, testDir: "./story_deletion_connected_e2e", workers: 1, retries: 0,
  timeout: 90_000, expect: { timeout: 10_000 }, use: { baseURL: process.env.BASE_URL, trace: "off", screenshot: "off", video: "off" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }] });
