import { expect, test, type Page } from "@playwright/test";

// P6.5 Workspaces candidate UX, mocked at the network layer (no backend, no paid calls).
// Backend security (membership/sharing/revocation/isolation) is proven authoritatively by
// the Python suites (test_workspaces_p6_5 / test_sharing_p6_5 / eval_workspace_security);
// these browser tests prove the UI states render and interactions call the right endpoints.

const ACCOUNT = {
  user_id: 1, email: "u@example.com", display_name: null, platform_role: "user",
  tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: [], response_detail: "brief",
  interface_locale: "en", conversation_language: "en",
};

const CAPS = {
  career_intelligence: true, interview_practice: true, knowledge_base: true,
  evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true,
};

async function mock(page: Page) {
  const state = {
    workspaces: [] as Record<string, unknown>[],
    sharedByMe: [{ id: 7, owner_user_id: 1, workspace_id: 1, resource_type: "interview_report", resource_id: "3", permission: "view", status: "active", created_at: null, revoked_at: null }],
  };
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });

    if (path.endsWith("/capabilities")) return json(CAPS);
    if (path.endsWith("/auth/me")) return json(ACCOUNT);
    if (path.endsWith("/workspaces") && method === "GET")
      return json({ workspaces: state.workspaces, invited: [] });
    if (path.endsWith("/workspaces") && method === "POST") {
      state.workspaces = [{ id: 1, name: "Team Alpha", status: "active", owner_user_id: 1, member_count: 1, created_at: null, my_role: "workspace_owner" }];
      return json(state.workspaces[0]);
    }
    if (path.endsWith("/shares/mine")) return json({ shares: state.sharedByMe });
    if (path.endsWith("/shares/with-me")) return json({ shares: [] });
    if (path.match(/\/shares\/\d+$/) && method === "DELETE") {
      state.sharedByMe = [];
      return json({ status: "revoked" });
    }
    return json({});
  });
}

test("workspaces page renders, private-by-default messaging, create + revoke flows", async ({ page }) => {
  await mock(page);
  await page.goto("/workspaces");

  // Private-by-default messaging is visible.
  await expect(page.getByText(/shares nothing automatically/i)).toBeVisible();

  // Empty state, then create a workspace.
  await expect(page.getByText(/You are not in any workspace yet/i)).toBeVisible();
  await page.getByPlaceholder(/Workspace name/i).fill("Team Alpha");
  await page.getByRole("button", { name: /Create workspace/i }).click();

  // The new workspace renders with role + member count.
  await expect(page.getByText("Team Alpha")).toBeVisible();
  await expect(page.getByText(/Owner/i).first()).toBeVisible();

  // Shared-by-me renders, and revoke removes it from the UX.
  await expect(page.getByText(/interview_report #3/i)).toBeVisible();
  await page.getByRole("button", { name: /Revoke/i }).click();
  await expect(page.getByText(/interview_report #3/i)).toHaveCount(0);
});

test("workspaces does not expose candidate-private content", async ({ page }) => {
  await mock(page);
  await page.goto("/workspaces");
  await expect(page.getByText(/Your workspaces/i)).toBeVisible();
  // The workspace surface never renders raw private artefacts (CV text, answers, memory).
  await expect(page.getByText(/curriculum vitae|raw answer|memory summary/i)).toHaveCount(0);
});
