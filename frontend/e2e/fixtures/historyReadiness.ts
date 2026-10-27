import { writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { expect, type Locator, type Page, type Request, type TestInfo } from "@playwright/test";

const SOURCE_SHA = execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim();
const SOURCE_DIRTY = Boolean(execFileSync("git", ["status", "--porcelain"], { encoding: "utf8" }).trim());
const ASSET = "/images/ask4mo/ask4mo-empty-history-ink.png";
export const SECURITY_OBSERVATION_MS = 500; // Preserve networkidle's minimum observation, after semantic readiness.

/** Synthetic mocked-network tests only. No headers, cookies, bodies, query strings or console text. */
export function observeHistory(page: Page) {
  const start = Date.now();
  const events: Array<Record<string, unknown>> = [];
  const pending = new Map<Request, string>();
  let sequence = 0;
  const requests = new Map<Request, { id: number; rsc: boolean; prefetch: boolean; status?: number; contentType?: string }>();
  const consoleErrors: string[] = [], pageErrors: string[] = [], transportFailures: string[] = [];
  const imageResponses: Array<{ status: number; elapsedMs: number; cache: string | null; source: string | null }> = [];
  const safeUrl = (raw: string) => {
    const url = new URL(raw);
    return `${url.origin}${url.pathname}`;
  };
  const record = (kind: string, detail: Record<string, unknown>) => events.push({ kind, elapsedMs: Date.now() - start, ...detail });
  page.on("request", request => {
    const url = safeUrl(request.url()); pending.set(request, url);
    const headers = request.headers();
    const metadata = { id: ++sequence, rsc: headers.rsc === "1", prefetch: headers["next-router-prefetch"] === "1" || Boolean(headers["next-router-segment-prefetch"]) };
    requests.set(request, metadata);
    record("request", { ...metadata, url, resource: request.resourceType() });
  });
  page.on("response", response => {
    const url = new URL(response.url());
    const metadata = requests.get(response.request());
    if (metadata) { metadata.status = response.status(); metadata.contentType = response.headers()["content-type"]?.split(";")[0]; }
    record("response", { ...metadata, url: safeUrl(response.url()), status: response.status() });
    if (url.pathname === "/_next/image" && [ASSET, "/images/ask4mo/missing-history-qualification.png"].includes(url.searchParams.get("url") ?? "")) {
      imageResponses.push({ status: response.status(), elapsedMs: Date.now() - start, cache: response.headers()["x-nextjs-cache"] ?? null, source: url.searchParams.get("url") });
    }
  });
  page.on("requestfinished", request => { record("finished", { id: requests.get(request)?.id, url: safeUrl(request.url()) }); pending.delete(request); });
  page.on("requestfailed", request => {
    const headers = request.headers();
    const prefetch = headers["next-router-prefetch"] === "1" || Boolean(headers["next-router-segment-prefetch"]);
    const expectedAbort = request.failure()?.errorText === "net::ERR_ABORTED" && prefetch;
    const category = expectedAbort ? "next_prefetch_cancelled_by_navigation" : "unexpected_request_failure";
    const rawCode = request.failure()?.errorText ?? "";
    const code = /^net::ERR_[A-Z_]+$/.test(rawCode) ? rawCode : "other_transport_code";
    record("failed", { ...requests.get(request), url: safeUrl(request.url()), resource: request.resourceType(), category, code });
    if (!expectedAbort) transportFailures.push(safeUrl(request.url()));
    pending.delete(request);
  });
  page.on("console", message => {
    if (message.type() === "error") {
      const match = message.text().match(/^Failed to load resource: the server responded with a status of (400|403)/);
      const category = match ? `http_${match[1]}` : /content security policy|violates.*directive/i.test(message.text()) ? "csp_refusal" : "console_error";
      consoleErrors.push(category); record("console_error", { category });
    }
  });
  page.on("pageerror", error => { pageErrors.push(error.name); record("page_error", { category: error.name }); });
  return {
    imageResponses, consoleErrors, pageErrors, transportFailures,
    async ready(path: string) {
      record("ui_ready", { path, documentState: await page.evaluate(() => document.readyState), hydration: path === "/pricing" ? "static_navigation" : "controlled_menu_interaction" });
    },
    snapshot: () => ({ sourceSha: SOURCE_SHA, workingTreeDirty: SOURCE_DIRTY, nodeVersion: process.version, browserVersion: page.context().browser()?.version(), scope: "synthetic mocked API; real production Next.js and image requests", events, outstanding: [...pending.values()], imageResponses, consoleErrors, pageErrors, transportFailures }),
    async attach(info: TestInfo, name: string) {
      const path = info.outputPath(name + ".json");
      writeFileSync(path, JSON.stringify(this.snapshot(), null, 2));
      await info.attach(name, { path, contentType: "application/json" });
    },
  };
}

export type HistoryObservation = ReturnType<typeof observeHistory>;

export async function historyReady(page: Page) {
  await expect(page).toHaveURL(/\/history$/);
  await expect(page.getByRole("heading", { level: 1, name: "History", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "No completed interviews yet", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Start Practice", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Learn about History", exact: true })).toBeVisible();
}

/** A pending/failed optimizer must fail explicitly, even though the page is usable. */
export async function qualifyHistoryImage(image: Locator, observation: HistoryObservation) {
  await expect(image).toBeVisible();
  await image.scrollIntoViewIfNeeded(); // Exercise the actual lazy image; never intercept it.
  try {
    await expect.poll(() => image.evaluate(node => (node as HTMLImageElement).complete), { message: "history_image_optimizer_pending" }).toBe(true);
  } catch {
    throw new Error("history_image_optimizer_pending: " + JSON.stringify(observation.snapshot().outstanding));
  }
  const state = await image.evaluate(node => {
    const img = node as HTMLImageElement;
    const url = new URL(img.currentSrc);
    return { complete: img.complete, naturalWidth: img.naturalWidth, naturalHeight: img.naturalHeight,
      optimizer: url.pathname === "/_next/image", source: url.searchParams.get("url"), origin: url.origin };
  });
  if (state.naturalWidth === 0) {
    const status = observation.imageResponses.at(-1)?.status;
    throw new Error(status && status >= 400 ? `history_image_http_${status}` : "history_image_decode_failed");
  }
  await image.evaluate(node => (node as HTMLImageElement).decode());
  expect(state.optimizer).toBe(true);
  expect(state.source).toBe(ASSET);
  expect(state.naturalHeight).toBeGreaterThan(0);
  return state;
}

export async function candidateReady(page: Page, path: string) {
  await expect(page).toHaveURL(new RegExp(path + "$"));
  const main = page.locator("#main");
  await expect(main).toBeVisible();
  await expect(main.getByRole("heading", { level: 1 }).first()).toBeVisible();
  await expect(main.getByRole("status").filter({ has: page.locator(".animate-pulse") })).toHaveCount(0);
  // Opening the real controlled menu verifies hydration, not just SSR markup.
  if (path !== "/pricing") {
    await page.getByRole("button", { name: /more/i }).first().click();
    await expect(page.getByRole("menuitem").first()).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("menuitem")).toHaveCount(0);
  } else {
    await expect(page.getByRole("navigation").first()).toBeVisible();
  }
}
