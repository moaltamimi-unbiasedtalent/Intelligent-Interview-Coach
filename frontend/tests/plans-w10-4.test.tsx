import { readFileSync, readdirSync } from "node:fs";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";
import { BRAND_SLOGAN } from "@/lib/brand";
import en104 from "@/lib/i18n/messages/w104/en";

// P10B-W10.4 plans UI. Server-resolved permissions and entitlements only; async content awaited with findBy*/waitFor.

let mockPerms: string[] = [];
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/admin/plans" }));
vi.mock("next/link", () => ({ default: ({ href, children, onClick, ...r }: any) => <a href={href} onClick={onClick} {...r}>{children}</a> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuthOptional: () => ({ account: { platform_role: "x", admin_permissions: mockPerms }, status: "authenticated" }),
}));

const plans = vi.fn();
const plan = vi.fn();
const assignable = vi.fn();
const createDraft = vi.fn();
const updateDraft = vi.fn();
const activate = vi.fn();
const retire = vi.fn();
const setUserPlan = vi.fn();
const setWorkspacePlan = vi.fn();
const myPlan = vi.fn();
vi.mock("@/lib/api/client", () => ({
  api: {
    auth: { plan: (...a: unknown[]) => myPlan(...a) },
    admin: {
      plans: (...a: unknown[]) => plans(...a), plan: (...a: unknown[]) => plan(...a), assignablePlans: (...a: unknown[]) => assignable(...a),
      createPlanDraft: (...a: unknown[]) => createDraft(...a), updatePlanDraft: (...a: unknown[]) => updateDraft(...a),
      activatePlan: (...a: unknown[]) => activate(...a), retirePlan: (...a: unknown[]) => retire(...a),
      setUserPlan: (...a: unknown[]) => setUserPlan(...a), setWorkspacePlan: (...a: unknown[]) => setWorkspacePlan(...a),
    },
  },
}));

import { PlanSummary } from "@/components/account/PlanSummary";
import { PlanControl } from "@/components/admin/PlanControl";
import { PlanDetailView } from "@/components/admin/PlanDetailView";
import { PlansView } from "@/components/admin/PlansView";

const ROWS = [
  { id: 2, plan_code: "premium", version: 1, display_name: "Premium (preview)", status: "active", enabled_entitlements: 5, total_entitlements: 5, subscribers: { users: 3, workspaces: 1 }, created_at: null, activated_at: "2026-10-01", retired_at: null },
  { id: 1, plan_code: "basic", version: 1, display_name: "Basic", status: "active", enabled_entitlements: 4, total_entitlements: 5, subscribers: { users: 40, workspaces: 0 }, created_at: null, activated_at: "2026-10-01", retired_at: null },
];
const ENTS = (over: Record<string, boolean> = {}) => ["current_market_research", "standard_history", "standard_progress", "standard_model_profiles", "premium_preview"].map((k) => ({
  code: k, label: `Label ${k}`, description: `Desc ${k}`, type: "boolean", enabled: over[k] ?? k !== "premium_preview", limit: null }));
const DETAIL = (over = {}) => ({ id: 3, plan_code: "premium", version: 2, display_name: "Premium (preview)", status: "draft", editable: true, entitlements: ENTS(),
  subscribers: { users: 0, workspaces: 0 }, created_at: null, activated_at: null, retired_at: null, ...over });

beforeEach(() => {
  mockPerms = ["platform.plans.read", "platform.plans.manage", "platform.subscriptions.manage"];
  plans.mockResolvedValue({ items: ROWS });
  plan.mockResolvedValue(DETAIL());
  assignable.mockResolvedValue([{ plan_code: "basic", version: 1, display_name: "Basic" }, { plan_code: "premium", version: 1, display_name: "Premium (preview)" }]);
  for (const m of [createDraft, updateDraft, activate, retire, setUserPlan, setWorkspacePlan]) m.mockResolvedValue({ version: 2 });
  myPlan.mockResolvedValue({ plan_code: "basic", plan_version: 1, entitlements: Object.fromEntries(ENTS().map((e) => [e.code, { enabled: e.enabled, limit: null, unlimited: e.enabled }])) });
});
afterEach(() => vi.clearAllMocks());

describe("Admin plan catalogue", () => {
  it("lists versions with lifecycle, entitlement and subscriber counts and links to detail - and states there is no pricing", async () => {
    render(<PlansView />);
    const link = await screen.findByRole("link", { name: /Premium \(preview\)/ });
    expect(link).toHaveAttribute("href", "/admin/plans/2");
    expect(screen.getByText("5 of 5 enabled")).toBeInTheDocument();
    expect(screen.getByText("Accounts 40, workspaces 0")).toBeInTheDocument();
    expect(screen.getByText(/no prices, payments or invoices/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\$|€|per month|checkout|invoice number/i);
  });

  it("creates the next draft only with plans.manage, and disables it when a draft exists", async () => {
    const user = userEvent.setup();
    render(<PlansView />);
    await screen.findByRole("link", { name: /Premium/ });
    await user.click(screen.getByRole("button", { name: "Create next draft of premium" }));
    await waitFor(() => expect(createDraft).toHaveBeenCalledWith("premium"));
    expect(await screen.findByText(/Draft version 2 of premium created/)).toBeInTheDocument();
  });

  it("disables creating a draft when one already exists", async () => {
    plans.mockResolvedValue({ items: [{ ...ROWS[0], id: 9, version: 2, status: "draft" }, ...ROWS] });
    render(<PlansView />);
    await screen.findAllByRole("link", { name: /Premium/ });
    expect(screen.getByRole("button", { name: "Create next draft of premium" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Create next draft of basic" })).toBeEnabled();
  });

  it("a read-only role sees the catalogue without any create control, and without plans.read nothing is fetched", async () => {
    mockPerms = ["platform.plans.read"];
    const { unmount } = render(<PlansView />);
    await screen.findByRole("link", { name: /Premium/ });
    expect(screen.queryByRole("button", { name: /Create next draft/ })).not.toBeInTheDocument();
    unmount();
    mockPerms = ["platform.users.read"];
    plans.mockClear();
    render(<PlansView />);
    expect(await screen.findByText(/does not include access/)).toBeInTheDocument();
    expect(plans).not.toHaveBeenCalled();
  });
});

describe("Admin plan detail", () => {
  it("a draft is editable: only registry rows, save sends exactly the changed value, activation needs confirmation (Cancel focused)", async () => {
    const user = userEvent.setup();
    render(<PlanDetailView versionId={3} />);
    const box = await screen.findByLabelText("Include Label premium_preview");
    expect(screen.getAllByRole("checkbox")).toHaveLength(5);            // exactly the code-defined entitlements
    expect(screen.getByRole("button", { name: "Activate this version" })).toBeEnabled();
    await user.click(box);
    expect(screen.getByRole("button", { name: "Activate this version" })).toBeDisabled();   // unsaved edits first
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => expect(updateDraft).toHaveBeenCalledWith(3, { premium_preview: { enabled: true, limit: null } }));
    expect(await screen.findByText("Draft saved.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Activate this version" }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    expect(within(dialog).getByText(/Existing subscribers are not moved and nobody is charged/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Activate" }));
    await waitFor(() => expect(activate).toHaveBeenCalledWith(3));
  });

  it("an active version is immutable (no checkboxes, no save) and can be retired after confirmation", async () => {
    const user = userEvent.setup();
    plan.mockResolvedValue(DETAIL({ status: "active", editable: false, version: 1, activated_at: "2026-10-01" }));
    render(<PlanDetailView versionId={3} />);
    await screen.findByText(/This version is immutable/);
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
    expect(screen.queryByRole("button", { name: "Save draft" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retire this version" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Retire" }));
    await waitFor(() => expect(retire).toHaveBeenCalledWith(3));
  });

  it("a failed activation shows the error inside the dialog and is not retried; read-only shows no controls", async () => {
    const user = userEvent.setup();
    activate.mockRejectedValue(new Error("Only a draft version can be activated."));
    const { unmount } = render(<PlanDetailView versionId={3} />);
    await user.click(await screen.findByRole("button", { name: "Activate this version" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Activate" }));
    expect(await within(screen.getByRole("alertdialog")).findByRole("alert")).toHaveTextContent(/Only a draft/);
    expect(activate).toHaveBeenCalledTimes(1);
    unmount();
    mockPerms = ["platform.plans.read"];
    render(<PlanDetailView versionId={3} />);
    await screen.findByRole("heading", { name: "Plan version" });
    expect(screen.queryByRole("button", { name: /Activate|Save draft|Retire/ })).not.toBeInTheDocument();
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
  });
});

describe("Subject plan control (user and workspace)", () => {
  const PLAN = { current: { plan_code: "basic", version: 1, display_name: "Basic", status: "active", source: "system_default", started_at: "2026-10-01", ended_at: null },
    history: [{ plan_code: "basic", version: 1, display_name: "Basic", status: "active", source: "system_default", started_at: "2026-10-01", ended_at: null }] };

  it("shows the current plan, an access-not-payment note, and changes the user's plan after confirmation", async () => {
    const user = userEvent.setup();
    const changed = vi.fn();
    render(<PlanControl plan={PLAN} subject={{ kind: "user", id: 7 }} onChanged={changed} />);
    expect(screen.getByText("Basic (version 1)")).toBeInTheDocument();
    expect(screen.getByText(/no payment, price or invoice behind it/)).toBeInTheDocument();
    const select = await screen.findByLabelText("Change plan");
    await screen.findByRole("option", { name: "Premium (preview) (version 1)" });
    expect(within(select).queryByRole("option", { name: "Basic (version 1)" })).not.toBeInTheDocument();   // current plan not offered
    await user.selectOptions(select, "premium");
    await user.click(screen.getByRole("button", { name: "Change plan" }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.click(within(dialog).getByRole("button", { name: "Change plan" }));
    await waitFor(() => expect(setUserPlan).toHaveBeenCalledWith(7, "premium"));
    await waitFor(() => expect(changed).toHaveBeenCalledWith(expect.stringContaining("Plan changed to Premium (preview)")));
  });

  it("assigns a workspace plan and says it never raises a member's personal plan", async () => {
    const user = userEvent.setup();
    render(<PlanControl plan={{ current: null, history: [] }} subject={{ kind: "workspace", id: 4 }} onChanged={() => {}} />);
    expect(screen.getByText(/No active subscription \(Basic access applies\)/)).toBeInTheDocument();
    expect(screen.getByText(/never raises a member's personal plan/)).toBeInTheDocument();
    await screen.findByRole("option", { name: "Premium (preview) (version 1)" });
    await user.selectOptions(screen.getByLabelText("Change plan"), "premium");
    await user.click(screen.getByRole("button", { name: "Change plan" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Change plan" }));
    await waitFor(() => expect(setWorkspacePlan).toHaveBeenCalledWith(4, "premium"));
  });

  it("without subscriptions.manage there is no change control and the assignable list is not fetched", async () => {
    mockPerms = ["platform.users.read"];
    render(<PlanControl plan={PLAN} subject={{ kind: "user", id: 7 }} onChanged={() => {}} />);
    expect(screen.queryByLabelText("Change plan")).not.toBeInTheDocument();
    expect(assignable).not.toHaveBeenCalled();
  });
});

describe("Candidate plan view", () => {
  const wrap = (locale: "en" | "de" = "en") => render(<I18nProvider initialLocale={locale}><PlanSummary /></I18nProvider>);
  const t = (k: string) => translate("en", k);

  it("shows the plan name and the server-resolved entitlements, with a preview notice and no purchase affordance", async () => {
    wrap();
    expect(await screen.findByText(t("plan.nameBasic"))).toBeInTheDocument();
    const list = screen.getByRole("list");
    expect(within(list).getByText(t("plan.ent_standard_history")).closest("li")).toHaveTextContent(t("plan.included"));
    expect(within(list).getByText(t("plan.ent_premium_preview")).closest("li")).toHaveTextContent(t("plan.notIncluded"));
    expect(screen.getByText(t("plan.previewNotice"))).toBeInTheDocument();
    expect(screen.getByText(t("plan.noPayments"))).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\$|€|buy now|upgrade now|\/month/i);   // (W10.5: the notice may SAY there is no checkout; it must offer none: no button, no link)
  });

  it("a Premium account is labelled as a preview and still offers nothing to buy", async () => {
    myPlan.mockResolvedValue({ plan_code: "premium", plan_version: 1, entitlements: Object.fromEntries(ENTS().map((e) => [e.code, { enabled: true, limit: null, unlimited: true }])) });
    wrap();
    expect(await screen.findByText(t("plan.namePremium"))).toBeInTheDocument();
    expect(screen.getByText(t("plan.previewNotice"))).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("a load error offers a retry that refetches", async () => {
    myPlan.mockRejectedValueOnce(new Error("x"));
    const user = userEvent.setup();
    wrap();
    await user.click(await screen.findByRole("button", { name: t("plan.retry") }));
    expect(await screen.findByText(t("plan.nameBasic"))).toBeInTheDocument();
  });

  it("is localized (a German account sees German plan copy)", async () => {
    wrap("de");
    expect(await screen.findByText(translate("de", "plan.title"))).toBeInTheDocument();
    expect(screen.getByText(translate("de", "plan.previewNotice"))).toBeInTheDocument();
  });

  const keys = Object.keys(en104.plan);
  it.each(SUPPORTED_LOCALE_CODES)("%s defines every plan key and the export line, with no price or purchase claim", (locale) => {
    for (const k of keys) {
      const v = translate(locale, `plan.${k}`);
      expect(v, `${locale}.plan.${k}`).not.toBe(`plan.${k}`);
    }
    expect(translate(locale, "dataPrivacy.incPlan")).not.toBe("dataPrivacy.incPlan");
    const all = keys.map((k) => translate(locale, `plan.${k}`)).join(" ");
    expect(all).not.toMatch(/[€$£]|\b\d+[.,]\d{2}\b/);
    expect(all).not.toContain(BRAND_SLOGAN);
  });
});

describe("no frontend plan map and no role-name authorisation", () => {
  it("plan components do not derive access from the tier and do not compare role names", () => {
    const files = ["components/account/PlanSummary.tsx", ...readdirSync("components/admin").filter((n) => /Plan/.test(n)).map((n) => `components/admin/${n}`)];
    for (const f of files) {
      const src = readFileSync(f, "utf8");
      expect(src, f).not.toMatch(/\.tier\b|tier\s*===|platform_role\s*===|===\s*"platform_admin"|localStorage|sessionStorage/);
      expect(src, f).not.toContain('from "next/link"');
    }
    expect(readFileSync("components/auth/AccountPanel.tsx", "utf8")).not.toMatch(/account\.tier\s*===/);
  });
});
