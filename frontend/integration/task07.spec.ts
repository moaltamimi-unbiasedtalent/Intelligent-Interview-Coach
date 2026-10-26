import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
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
test('UI-01 sign-in form hydrates against actual connected stack', async ({ page }) => {
  await page.goto('/sign-in?next=%2Faccount');
  await page.getByLabel('Email').fill(credentials.alice.email);
  await page.getByLabel('Password').fill(credentials.alice.password);
  await page.getByRole('button', {name: /sign in/i}).click();
  await expect(page).toHaveURL(/\/account/);
  await expect(page.getByRole('heading', {name: 'Your account'})).toBeVisible();
});
