import { expect, test, type Page } from "@playwright/test";

// P4 documents surface, mocked at the network layer (no backend, no real files).
// Verifies the candidate flow: authenticated Documents page → review evidence with
// provenance → draft a story → story bank shows verification state.

const ACCOUNT = {
  user_id: 1, email: "u@example.com", display_name: null, platform_role: "user",
  tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: [], response_detail: "brief",
  interface_locale: "en", conversation_language: "en",
};

const DOC = {
  id: 1, category: "cv", title: "cv.txt", status: "review_required", current_version: 1, created_at: null,
  versions: [{ version: 1, original_filename: "cv.txt", mime_type: "text/plain", size_bytes: 10, page_count: null, extraction_origin: "native", status: "ready", failure_reason: null, language_hint: null }],
  claims: [
    { id: 11, document_id: 1, version_id: 1, claim_type: "skill", text: "Python", edited_text: null, display_text: "Python", source_page: null, source_section: "block 2", review_state: "pending" },
    { id: 12, document_id: 1, version_id: 1, claim_type: "achievement", text: "Cut latency 40%", edited_text: null, display_text: "Cut latency 40%", source_page: null, source_section: "block 3", review_state: "pending" },
  ],
};

async function mock(page: Page) {
  const state = { drafted: false };
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
    if (url.includes("/auth/me")) return json(ACCOUNT);
    if (url.match(/\/documents$/) && method === "GET")
      return json({ documents: [{ id: 1, category: "cv", title: "cv.txt", status: "review_required", current_version: 1, updated_at: null }] });
    if (url.match(/\/documents\/1$/) && method === "GET") return json(DOC);
    if (url.includes("/claims/11/review")) return json({ ...DOC.claims[0], review_state: "accepted" });
    if (url.includes("/stories/draft")) {
      state.drafted = true;
      return json({ id: 5, title: "cv.txt", status: "source_backed", evidence_state: "verified", competencies: [], evidence_claim_ids: [11] }, 201);
    }
    if (url.match(/\/stories$/) && method === "GET")
      return json({ stories: state.drafted ? [{ id: 5, title: "cv.txt", status: "source_backed", evidence_state: "verified", competencies: [], evidence_claim_ids: [11] }] : [] });
    return json({});
  });
}

test("Documents: review evidence with provenance and draft a story", async ({ page }) => {
  await mock(page);
  await page.goto("/documents");
  await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();
  await page.getByText("cv.txt").first().click();
  await expect(page.getByText("Review extracted evidence")).toBeVisible();
  // Provenance is shown for a claim.
  await expect(page.getByText(/block 2/)).toBeVisible();
  // Accept the first claim.
  await page.getByRole("button", { name: "Accept" }).first().click();
  // Select the skill and draft a story.
  await page.getByLabel("Python").check();
  await page.getByRole("button", { name: /Draft a story/ }).click();
  // The story bank shows the verified, source-backed story.
  await expect(page.getByText("Source-backed")).toBeVisible();
  await expect(page.getByText("Evidence verified")).toBeVisible();
});

test("Documents requires sign-in (protected route)", async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    if (url.includes("/auth/me"))
      return route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ error: { code: "unauthorized", message: "x" } }) });
    return route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });
  await page.goto("/documents");
  await expect(page).toHaveURL(/\/sign-in/);
});
