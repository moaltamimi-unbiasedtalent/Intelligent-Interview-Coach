import { defineConfig, devices } from '@playwright/test';
if (process.env.BASE_URL !== 'https://app.staging.example.com' || !/^[a-f0-9]{16}$/.test(process.env.CAMPAIGN_ID ?? '')) throw new Error('Disposable campaign boundary required');
export default defineConfig({
  testDir: './integration', testMatch: 'task07.spec.ts', timeout: 45_000,
  workers: 1, retries: 0, outputDir: process.env.CAMPAIGN_PRIVATE_RESULTS,
  reporter: [['./integration/safe-reporter.ts']],
  use: { ...devices['Desktop Chrome'], baseURL: process.env.BASE_URL, ignoreHTTPSErrors: true,
    trace: 'off', screenshot: 'off', video: 'off',
    launchOptions: { args: ['--no-proxy-server', '--host-resolver-rules=MAP app.staging.example.com 127.0.0.1, MAP api.staging.example.com 127.0.0.1'] } },
});
