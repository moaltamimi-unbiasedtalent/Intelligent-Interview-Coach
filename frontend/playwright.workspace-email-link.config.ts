import { defineConfig, devices } from "@playwright/test";
if (!process.env.BASE_URL || !process.env.LINK_API_URL || !process.env.LINK_ACCOUNTS_FILE || !process.env.LINK_OUTPUT_DIR) throw new Error("Isolated Workspace email-link harness required");
export default defineConfig({ outputDir: process.env.LINK_OUTPUT_DIR, testDir: "./workspace_email_link_e2e", workers: 1, retries: 0, timeout: 90_000, expect: { timeout: 10_000 },
  use: { baseURL: process.env.BASE_URL, trace: "off", screenshot: "off", video: "off" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }] });
