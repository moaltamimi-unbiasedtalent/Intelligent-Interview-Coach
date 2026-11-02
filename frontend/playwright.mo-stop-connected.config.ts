import { defineConfig, devices } from "@playwright/test";
if (!process.env.BASE_URL || !process.env.STORY_API_URL || !process.env.STORY_ACCOUNTS_FILE || !process.env.MO_STOP_STATE_DIR) throw new Error("Disposable Mo Stop harness required");
export default defineConfig({ testDir: "./mo_stop_connected_e2e", outputDir: process.env.MO_STOP_STATE_DIR + "/results", workers: 1, retries: 0, timeout: 90_000, expect: { timeout: 10_000 }, use: { baseURL: process.env.BASE_URL, trace: "off", screenshot: "off", video: "off" }, projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }] });
