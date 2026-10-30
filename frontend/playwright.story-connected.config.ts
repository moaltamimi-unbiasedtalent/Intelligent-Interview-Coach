import { defineConfig, devices } from "@playwright/test";
if (!process.env.BASE_URL || !process.env.STORY_API_URL || !process.env.STORY_ACCOUNTS_FILE) throw new Error("Isolated Story Bank harness required");
export default defineConfig({ testDir: "./story_connected_e2e", workers: 1, retries: 0, timeout: 90_000, expect: { timeout: 10_000 },
  use: { baseURL: process.env.BASE_URL, trace: "off", screenshot: "off", video: "off" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }] });
