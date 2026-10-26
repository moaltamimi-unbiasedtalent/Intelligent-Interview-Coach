import type { Reporter, TestCase, TestResult } from '@playwright/test/reporter';
import { writeFileSync } from 'node:fs';
export default class SafeReporter implements Reporter {
  rows: {id: string; status: string; duration_ms: number; csp_inline_refusals: number}[] = [];
  onTestEnd(test: TestCase, result: TestResult) {
    // No error messages, DOM, cookies, attachments or raw console output.
    this.rows.push({id: test.title.split(' ')[0], status: result.status, duration_ms: result.duration, csp_inline_refusals: Number(test.annotations.find(a => a.type === 'csp_inline_refusals')?.description ?? '0')});
    writeFileSync(process.env.CAMPAIGN_BROWSER_REPORT!, JSON.stringify({tests: this.rows}, null, 2));
  }
}
