import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { UI01_ACTIVE_STAGE, UI01_LAST_COMPLETED_STAGE, type Ui01Stage } from './safe-reporter';
const credentials = JSON.parse(readFileSync(process.env.CAMPAIGN_CREDENTIALS_FILE!, 'utf8'));
const api = 'https://api.staging.example.com/api/v1';
let inlineRefusals = 0;
test.beforeEach(async ({ page }) => {
  inlineRefusals = 0;
  page.on('console', message => {
    if (/inline script/i.test(message.text()) && /violat|refus/i.test(message.text())) inlineRefusals++;
  });
});
test.afterEach(async ({}, info) => {
  info.annotations.push({type: 'csp_inline_refusals', description: String(inlineRefusals)});
});
test('EDGE-01 real Caddy policy and API readiness', async ({ page }) => {
  const response = await page.goto('/');
  expect(response?.status()).toBe(200);
  const headers = response!.headers();
  expect(headers['content-security-policy']).toContain("script-src 'self'");
  expect(headers['strict-transport-security']).toContain('max-age=31536000');
  const code = await page.evaluate(async (url) => (await fetch(url)).status, api + '/ready');
  expect(code).toBe(200);
});
test('AUTH-01 real cross-origin session login ownership and logout', async ({ page }) => {
  await page.goto('/');
  const result = await page.evaluate(async ({ api, account }) => {
    const send = (path: string, method = 'GET', data?: object) => fetch(api + path, {
      method, credentials: 'include', headers: {'Content-Type': 'application/json'}, body: data ? JSON.stringify(data) : undefined,
    });
    const login = await send('/auth/login', 'POST', {email: account.email, password: account.password});
    const me = await send('/auth/me'); const body = await me.json();
    const logout = await send('/auth/logout', 'POST'); const after = await send('/auth/me');
    return {login: login.status, me: me.status, same: body.user_id === account.user_id, logout: logout.status, after: after.status};
  }, {api, account: credentials.alice});
  expect(result).toEqual({login: 200, me: 200, same: true, logout: 200, after: 401});
});
test('UI-01 hydrated sign-in, authenticated navigation, images, injection refusal and logout', async ({ page, context }, info) => {
  let activeStage: Ui01Stage | undefined;
  // Reaching the next stage means the preceding stage returned successfully.
  function enterStage(stage: Ui01Stage) {
    if (activeStage !== undefined) {
      info.annotations.push({type: UI01_LAST_COMPLETED_STAGE, description: activeStage});
    }
    info.annotations.push({type: UI01_ACTIVE_STAGE, description: stage});
    activeStage = stage;
  }

  enterStage('sign_in_document');
  const external: string[] = [];
  page.on('request', request => {
    if (!['https://app.staging.example.com', 'https://api.staging.example.com'].includes(new URL(request.url()).origin)) external.push('external_host');
  });
  const response = (await page.goto('/sign-in?next=%2Faccount', {waitUntil: 'domcontentloaded'}))!;
  enterStage('csp_header_validation');
  const policy = response.headers()['content-security-policy'];
  expect(policy).toMatch(/script-src 'self' 'nonce-/);
  expect(policy.split(';').find(d => d.trim().startsWith('script-src '))).not.toMatch(/unsafe-inline|unsafe-eval/);
  enterStage('sign_in_form_ready');
  await page.getByLabel('Email', {exact: true}).fill(credentials.alice.email);
  await page.getByLabel('Password', {exact: true}).fill(credentials.alice.password);
  enterStage('sign_in_submitted');
  await page.getByRole('button', {name: /^sign in$/i}).click();
  enterStage('account_navigation');
  await expect(page).toHaveURL(/\/account$/);
  await expect(page.getByRole('heading', {name: 'Your account'})).toBeVisible();
  enterStage('session_cookie_verified');
  const session = (await context.cookies(api)).find(c => c.name === 'ask4mo_session');
  expect(session).toMatchObject({secure: true, httpOnly: true, sameSite: 'Lax'});
  for (const [path, endpoint] of [['/history', '/history/interviews'], ['/opportunities', '/opportunities']]) {
    enterStage(path === '/history' ? 'history_navigation' : 'opportunities_navigation');
    const data = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v1' + endpoint && r.request().method() === 'GET');
    await page.goto(path, {waitUntil: 'domcontentloaded'});
    enterStage(path === '/history' ? 'history_api_response' : 'opportunities_api_response');
    expect((await data).status()).toBe(200);
    enterStage(path === '/history' ? 'history_heading_validation' : 'opportunities_heading_validation');
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('h1')).not.toHaveText(/sign in|not found|error/i);
    if (path === '/history') {
      enterStage('history_image_validation');
      const image = page.locator('img:visible');
      for (const img of await image.all()) {
        await expect.poll(() => img.evaluate(el => (el as HTMLImageElement).complete && (el as HTMLImageElement).naturalWidth > 0)).toBe(true);
      }
    }
  }
  enterStage('before_csp_injection');
  expect(inlineRefusals).toBe(0);
  enterStage('csp_injection_attempt');
  await page.evaluate(() => {
    const script = document.createElement('script');
    script.textContent = 'window.__task07Injection = true';
    document.head.appendChild(script);
  });
  enterStage('csp_refusal_observed');
  await expect.poll(() => inlineRefusals).toBe(1);
  enterStage('injected_script_nonexecution');
  expect(await page.evaluate(() => (window as unknown as {__task07Injection?: boolean}).__task07Injection)).toBeUndefined();
  enterStage('return_to_account');
  await page.goto('/account', {waitUntil: 'domcontentloaded'});
  await expect(page.getByRole('heading', {name: 'Your account'})).toBeVisible();
  enterStage('logout_requested');
  const logout = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v1/auth/logout' && r.request().method() === 'POST');
  await page.locator('#main').getByRole('button', {name: 'Sign out', exact: true}).click();
  enterStage('logout_response');
  expect((await logout).status()).toBe(200);
  enterStage('signed_out_navigation');
  await expect.poll(() => new URL(page.url()).pathname).toBe('/sign-in');
  enterStage('session_revocation_verified');
  expect(await page.evaluate(async url => (await fetch(url, {credentials: 'include'})).status, api + '/auth/me')).toBe(401);
  expect((await context.cookies(api)).some(c => c.name === 'ask4mo_session')).toBe(false);
  enterStage('no_external_requests');
  expect(external).toHaveLength(0);
  enterStage('complete');
});
