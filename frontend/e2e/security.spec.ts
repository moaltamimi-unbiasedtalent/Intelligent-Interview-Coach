import { expect, test, type Page } from "@playwright/test";

// P10B-W10.13 Admin Security journeys, mocked at the network layer with deterministic fixtures (no sleeps). The real SQL semantics (append-only audit, two-person role
// change, step-up expiry, stale approval) are proven by tests/test_security_w10_13.py and the manual QA; this proves the browser flows and the permission split.

const CAPS = { career_intelligence: true, interview_practice: true, knowledge_base: true, evaluation: true, live_interview_enabled: false, agentic_rag: true,
  agent_memory: true, human_in_the_loop: true, agent_coach_enabled: true };
const json = (route: any, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "x-request-id": "r" }, body: JSON.stringify(body) });
const err = (route: any, status: number, code: string, message: string) => json(route, { error: { code, message, request_id: "r" } }, status);
const account = (perms: string[], id = 1) => ({ user_id: id, email: "ops@example.com", display_name: null, platform_role: "x", tier: "basic", status: "active", email_verified: true,
  providers: ["password"], auth_method: "session", capabilities: [], admin_permissions: perms, response_detail: "brief", interface_locale: "en", conversation_language: "en",
  coaching_style: "balanced", career_geography: "", target_role: "", onboarding_completed: true, onboarding_step: 0 });

const SEC = ["platform.overview.read", "platform.security.read", "platform.security.manage", "platform.incidents.manage", "platform.audit.read", "platform.audit.export"];
const ADM = ["platform.overview.read", "platform.users.read", "platform.users.role.assign", "platform.security.read"];

const EVENTS = { items: [
  { id: 3, event_type: "admin.access.denied", category: "authorization", severity: "medium", actor_user_id: 12, target_type: "permission", target_id: "platform.billing.read", result: "denied", request_id: "req-deny", created_at: "2026-10-06T10:02:00" },
  { id: 2, event_type: "account.login", category: "authentication", severity: "low", actor_user_id: 12, target_type: null, target_id: null, result: "failure", request_id: "req-login", created_at: "2026-10-06T10:01:00" }],
  total: 2, page: 1, page_size: 25, anomalies: [], advanced_anomaly_detection: false };
const AUDIT = { items: [{ id: 9, event_type: "admin.role_change.approved", result: "success", actor_user_id: 5, target_type: "role_change_request", target_id: "rc1", request_id: "req-aud", context: null, created_at: "2026-10-06T10:03:00" }], total: 1, page: 1, page_size: 50 };

async function mockSecurity(page: Page, perms: string[]) {
  const state = { alert: { public_id: "al1", category: "job_failed", severity: "medium", state: "active", source_type: "job", source_id: "j1", title: "A background job failed terminally",
    occurrence_count: 3, first_seen_at: "x", last_seen_at: "y", acknowledged_at: null as string | null, resolved_at: null as string | null, revision: 0 },
    incident: null as null | Record<string, unknown>, history: [] as Record<string, unknown>[] };
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    if (path.endsWith("/capabilities")) return json(route, CAPS);
    if (path.endsWith("/auth/me")) return json(route, account(perms));
    if (path.endsWith("/admin/security/events")) return json(route, EVENTS);
    if (path.endsWith("/admin/audit") && method === "GET") return json(route, AUDIT);
    if (path.endsWith("/admin/security/summary")) return json(route, { alerts: { active_critical: 0, active_high: 0, active: 1, acknowledged: 0 }, open_incidents: 0, pending_role_changes: 0, categories: [], anomaly_rules: [], advanced_anomaly_detection: false });
    if (path.endsWith("/admin/security/alerts") && method === "GET") return json(route, { items: [state.alert], total: 1, page: 1, page_size: 25, categories: ["job_failed"], not_implemented: ["provider_outage"], delivery: "in_app_only" });
    if (path.endsWith("/acknowledge")) { state.alert = { ...state.alert, state: "acknowledged", revision: 1 }; return json(route, state.alert); }
    if (path.endsWith("/resolve")) { state.alert = { ...state.alert, state: "resolved", revision: 2 }; return json(route, state.alert); }
    if (path.endsWith("/admin/security/incidents") && method === "GET") return json(route, { items: state.incident ? [state.incident] : [], total: state.incident ? 1 : 0, page: 1, page_size: 25, severities: ["low", "medium", "high", "critical"], statuses: [], services: ["agent", "platform"] });
    if (path.endsWith("/admin/security/incidents") && method === "POST") {
      state.incident = { public_id: "in1", title: "Provider latency", severity: "medium", status: "open", affected_service: "agent", started_at: "x", resolved_at: null, owner_admin_user_id: null, affected_user_estimate: null, root_cause: null, remediation: null, created_at: "x", updated_at: "x", revision: 0 };
      state.history = [{ id: 1, action: "created", prior_status: null, new_status: "open", actor_user_id: 1, request_id: "q1", meta: null, created_at: "x" }];
      return json(route, state.incident);
    }
    if (path.endsWith("/admin/security/incidents/in1") && method === "GET") return json(route, { ...state.incident, allowed_transitions: state.incident?.status === "open" ? ["investigating"] : [], tickets: [{ public_id: "tk1", status: "new", category: "technical", linked_at: "x" }], history: state.history });
    if (path.endsWith("/admin/security/incidents/in1/status")) {
      state.incident = { ...state.incident!, status: "investigating", revision: 1 };
      state.history = [{ id: 2, action: "status_changed", prior_status: "open", new_status: "investigating", actor_user_id: 1, request_id: "q2", meta: null, created_at: "x" }, ...state.history];
      return json(route, state.incident);
    }
    return json(route, {});
  });
  return state;
}

test("W10.13: Security Admin journey: events, audit, incident lifecycle with history, alert acknowledge then resolve, and no candidate content", async ({ page }) => {
  await mockSecurity(page, SEC);
  await page.goto("/admin/security");
  await expect(page.getByRole("heading", { name: "Security", exact: true, level: 1 })).toBeVisible();
  await expect(page.getByText("req-login")).toBeVisible();
  await expect(page.getByText("req-deny")).toBeVisible();
  await page.getByRole("tab", { name: "Audit" }).click();
  await expect(page.getByText("req-aud")).toBeVisible();
  await expect(page.getByRole("button", { name: "Export audit events" })).toBeVisible();
  await page.getByRole("tab", { name: "Incidents" }).click();
  await page.getByRole("button", { name: "Create incident" }).click();
  await page.getByLabel("Title").fill("Provider latency");
  await page.getByRole("alertdialog").getByRole("button", { name: "Create" }).click();
  await page.getByRole("button", { name: "Open" }).click();
  await expect(page.getByText("tk1")).toBeVisible();                                                  // a ticket IDENTIFIER, never its body
  await page.getByRole("button", { name: "Move to investigating" }).click();
  await expect(page.getByRole("cell", { name: "investigating" }).first()).toBeVisible();              // the append-only history shows the transition
  await expect(page.getByRole("button", { name: /delete/i })).toHaveCount(0);
  await page.getByRole("tab", { name: "Alerts" }).click();
  await expect(page.getByText("A background job failed terminally")).toBeVisible();
  await page.getByRole("button", { name: "Acknowledge" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Acknowledge" }).click();
  await expect(page.getByText("Alert acknowledged.")).toBeVisible();
  await page.getByRole("button", { name: "Resolve" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Resolve" }).click();
  await expect(page.getByText("Alert resolved.")).toBeVisible();
  await expect(page.getByText(/example\.com|@/i)).toHaveCount(0);
});

test("W10.13: a security.read-only Admin can read but sees no mutation controls", async ({ page }) => {
  await mockSecurity(page, ["platform.overview.read", "platform.security.read"]);
  await page.goto("/admin/security");
  await page.getByRole("tab", { name: "Alerts" }).click();
  await expect(page.getByText("A background job failed terminally")).toBeVisible();
  await expect(page.getByRole("button", { name: "Acknowledge" })).toHaveCount(0);
  await page.getByRole("tab", { name: "Incidents" }).click();
  await expect(page.getByRole("button", { name: "Create incident" })).toHaveCount(0);
  await expect(page.getByRole("tab", { name: "Audit" })).toHaveCount(0);
});

test("W10.13: role change is a REQUEST that needs a password step-up, then a different Admin approves it (also with step-up)", async ({ page, browser }) => {
  // requester
  let elevated = false;
  const requests: Record<string, unknown>[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    if (path.endsWith("/capabilities")) return json(route, CAPS);
    if (path.endsWith("/auth/me")) return json(route, account(ADM, 2));
    if (path.endsWith("/admin/users/9") && method === "GET") return json(route, {
      account: { user_id: 9, email: "target@example.com", display_name: null, status: "active", platform_role: "user", tier: "basic", onboarding_completed: true, interface_locale: "en", email_verified: false, created_at: null, updated_at: null, workspace_count: 0, active_session_count: 0 },
      access: { platform_role: "user", capabilities: [], assignable_roles: ["user", "billing_admin"], is_self: false }, sessions: { active_count: 0, recent: [] }, workspaces: [], audit: [], plan: { current: null, versions: [], plans: [] } });
    if (path.endsWith("/admin/step-up") && method === "POST") { elevated = true; return json(route, { elevated: true, elevated_until: "x", window_seconds: 300, method: "password_reauthentication" }); }
    if (path.endsWith("/admin/role-changes") && method === "POST") {
      if (!elevated) return err(route, 403, "step_up_required", "Confirm your password to continue.");
      requests.push(route.request().postDataJSON());
      return json(route, { public_id: "rc1", status: "pending" });
    }
    return json(route, {});
  });
  await page.goto("/admin/users/9");
  await page.getByLabel("Role preset").selectOption("billing_admin");
  await page.getByRole("button", { name: "Request role change" }).click();
  const dlg = page.getByRole("alertdialog");
  await dlg.getByLabel(/Reason/).fill("covers billing");
  await dlg.getByRole("button", { name: "Request role change" }).click();
  const step = page.getByTestId("step-up-dialog");
  await expect(step.getByText("Confirm your password to continue")).toBeVisible();                    // the step-up prompt appears
  await expect(step.getByLabel("Current password")).toHaveAttribute("autocomplete", "current-password");
  await step.getByLabel("Current password").fill("a-test-password");
  await step.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText(/a different Admin must approve it/)).toBeVisible();                    // pending: nothing changed yet
  expect(requests).toEqual([{ target_user_id: 9, role: "billing_admin", reason: "covers billing" }]);

  // second Admin (a different browser context / session)
  const ctx = await browser.newContext();
  const page2 = await ctx.newPage();
  let elevated2 = false;
  let applied = false;
  await page2.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    if (path.endsWith("/capabilities")) return json(route, CAPS);
    if (path.endsWith("/auth/me")) return json(route, account(ADM, 3));
    if (path.endsWith("/admin/security/events")) return json(route, EVENTS);
    if (path.endsWith("/admin/role-changes") && method === "GET") return json(route, { items: [{ public_id: "rc1", target_user_id: 9, before_role: "user", requested_role: "billing_admin", requester_user_id: 2, approver_user_id: applied ? 3 : null, status: applied ? "applied" : "pending", reason: "covers billing", requested_at: "x", decided_at: null, applied_at: null, revision: 0 }], total: 1, page: 1, page_size: 25, assignable_roles: [], viewer_user_id: 3 });
    if (path.endsWith("/admin/step-up") && method === "POST") { elevated2 = true; return json(route, { elevated: true }); }
    if (path.endsWith("/rc1/approve")) { if (!elevated2) return err(route, 403, "step_up_required", "Confirm your password to continue."); applied = true; return json(route, { outcome: "applied", status: "applied" }); }
    return json(route, {});
  });
  await page2.goto("/admin/security");
  await page2.getByRole("tab", { name: "Role approvals" }).click();
  await page2.getByRole("button", { name: "Approve" }).click();
  await page2.getByTestId("step-up-dialog").getByLabel("Current password").fill("another-password");
  await page2.getByTestId("step-up-dialog").getByRole("button", { name: "Confirm" }).click();
  await expect(page2.getByText("Role change approved and applied.")).toBeVisible();
  await ctx.close();
});

test("W10.13: the requester sees that a different Admin must approve and gets no Approve button", async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/capabilities")) return json(route, CAPS);
    if (path.endsWith("/auth/me")) return json(route, account(ADM, 2));
    if (path.endsWith("/admin/security/events")) return json(route, EVENTS);
    if (path.endsWith("/admin/role-changes")) return json(route, { items: [{ public_id: "rc1", target_user_id: 9, before_role: "user", requested_role: "billing_admin", requester_user_id: 2, approver_user_id: null, status: "pending", reason: "covers billing", requested_at: "x", decided_at: null, applied_at: null, revision: 0 }], total: 1, page: 1, page_size: 25, assignable_roles: [], viewer_user_id: 2 });
    return json(route, {});
  });
  await page.goto("/admin/security");
  await page.getByRole("tab", { name: "Role approvals" }).click();
  await expect(page.getByText(/You requested this; a different Admin must approve/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);
});
