import { expect, type Page } from "@playwright/test";

import { CATALOGS, translate } from "../../lib/i18n/catalog";
import type { AppLocale } from "../../lib/i18n/locales";

/**
 * 06B shared helpers for the per-language Candidate journeys. ONE journey definition is parameterised by locale
 * (language-journeys-06b.spec.ts); nothing here is per-language. Mocked network only: no backend, no provider call.
 * All non-English strings referenced here are ENGINEERING translations, not native-reviewed.
 */

export const T = (l: string, k: string, v?: Record<string, string | number>) => translate(l as AppLocale, k, v);

export function account(ui: string, conv = "en", over: Record<string, unknown> = {}) {
  return {
    user_id: 1, email: "kandidat@example.com", display_name: null, platform_role: "user", tier: "basic",
    status: "active", email_verified: true, providers: ["password"], auth_method: "session", capabilities: [],
    response_detail: "brief", interface_locale: ui, conversation_language: conv, coaching_style: "balanced",
    career_geography: "de", target_role: "", onboarding_completed: true, onboarding_step: 0, ...over,
  };
}

export const CAPS = {
  career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false,
  agentic_rag: true, agent_memory: true, human_in_the_loop: true, agent_coach_enabled: false, realtime_voice_enabled: false,
  company_research_enabled: true,
};

export async function quietTutorial(page: Page) {
  await page.addInitScript(() => {
    try { window.localStorage.setItem("ask4mo.tutorial:1", JSON.stringify({ version: 2, dismissedAt: Date.now() })); } catch { /* ignore */ }
  });
}

export const jsonRoute = (route: import("@playwright/test").Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "req_06b" }, body: JSON.stringify(body) });

export type SweepOpts = {
  ui: string; conv?: string; geography?: string; onboarding?: boolean; failAll?: boolean; patches?: Record<string, unknown>[];
  chat?: Record<string, unknown>; chatBodies?: unknown[]; onboardingCalls?: Record<string, unknown>[];
};

/** Generic read-only candidate backend used by the surface sweep. */
export async function installSweepMock(page: Page, o: SweepOpts) {
  await quietTutorial(page);
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname.replace(/^.*\/api\/v1/, "");
    const method = req.method();
    const json = (b: unknown, s = 200) => jsonRoute(route, b, s);
    if (path === "/auth/me") return json(account(o.ui, o.conv ?? "en", { ...(o.onboarding ? { onboarding_completed: false } : {}), ...(o.geography !== undefined ? { career_geography: o.geography } : o.onboarding ? { career_geography: "" } : {}) }));
    if (path === "/auth/preferences" && method === "PATCH") { o.patches?.push(req.postDataJSON()); return json(account(o.ui, o.conv ?? "en")); }
    if (path === "/auth/onboarding" && method === "POST") { o.onboardingCalls?.push(req.postDataJSON()); return json(account(o.ui, o.conv ?? "en", { onboarding_completed: !!(req.postDataJSON() as { complete?: boolean })?.complete })); }
    if (path === "/career/chat" && method === "POST") { o.chatBodies?.push(req.postDataJSON()); return json(o.chat ?? {}); }
    if (path === "/capabilities") return json({ ...CAPS, active_candidate_locales: ["en", "de", "fr", "es", "it", "pt", "nl"], default_locale: "en" });
    if (o.failAll) return json({ error: { code: "server_error", message: "x", request_id: "req_06b" } }, 500);
    if (path === "/opportunities") return json({ opportunities: [{ id: 3, title: "Pflegefachkraft", target_role: "Nurse", company: "Acme", status: "active", created_at: "2026-10-01T10:00:00Z" }] });
    if (path === "/documents") return json({ documents: [{ id: 1, category: "cv", title: "cv.txt", status: "ready", current_version: 1, updated_at: "2026-10-01T10:00:00Z" }] });
    if (path === "/stories") return json({ stories: [] });
    if (path === "/stories/tags") return json({ tags: [] });
    if (path === "/workspaces") return json({ workspaces: [], invited: [] });
    if (path === "/history/interviews" || path === "/history") return json({ interviews: [{ id: 30, target_role: "Nurse", created_at: "2026-09-01T10:00:00Z", questions: 3 }] });
    if (path === "/memory" || path.startsWith("/memory")) return json({ memories: [], items: [] });
    if (path === "/progress") return json({ interviews_completed: 1, answers_evaluated: 3, average_practice_score: 3.5, most_common_improvement_area: null, average_answer_seconds: 42, recent_interviews: [] });
    if (path === "/interviews/options") return json({ career_levels: ["junior", "mid", "senior"], interview_types: ["behavioural"], deep_dive_modes: [] });
    if (path === "/shares/mine" || path === "/shares/with-me") return json({ shares: [] });
    if (path === "/privacy/requests") return json({ items: [], total: 0, page: 1, page_size: 20 });
    if (path.startsWith("/knowledge/")) return json({ sources: [], documents: 0, chunks: 0, document_types: 0 });
    return json({});
  });
}

// ----- generic assertions -----

/**
 * English strings that a non-English interface must not show: every English catalogue value (longest literal segment) whose
 * translation in this locale differs from English. Matching is case-sensitive on the visible text of the page body.
 */
export function englishLeakPhrases(locale: string): string[] {
  const en = CATALOGS.en as unknown as Record<string, Record<string, string>>;
  const loc = (CATALOGS as unknown as Record<string, Record<string, Record<string, string>>>)[locale];
  const out = new Set<string>();
  for (const ns of Object.keys(en)) {
    for (const [k, v] of Object.entries(en[ns])) {
      if (typeof v !== "string" || loc?.[ns]?.[k] === v) continue;
      const seg = v.split(/\{\w+\}/).sort((a, b) => b.length - a.length)[0].trim();
      if (seg.length >= 14) out.add(seg);
    }
  }
  return [...out];
}

export async function expectNoEnglishLeak(page: Page, locale: string, where: string, allow: string[] = []) {
  if (locale === "en") return;
  const text = await page.locator("body").innerText();
  const hits = englishLeakPhrases(locale).filter((p) => text.includes(p) && !allow.some((a) => p.includes(a)));
  expect(hits, `${locale} ${where}: English interface text leaked`).toEqual([]);
}

export async function expectNoOverflow(page: Page, locale: string, where: string) {
  for (const width of [768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(over, `${locale} ${where} @${width}px horizontal overflow`).toBeLessThanOrEqual(1);
  }
}
