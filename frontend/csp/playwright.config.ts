import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: ".", testMatch: "hydration.spec.ts", workers: 1, retries: 0,
  timeout: 45_000, expect: { timeout: 10_000 }, reporter: "line",
  outputDir: process.env.CSP_PRIVATE_RESULTS,
  use: {
    baseURL: "https://app.staging.example.com", ignoreHTTPSErrors: true,
    trace: "off", screenshot: "off", video: "off",
    launchOptions: { args: ["--no-proxy-server", `--host-resolver-rules=MAP app.staging.example.com ${process.env.CSP_EDGE_IP}, MAP api.staging.example.com ${process.env.CSP_EDGE_IP}`] },
  },
});
