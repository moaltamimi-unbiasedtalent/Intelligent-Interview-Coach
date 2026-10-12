import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CATALOGS, translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES, type AppLocale } from "@/lib/i18n/locales";
import { I18nProvider } from "@/components/i18n/I18nProvider";
import { AgentConversation } from "@/components/agent/AgentConversation";
import { AgentSources } from "@/components/agent/AgentSources";
import { ProvenanceBadge } from "@/components/trust/ProvenanceBadge";
import { candidateEvidenceSelected, externalSourcesUsed } from "@/lib/provenance";
import type { AgentConversationMessage, AgentRunResponse, AgentSource } from "@/lib/api/types";

/**
 * Pilot 2 P2-04: AI / external-source / candidate-evidence provenance. Mo's prose is AI-generated; retrieved sources support retrieved career
 * evidence only (never the whole answer); "Your evidence considered" appears ONLY when the deterministic Candidate Evidence specialist returned a
 * non-empty selection (server event), never from retrieval_used or journey.understand.evidence_used.
 */

const t = (k: string, v?: Record<string, string | number>, l: AppLocale = "en") => translate(l, k, v);
const wrap = (ui: React.ReactElement, locale: AppLocale = "en") => render(<I18nProvider initialLocale={locale}>{ui}</I18nProvider>);

const MESSAGES: AgentConversationMessage[] = [
  { role: "user", content: "How do I prepare?" },
  { role: "assistant", content: "Start with the role requirements." },
];
const SOURCE = { title: "O*NET Registered Nurses", source_url: "https://www.onetonline.org/link/summary/29-1141.00", evidence_type: "role", geography: "US", reference_year: 2024 } as AgentSource;
const run = (over: Partial<AgentRunResponse> = {}): AgentRunResponse => ({
  run_id: "r1", status: "completed", response: "x", tools_used: [], retrieval_used: false, sources: [], citations: [], memory_used: false, memory_count: 0,
  awaiting_human_input: false, handoff_approved: false, events: [], tool_calls: [], warnings: [], step_count: 1, turn_step_count: 1, conversation: MESSAGES, ...over,
} as AgentRunResponse);
const evidenceEvent = (over: Record<string, unknown> = {}) => ({ event_type: "tool_completed", tool_name: "FindCandidateEvidence", status: "ok", source_count: 2, step: 1, ...over });
const show = (r: AgentRunResponse | null, locale: AppLocale = "en") => wrap(<AgentConversation run={r} busy={false} messages={MESSAGES} />, locale);

describe("assistant answer provenance", () => {
  it("labels the latest Mo answer as AI-generated, inside the answer, with an honest explanation", () => {
    show(run());
    const ai = screen.getByTestId("ai-provenance");
    expect(within(ai).getByText("AI-generated")).toBeVisible();
    expect(ai.textContent).toContain("Mo created this response with AI. Check important details.");
    expect(ai.closest("li")?.textContent).toContain("Start with the role requirements.");   // it belongs to the answer, not a footer
    expect(ai.textContent).not.toMatch(/verified|human coach|recruiter|employer/i);
  });

  it("keeps the AI transparency link reachable", () => {
    show(run());
    expect(screen.getByRole("link", { name: t("trustUx.aiCueLink") })).toHaveAttribute("href", "/ai-transparency");
  });

  it("a source-free response does NOT claim external sources", () => {
    show(run({ sources: [], retrieval_used: false }));
    expect(screen.queryByText(/External sources used/i)).toBeNull();
    expect(screen.queryByTestId("external-sources")).toBeNull();
  });

  it("a response with sources shows 'External sources used' with real titles, without claiming the whole answer is verified", () => {
    show(run({ sources: [SOURCE, { ...SOURCE, title: "ESCO", source_url: null } as AgentSource], retrieval_used: true }));
    const box = screen.getByTestId("external-sources");
    expect(within(box).getByText("External sources used: 2")).toBeInTheDocument();
    expect(within(box).getByRole("link", { name: "O*NET Registered Nurses" })).toHaveAttribute("rel", expect.stringContaining("noopener"));
    expect(within(box).getByText("ESCO").tagName).not.toBe("A");                                   // no URL: plain text
    expect(box.textContent).toContain("Mo's response itself is still AI-generated");
    expect(box.textContent).not.toMatch(/\b(verified|fact[- ]checked|fully sourced|every sentence)\b/i);
    expect(box.textContent).not.toMatch(/chunk|embedding|score/i);                                  // no internals
  });

  it("shows 'Your evidence considered' ONLY when the Candidate Evidence specialist returned a non-empty selection", () => {
    const { unmount } = show(run({ events: [evidenceEvent()] as never }));
    const box = screen.getByTestId("candidate-evidence-provenance");
    expect(within(box).getByText("Your evidence considered")).toBeVisible();
    expect(box.textContent).toContain("Mo's wording is still AI-generated");
    unmount();
    show(run());
    expect(screen.queryByTestId("candidate-evidence-provenance")).toBeNull();
  });

  it("does NOT infer candidate evidence from retrieval_used, journey.understand.evidence_used, a failed or empty specialist call, or other tools", () => {
    const journeyOnly = run({ retrieval_used: true, journey: { understand: { evidence_used: true } } as never, sources: [SOURCE] });
    const { unmount } = show(journeyOnly);
    expect(screen.queryByTestId("candidate-evidence-provenance")).toBeNull();
    unmount();
    for (const events of [
      [evidenceEvent({ source_count: 0 })],                       // empty selection
      [evidenceEvent({ status: "error" })],                       // not ok
      [evidenceEvent({ event_type: "tool_failed" })],             // failed
      [evidenceEvent({ tool_name: "SearchCareerKnowledge" })],    // another tool with sources
    ]) {
      const u = show(run({ events: events as never, retrieval_used: true }));
      expect(screen.queryByTestId("candidate-evidence-provenance")).toBeNull();
      u.unmount();
    }
    expect(candidateEvidenceSelected(null)).toBe(false);
  });

  it("external-source signal is only the actual returned sources", () => {
    expect(externalSourcesUsed(run())).toBe(0);
    expect(externalSourcesUsed(run({ sources: [SOURCE] }))).toBe(1);
    expect(externalSourcesUsed(run({ retrieval_used: true }))).toBe(0);                            // retrieval alone is not a source claim
  });

  it("explains what the labels mean, and 'Reviewed by you' is not third-party verification", () => {
    show(run());
    const ex = screen.getByTestId("provenance-explainer");
    expect(ex.querySelector("summary")?.textContent).toBe("What these labels mean");
    for (const frag of ["AI-generated", "External source", "Your evidence", "Reviewed by you"]) expect(ex.textContent).toContain(frag);
    expect(ex.textContent).toContain("does not mean a third party verified it");
  });
});

describe("AgentSources keeps safe provenance", () => {
  it("renders titles, a safe clickable link and no internals", () => {
    wrap(<AgentSources sources={[SOURCE]} />);
    expect(screen.getByRole("link", { name: "O*NET Registered Nurses" })).toHaveAttribute("href", SOURCE.source_url!);
    expect(screen.getByText("External sources used: 1")).toBeInTheDocument();
  });
});

describe("ProvenanceBadge", () => {
  it("renders visible text for each bounded kind (never colour or icon alone) and its explanation as text, not a tooltip", () => {
    for (const [kind, label] of [["ai", "AI-generated"], ["external_source", "External sources used"], ["candidate_evidence", "Your evidence considered"], ["candidate_reviewed", "Reviewed by you"]] as const) {
      const { container, unmount } = wrap(<ProvenanceBadge kind={kind} explain />);
      expect(screen.getByText(label)).toBeVisible();
      expect(container.querySelector("[title]")).toBeNull();
      expect(container.querySelector(`[data-provenance="${kind}"]`)?.textContent!.length).toBeGreaterThan(label.length + 10);
      unmount();
    }
  });
});

describe("provenance translations", () => {
  it("all provenance keys exist in the eight locales, are translated and never claim verification", () => {
    const keys = Object.keys((CATALOGS.en as unknown as Record<string, Record<string, string>>).provenance);
    expect(keys.length).toBeGreaterThanOrEqual(18);
    for (const locale of SUPPORTED_LOCALE_CODES) {
      for (const k of keys) {
        const v = t(`provenance.${k}`, { n: 2 }, locale);
        expect(v, `${locale}.${k}`).not.toBe(`provenance.${k}`);
        expect(v, `${locale}.${k}`).not.toMatch(/[—–]/);
        if (locale !== "en") expect(v, `${locale}.${k}`).not.toBe(t(`provenance.${k}`, { n: 2 }));
      }
    }
    expect(t("provenance.reviewedExplain")).toMatch(/does not mean a third party verified it/);
  });

  it("renders the AI label and external-source summary in German and Russian without raw keys", () => {
    for (const locale of ["de", "ru"] as const) {
      const { container, unmount } = show(run({ sources: [SOURCE] }), locale);
      expect(container.textContent).not.toMatch(/provenance\.\w+/);
      expect(within(screen.getByTestId("ai-provenance")).getByText(t("provenance.aiLabel", undefined, locale))).toBeInTheDocument();
      expect(screen.getByText(t("provenance.sourcesSummaryOne", undefined, locale))).toBeInTheDocument();
      unmount();
    }
  });
});
