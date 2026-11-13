import type { Reporter, TestCase, TestResult } from '@playwright/test/reporter';
import { writeFileSync } from 'node:fs';

const UI01_STAGES = [
  'sign_in_document',
  'csp_header_validation',
  'sign_in_form_ready',
  'sign_in_submitted',
  'account_navigation',
  'session_cookie_verified',
  'history_navigation',
  'history_api_response',
  'history_heading_validation',
  'history_image_validation',
  'opportunities_navigation',
  'opportunities_api_response',
  'opportunities_heading_validation',
  'before_csp_injection',
  'csp_injection_attempt',
  'csp_refusal_observed',
  'injected_script_nonexecution',
  'return_to_account',
  'logout_requested',
  'logout_response',
  'signed_out_navigation',
  'session_revocation_verified',
  'no_external_requests',
  'complete',
] as const;

export type Ui01Stage = (typeof UI01_STAGES)[number];
export const UI01_ACTIVE_STAGE = 'ui01_active_stage';
export const UI01_LAST_COMPLETED_STAGE = 'ui01_last_completed_stage';

function readStage(annotations: TestResult['annotations'], type: string): Ui01Stage | null {
  const description = annotations.findLast(annotation => annotation.type === type)?.description;
  return UI01_STAGES.find(stage => stage === description) ?? null;
}

type SafeTestRow = {
  id: string;
  status: string;
  duration_ms: number;
  csp_inline_refusals: number;
  active_stage?: Ui01Stage | null;
  last_completed_stage?: Ui01Stage | null;
};

export default class SafeReporter implements Reporter {
  rows: SafeTestRow[] = [];
  onTestEnd(test: TestCase, result: TestResult) {
    // No error messages, DOM, cookies, attachments or raw console output.
    const id = test.title.split(' ')[0];
    this.rows.push({
      id,
      status: result.status,
      duration_ms: result.duration,
      csp_inline_refusals: Number(test.annotations.find(a => a.type === 'csp_inline_refusals')?.description ?? '0'),
      ...(id === 'UI-01' ? {
        active_stage: readStage(result.annotations, UI01_ACTIVE_STAGE),
        last_completed_stage: readStage(result.annotations, UI01_LAST_COMPLETED_STAGE),
      } : {}),
    });
    writeFileSync(process.env.CAMPAIGN_BROWSER_REPORT!, JSON.stringify({tests: this.rows}, null, 2));
  }
}
