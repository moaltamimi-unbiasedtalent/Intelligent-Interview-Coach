import type { Reporter, TestCase, TestResult } from '@playwright/test/reporter';
import { writeFileSync } from 'node:fs';
export default class SafeReporter implements Reporter {
  rows: {id: string; status: string; duration_ms: number}[] = [];
  onTestEnd(test: TestCase, result: TestResult) {
    // No error messages, DOM, cookies, attachments or raw console output.
    this.rows.push({id: test.title.split(' ')[0], status: result.status, duration_ms: result.duration});
    writeFileSync(process.env.CAMPAIGN_BROWSER_REPORT!, JSON.stringify({tests: this.rows}, null, 2));
  }
}
