import { render, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import table from "./fixtures/deferral-table-07a.json";

// 07A (PG-10, REQ-DEFER-01): the browser-side half of the deferral-inaccessibility evidence. The single table of deferred or gated families lives in tests/_deferral_table_07a.py
// (the API half runs against the real FastAPI app there); this file reads its generated JSON mirror and proves that, while a gate is off, no navigation entry, link, button, route
// or client call exposes the feature. Offline: every API call is mocked and asserted.

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {}, replace: () => {} }), usePathname: () => "/", useSearchParams: () => new URLSearchParams("") }));

const me = vi.fn();
const availability = vi.fn();
const status = vi.fn();
const startCheckout = vi.fn();
const capabilities = vi.fn();
vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    api: {
      auth: { me: (...a: unknown[]) => me(...a), updatePreferences: vi.fn() },
      billing: { availability: (...a: unknown[]) => availability(...a), status: (...a: unknown[]) => status(...a), startCheckout: (...a: unknown[]) => startCheckout(...a) },
      capabilities: (...a: unknown[]) => capabilities(...a),
    },
  };
});

import { PremiumSubscriptionPanel } from "@/components/account/PremiumSubscriptionPanel";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { I18nProvider } from "@/components/i18n/I18nProvider";
import { MoreMenu } from "@/components/layout/MoreMenu";
import { ACCOUNT_NAV, INTERNAL_NAV, PRIMARY_NAV, SECONDARY_NAV } from "@/components/layout/nav-items";
import { ADMIN_DESTINATIONS, ADMIN_GROUPS, P, visibleDestinations } from "@/lib/admin/capabilities";
import { useCapabilities } from "@/lib/useCapabilities";

const FRONTEND = resolve(__dirname, "..");
const FAMILIES = table.families;
const ABSENT_PATHS = FAMILIES.flatMap((f) => f.ui_absent_paths);
const ABSENT_TEXTS = FAMILIES.flatMap((f) => f.ui_absent_texts.map((t) => ({ family: f.id, re: new RegExp(t, "i") })));
const KNOWN_UI = new Set(FAMILIES.flatMap((f) => f.ui_known_routes));
const ALL_PERMISSIONS: string[] = Object.values(P);

function underAbsentPath(href: string): string | undefined {
  const path = href.split("?")[0].replace(/\/$/, "") || "/";
  return ABSENT_PATHS.find((p) => path === p || path.startsWith(p + "/"));
}

function textHits(text: string) {
  return ABSENT_TEXTS.filter(({ re }) => re.test(text)).map(({ family, re }) => `${family}:${re.source}`);
}

/** Every string or template literal in ``src`` that starts with a gated API prefix, with interpolations (nested braces included) replaced by "{}" and any query string removed. */
function gatedPathLiterals(src: string): string[] {
  const out: string[] = [];
  const start = /["'`]\/(?:billing|speech|voice|admin\/billing|admin\/speech|model-profiles)/g;
  let m: RegExpExecArray | null;
  while ((m = start.exec(src))) {
    const quote = src[m.index];
    let i = m.index + 1;
    let lit = "";
    while (i < src.length) {
      const ch = src[i];
      if (quote === "`" && ch === "$" && src[i + 1] === "{") {
        let depth = 1;
        i += 2;
        while (i < src.length && depth > 0) {
          if (src[i] === "{") depth++;
          else if (src[i] === "}") depth--;
          i++;
        }
        lit += "{}";
        continue;
      }
      if (ch === quote) break;
      lit += ch;
      i++;
    }
    out.push(lit.split("?")[0].replace(/([^/])\{\}$/, "$1"));
  }
  return out;
}

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === ".next") continue;
    const full = join(dir, name);
    if (statSync(full).isDirectory()) walk(full, out);
    else out.push(full);
  }
  return out;
}

function appRoutes(): string[] {
  const root = join(FRONTEND, "app");
  return walk(root)
    .filter((f) => /\/page\.tsx$/.test(f))
    .map((f) => "/" + relative(root, f).replace(/\/?page\.tsx$/, "").split("/").filter((s) => s && !/^\(.*\)$/.test(s)).join("/"))
    .map((p) => (p === "/" ? "/" : p.replace(/\/$/, "")));
}

const sourceFiles = ["app", "components", "lib"].flatMap((d) => walk(join(FRONTEND, d))).filter((f) => /\.(ts|tsx)$/.test(f));
const rel = (f: string) => relative(FRONTEND, f);

describe("the table mirror", () => {
  it("lists the ten families once, with the gated UI keywords", () => {
    expect(FAMILIES.map((f) => f.id).sort()).toEqual(["billing_checkout", "billing_reconciliation", "compensation_v2", "history_gating", "international_sources", "mail_delivery_webhook", "model_profile_gating",
      "realtime_voice", "speech_server", "stripe_webhook"]);
    expect(table.gated_ui_keywords.length).toBeGreaterThan(8);
  });
});

describe("Candidate navigation exposes no deferred feature", () => {
  const entries = [...PRIMARY_NAV, ...SECONDARY_NAV, ...INTERNAL_NAV, ACCOUNT_NAV].map((e) => ({
    href: e.href, text: [e.label, "description" in e ? e.description : ""].join(" "),
  }));
  it.each(entries.map((e) => [e.href, e] as const))("%s is not a deferred destination", (_href, e) => {
    expect(underAbsentPath(e.href)).toBeUndefined();
    expect(textHits(e.text)).toEqual([]);
  });
  it("the primary navigation is exactly the five product destinations", () => {
    expect(PRIMARY_NAV.map((n) => n.href)).toEqual(["/opportunities", "/prepare", "/practice", "/progress", "/history"]);
  });
});

describe("Admin navigation exposes no deferred feature", () => {
  it("no destination, even with every permission granted, is a deferred destination", () => {
    const shown = visibleDestinations(ALL_PERMISSIONS);
    expect(shown.length).toBeGreaterThan(10);
    for (const d of shown) {
      expect(underAbsentPath(d.href), d.href).toBeUndefined();
      expect(textHits(`${d.label} ${d.description}`), d.id).toEqual([]);
    }
  });
  it("the Billing and Speech entries state truthfully that they are mock / not active", () => {
    const billing = ADMIN_DESTINATIONS.find((d) => d.id === "billing")!;
    const speech = ADMIN_DESTINATIONS.find((d) => d.id === "speech")!;
    expect(billing.description).toMatch(/not live/i);
    expect(speech.description).toMatch(/not active/i);
    expect(KNOWN_UI.has(billing.href) && KNOWN_UI.has(speech.href)).toBe(true);
  });
  it("every Admin destination carrying a gated keyword is a known, inert route in the table", () => {
    const kw = table.gated_ui_keywords;
    const flagged = ADMIN_DESTINATIONS.filter((d) => kw.some((k) => d.href.includes(k)));
    expect(flagged.map((d) => d.href).sort()).toEqual(["/admin/billing", "/admin/speech"]);
    for (const d of flagged) expect(KNOWN_UI.has(d.href), d.href).toBe(true);
    expect(ADMIN_GROUPS.length).toBeGreaterThan(3);
  });
});

const ACCOUNT = (role: string, perms: string[]) => ({
  user_id: 1, email: "u@example.com", display_name: null, platform_role: role, tier: "basic", status: "active", email_verified: true, providers: ["password"],
  auth_method: "session", capabilities: [], response_detail: "brief", interface_locale: "en", conversation_language: "en", admin_permissions: perms,
});

async function openMore(account: ReturnType<typeof ACCOUNT>) {
  me.mockResolvedValue(account);
  render(
    <AuthProvider>
      <I18nProvider initialLocale="en">
        <MoreMenu />
      </I18nProvider>
    </AuthProvider>,
  );
  await waitFor(() => expect(me).toHaveBeenCalled());
  await userEvent.click(screen.getByRole("button", { name: /more/i }));
  return screen.getAllByRole("menuitem");
}

describe("the More menu", () => {
  beforeEach(() => me.mockReset());
  it.each([["a Candidate", ACCOUNT("user", [])], ["a platform admin with every permission", ACCOUNT("platform_admin", ALL_PERMISSIONS)]] as const)(
    "shows no deferred feature to %s", async (_label, account) => {
      const items = await openMore(account);
      expect(items.length).toBeGreaterThanOrEqual(5);
      for (const el of items) {
        expect(underAbsentPath(el.getAttribute("href") ?? "/"), el.textContent ?? "").toBeUndefined();
        expect(textHits(el.textContent ?? ""), el.textContent ?? "").toEqual([]);
      }
    });
});

describe("the Premium panel with checkout gated off", () => {
  beforeEach(() => { availability.mockReset(); status.mockReset(); startCheckout.mockReset(); });
  const none = { checkout: "none", subscription: "none", payment: "none", confirmation: "not_applicable", entitlement: { plan_code: "basic", source: "entitlement_service", changed_by_billing: false },
    checkout_id: null, created_at: null, expires_at: null };
  const view = () => render(<I18nProvider initialLocale="en"><PremiumSubscriptionPanel /></I18nProvider>);

  it("offers no purchase button when the server says checkout is not enabled, and never starts one", async () => {
    availability.mockResolvedValue({ plan: "premium", available: false, reason: "not_enabled" });
    status.mockResolvedValue(none);
    view();
    await waitFor(() => expect(screen.getByTestId("checkout-unavailable")).toBeInTheDocument());
    expect(screen.queryByTestId("checkout-start")).toBeNull();
    expect(screen.queryByRole("button", { name: /checkout|subscribe|upgrade|pay|buy/i })).toBeNull();
    expect(startCheckout).not.toHaveBeenCalled();
  });
  it("fails closed (no button) when the availability call itself fails", async () => {
    availability.mockRejectedValue(new Error("network"));
    status.mockResolvedValue(none);
    view();
    await waitFor(() => expect(screen.getByTestId("checkout-unavailable")).toBeInTheDocument());
    expect(screen.queryByTestId("checkout-start")).toBeNull();
    expect(startCheckout).not.toHaveBeenCalled();
  });
  it("fails closed when both calls fail", async () => {
    availability.mockRejectedValue(new Error("network"));
    status.mockRejectedValue(new Error("network"));
    view();
    await waitFor(() => expect(screen.queryByTestId("checkout-start")).toBeNull());
    expect(startCheckout).not.toHaveBeenCalled();
  });
});

describe("capabilities", () => {
  beforeEach(() => capabilities.mockReset());
  it("every experimental or deferred capability is OFF when the backend is unreachable", async () => {
    capabilities.mockRejectedValue(new Error("offline"));
    const { result } = renderHook(() => useCapabilities());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.offline).toBe(true);
    expect(result.current.capabilities.realtime_voice_enabled).toBe(false);
    expect(result.current.capabilities.live_interview_enabled).toBe(false);
    expect(result.current.capabilities.company_research_enabled).toBe(false);
  });
  it("the capability contract names no deferred family", () => {
    const types = readFileSync(join(FRONTEND, "lib/api/types.ts"), "utf8");
    const block = /export interface CapabilitiesResponse \{[\s\S]*?\n\}/.exec(types)?.[0] ?? "";
    expect(block.length).toBeGreaterThan(50);
    expect(block).not.toMatch(/compensation|international|global|billing|checkout|stripe|salary/i);
  });
  afterEach(() => capabilities.mockReset());
});

describe("UI route inventory (fails when a gated-keyword route appears unlisted)", () => {
  const routes = appRoutes();
  it("finds the app routes", () => {
    expect(routes.length).toBeGreaterThan(30);
    expect(routes).toContain("/billing/return");
  });
  it("no deferred path exists as a route", () => {
    const hits = routes.filter((r) => underAbsentPath(r));
    expect(hits).toEqual([]);
  });
  it("every route whose path carries a gated keyword is listed in the table as known and inert", () => {
    const kw = table.gated_ui_keywords;
    const gated = routes.filter((r) => r.split("/").some((seg) => kw.some((k) => seg.includes(k))));
    const unlisted = gated.filter((r) => !KNOWN_UI.has(r));
    expect(unlisted, `unlisted gated UI routes (add them to tests/_deferral_table_07a.py): ${unlisted.join(", ")}`).toEqual([]);
    expect(gated.length).toBeGreaterThan(2);
  });
  it("every listed known route really exists", () => {
    for (const r of KNOWN_UI) expect(routes, r).toContain(r);
  });
  it("the route guard really fails for a new unlisted gated route", () => {
    const fake = [...routes, "/billing/portal", "/admin/compensation", "/voice-practice"];
    const kw = table.gated_ui_keywords;
    const gated = fake.filter((r) => r.split("/").some((seg) => kw.some((k) => seg.includes(k))));
    expect(gated.filter((r) => !KNOWN_UI.has(r))).toEqual(expect.arrayContaining(["/billing/portal", "/admin/compensation", "/voice-practice"]));
  });
});

describe("no frontend source reaches a deferred feature", () => {
  const text = new Map(sourceFiles.map((f) => [rel(f), readFileSync(f, "utf8")]));
  const sources = (re: RegExp) => [...text].filter(([name, body]) => re.test(body)).map(([name]) => name).sort();

  it("never calls server-side transcription or synthesis (only /speech/capabilities)", () => {
    expect(sources(/\/speech\/(transcriptions|synthesis)/)).toEqual([]);
  });
  it("loads no payment SDK and holds no payment key", () => {
    expect(sources(/loadStripe|@stripe\/|js\.stripe\.com|pk_live|pk_test|sk_live|sk_test|whsec_/)).toEqual([]);
  });
  it("starts checkout from exactly one component, and mints a realtime session from exactly one hook", () => {
    expect(sources(/\.startCheckout\(/)).toEqual(["components/account/PremiumSubscriptionPanel.tsx"]);
    expect(sources(/\.realtimeSession\(/)).toEqual(["lib/speech/useRealtimeVoice.ts"]);
  });
  it("the realtime voice entry in Practice is gated by the server capability", () => {
    expect(text.get("components/interview/PracticeClient.tsx")).toMatch(/realtimeEnabled\s*=\s*capabilities\.realtime_voice_enabled/);
  });
  it("the typed API client references no deferred API prefix and only listed gated endpoints", () => {
    const client = text.get("lib/api/client.ts")!;
    for (const f of FAMILIES) for (const prefix of f.forbidden_prefixes) expect(client.includes(`"${prefix}`) || client.includes(`\`${prefix}`), prefix).toBe(false);
    const listed = FAMILIES.flatMap((f) => f.api_paths).map((p) => p.replace(/^\/api\/v1/, ""));
    const matches = (clientPath: string) => listed.some((p) => {
      const a = clientPath.split("/"), b = p.split("/");
      return a.length === b.length && a.every((seg, i) => seg === "{}" || seg === b[i] || b[i].startsWith("deferral07a-"));
    });
    const found = gatedPathLiterals(client);
    expect(found.length).toBeGreaterThan(5);
    const unlisted = found.filter((p) => !matches(p));
    expect(unlisted, `the API client calls gated endpoints that the table does not list: ${unlisted.join(", ")}`).toEqual([]);
  });
  it("the mirror's UI absent paths are not linked from any source file", () => {
    const hrefRe = (p: string) => new RegExp(`href=["'\`{]*${p.replace(/\//g, "\\/")}["'\`}/?]`);
    for (const p of ABSENT_PATHS) expect(sources(hrefRe(p)), p).toEqual([]);
  });
  it("the deferral table file exists next to the Python source of truth", () => {
    expect(existsSync(resolve(FRONTEND, "..", "tests/_deferral_table_07a.py"))).toBe(true);
  });
});
