import { expect, test, type Page } from "@playwright/test";

// W12.4F Admin Speech page, mocked at the network layer. Server authorization, audit, revision handling and the effective runtime consumer are proven by
// tests/test_admin_completeness_w12_4f.py; these browser tests prove the governed UI flow and the role boundary. No provider is contacted.

const OWNER = ["platform.overview.read", "platform.flags.read", "platform.config.manage"];
const VIEWER = ["platform.overview.read", "platform.flags.read"];
const CAPS = { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true };

const cfg = (o: Record<string, unknown> = {}) => ({ stt_provider: "openai_whisper", tts_provider: "kyutai_pocket_tts", stt_enabled: false, tts_enabled: false, languages: ["en", "de", "fr", "es", "it", "pt", "nl"],
  browser_stt_allowed: true, browser_tts_allowed: true, stt_timeout_seconds: 30, tts_timeout_seconds: 20, revision: 0, persisted: false, ...o });
const ready = (provider: string) => ({ provider, configured: false, dependency_available: false, model_available: false, ready_for_offline_execution: false, validated_with_fixture: true,
  validated_with_genuine_model: "NOT_VERIFIED", live_authorized: false, operational: false, deployment: "none", blockers: ["disabled by configuration"], note: "" });
const lang = { product_authorized: true, stt_provider_supports: true, tts_provider_supports: true, tts_provider_unverified: false, admin_selected: true, effective_stt: true, effective_tts: true };

async function mock(page: Page, perms: string[], state: { config: ReturnType<typeof cfg>; sent: string[] }) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.endsWith("/auth/me")) {
      return json({ user_id: 1, email: "u@example.com", display_name: null, platform_role: "platform_admin", tier: "basic", status: "active", email_verified: true, providers: ["password"],
        auth_method: "session", capabilities: [], admin_permissions: perms, response_detail: "brief", interface_locale: "en", conversation_language: "en", onboarding_completed: true, onboarding_step: 0 });
    }
    if (path.endsWith("/admin/speech") && method === "PUT") {
      state.sent.push(route.request().postData() ?? "");
      const body = JSON.parse(route.request().postData() ?? "{}");
      if (body.expected_revision !== state.config.revision) return json({ error: { code: "conflict", message: "The speech settings changed since you loaded them." } }, 409);
      state.config = cfg({ ...state.config, ...body, revision: state.config.revision + 1, persisted: true });
      return json(state.config);
    }
    if (path.endsWith("/admin/speech")) {
      return json({ environment: "development", config: state.config, stt: ready("openai_whisper"), tts: ready("kyutai_pocket_tts"), language_matrix: { en: lang, ru: { ...lang, product_authorized: false, effective_stt: false, effective_tts: false } },
        provider_facts: {}, authorization: { server_speech_providers: false, hosted_whisper_api_transport: false, model_downloads: false, voice_cloning: false }, note: "Server-side speech is governed here but is NOT active." });
    }
    if (path.endsWith("/admin/readiness")) return json({ capabilities: [], summary: {}, vocabulary: { statuses: [], qualifiers: [] }, boundary: "" });
    return json({});
  });
}

test("an owner changes speech policy with a reason and server speech stays inactive", async ({ page }) => {
  const state = { config: cfg(), sent: [] as string[] };
  await mock(page, OWNER, state);
  await page.goto("/admin/speech");
  await expect(page.getByText("Server speech: not active")).toBeVisible();
  await expect(page.getByText("Not operational")).toHaveCount(2);
  await page.getByLabel("Allow browser speech output (fallback)").uncheck();
  await page.getByRole("button", { name: "Save changes" }).click();
  await page.getByLabel(/Reason/).fill("disable browser output while reviewing");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText(/No provider was started or contacted/)).toBeVisible();
  expect(state.sent).toHaveLength(1);
  expect(JSON.parse(state.sent[0])).toMatchObject({ browser_tts_allowed: false, expected_revision: 0, reason: "disable browser output while reviewing" });
  await expect(page.getByText(/Revision 1/)).toBeVisible();
});

test("a view-only role cannot change speech policy and no free-form field exists", async ({ page }) => {
  const state = { config: cfg(), sent: [] as string[] };
  await mock(page, VIEWER, state);
  await page.goto("/admin/speech");
  await expect(page.getByText("Server speech: not active")).toBeVisible();
  await expect(page.getByRole("button", { name: "Save changes" })).toHaveCount(0);
  await expect(page.getByLabel("Server speech to text selected")).toBeDisabled();
  await expect(page.getByRole("textbox")).toHaveCount(0);
});
