import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";
import { BRAND_SLOGAN } from "@/lib/brand";

/** P10B-W9.9 - trust copy, evidence presentation, navigation links and a11y semantics (deterministic). */

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/app" }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuth: () => ({
    account: { email: "a@example.com", display_name: null, platform_role: "user" },
    status: "authenticated", isRealSession: true, signOut: vi.fn(),
  }),
  useAuthOptional: () => ({ account: { platform_role: "user", conversation_language: "en" }, status: "authenticated", responseDetail: "brief" }),
}));

import { TrustContent } from "@/components/marketing/TrustContent";
import { AgentSources } from "@/components/agent/AgentSources";
import { AgentConversation } from "@/components/agent/AgentConversation";
import { AccountMenu } from "@/components/auth/AccountMenu";

const t = (k: string, v?: Record<string, string | number>) => translate("en", k, v);

describe("Trust page", () => {
  it("is organised into four labelled groups with an AI-limitations statement and a Data & privacy link", () => {
    render(<TrustContent />);
    for (const id of ["ai", "control", "data", "voice"]) {
      const group = screen.getByTestId(`trust-group-${id}`);
      expect(within(group).getByRole("heading", { level: 2 })).toBeInTheDocument();
    }
    const ai = screen.getByTestId("trust-group-ai");
    expect(within(ai).getByText(t("trustUx.limitsTitle"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: t("trustUx.yourDataLink") })).toHaveAttribute("href", "/account/data");
    // every previous control is still present (nothing silently dropped)
    expect(screen.getAllByRole("term").length).toBeGreaterThanOrEqual(17);
  });

  it("makes no absolute or certification claims", () => {
    const { container } = render(<TrustContent />);
    expect(container.textContent).not.toMatch(
      /100%|completely private|GDPR[- ]compliant|never retained|bias-free|fully unbiased|enterprise-grade|human reviewed|every answer is verified/i,
    );
  });
});

describe("Evidence presentation", () => {
  const sources = [
    { title: "O*NET", source_url: "https://www.onetcenter.org/", evidence_type: "occupation", geography: "US", reference_year: 2024 },
    { title: null, source_url: null, evidence_type: "narrative", geography: null, reference_year: null },
  ] as never;

  it("numbers sources so they match the [n] citation markers, with an explanatory hint", () => {
    render(<AgentSources sources={sources} />);
    expect(screen.getByRole("list").tagName).toBe("OL");
    const items = screen.getAllByRole("listitem");
    expect(items[0].textContent).toContain("[1]");
    expect(items[1].textContent).toContain("[2]");
    expect(screen.getByText(t("trustUx.sourcesHint"))).toBeInTheDocument();
  });

  it("shows the contextual AI note (with a link to AI transparency) only once an assistant answer exists", () => {
    const { rerender } = render(<AgentConversation run={null} busy={false} messages={[{ role: "user", content: "hi" }]} />);
    expect(screen.queryByTestId("ai-cue")).not.toBeInTheDocument();
    rerender(<AgentConversation run={null} busy={false} messages={[{ role: "user", content: "hi" }, { role: "assistant", content: "Hello" }]} />);
    const cue = screen.getByTestId("ai-cue");
    expect(cue).toHaveTextContent(t("trustUx.aiCueBody"));
    expect(within(cue).getByRole("link", { name: t("trustUx.aiCueLink") })).toHaveAttribute("href", "/ai-transparency");
  });
});

describe("Navigation discoverability", () => {
  it("account menu links to Data & privacy and Trust, alongside Account, Settings and Sign out", async () => {
    render(<AccountMenu />);
    await userEvent.click(screen.getByRole("button", { name: t("nav.account") }));
    const menu = screen.getByRole("menu");
    expect(within(menu).getByRole("menuitem", { name: t("trustUx.navDataPrivacy") })).toHaveAttribute("href", "/account/data");
    expect(within(menu).getByRole("menuitem", { name: t("trustUx.navTrust") })).toHaveAttribute("href", "/trust");
    expect(within(menu).getAllByRole("menuitem")).toHaveLength(5);
  });
});

describe("Truthful privacy copy", () => {
  it("account deletion copy does not claim agent context/checkpoints are removed and states the limitation", () => {
    for (const locale of SUPPORTED_LOCALE_CODES) {
      const v = translate(locale, "account.privacyDataDesc");
      expect(v, locale).not.toMatch(/checkpoint|agent context|контекст агента|contexte de l.agent|contexto del agente|Agentenkontext|contesto dell.agente|contexto do agente|agentcontext/i);
      if (locale !== "en") expect(v, locale).not.toBe(translate("en", "account.privacyDataDesc"));
    }
    expect(t("account.privacyDataDesc")).toContain("preparation-chat working data may remain");
  });

  it("trustUx copy is complete in all 8 locales, dash-free, and the slogan is untouched", async () => {
    const keys = Object.keys((await import("@/lib/i18n/messages/w99/en")).default.trustUx);
    for (const locale of SUPPORTED_LOCALE_CODES) {
      for (const k of keys) {
        const v = translate(locale, `trustUx.${k}`);
        expect(v, `${locale}.${k}`).not.toBe(`trustUx.${k}`);
        expect(v, `${locale}.${k}`).not.toMatch(/[—–]/);
      }
      if (locale !== "en") expect(translate(locale, "trustUx.limitsTitle")).not.toBe(t("trustUx.limitsTitle"));
      expect(translate(locale, "common.tagline")).toBe(BRAND_SLOGAN);
    }
  });
});
