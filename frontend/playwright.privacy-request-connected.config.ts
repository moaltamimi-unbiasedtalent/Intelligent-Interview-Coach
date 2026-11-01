import { defineConfig, devices } from "@playwright/test";
if (!process.env.BASE_URL || !process.env.STORY_API_URL || !process.env.STORY_ACCOUNTS_FILE || !process.env.STORY_OUTPUT_DIR) throw new Error("Disposable privacy harness required");
export default defineConfig({ testDir: "./privacy_request_connected_e2e", outputDir: process.env.STORY_OUTPUT_DIR, workers: 1, retries: 0, timeout: 90_000, expect: { timeout: 10_000 }, use: { baseURL: process.env.BASE_URL, trace: "off", screenshot: "off", video: "off" }, projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }] });
