import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { translate } from "@/lib/i18n/catalog";
import type { AppLocale } from "@/lib/i18n/locales";
import type { CareerChatResponse } from "@/lib/api/types";

/**
 * P10B-W9.7A - LANGUAGE OWNERSHIP in the response presentation (deterministic, no model call).
 *
 *   INTERFACE language  -> Ask4Mo UI chrome: "Career evidence: n sources", the "Source" fallback label,
 *                          the screen-reader source list.
 *   CONVERSATION language -> Mo-voiced text: the first-person insufficient-evidence note (it stands in
 *                          for Mo's own prose, beside an answer the backend now writes in that language).
 *   Verbatim              -> source titles, URLs, years, the answer text, calculated values.
 */

let conversation: string | undefined = "en";
vi.mock("@/components/auth/AuthProvider", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/components/auth/AuthProvider")>();
  return { ...actual, useAuthOptional: () => ({ status: "authenticated", account: { conversation_language: conversation } }) };
});

import { CareerAnswer } from "@/components/preparation/CareerAnswer";
import { AgentSources } from "@/components/agent/AgentSources";
import { I18nProvider } from "@/components/i18n/I18nProvider";

function response(over: Partial<CareerChatResponse> = {}): CareerChatResponse {
  return {
    answer: "Evidence (from sources): No sources were retrieved.\nTool results (calculated): None provided.\nRecommendation: Add a job description.",
    has_evidence: false,
    sources: [],
    citations: [],
    tools: [],
    ...over,
  } as unknown as CareerChatResponse;
}

function show(ui: AppLocale, conv: string, r: CareerChatResponse) {
  conversation = conv;
  return render(
    <I18nProvider initialLocale={ui}>
      <CareerAnswer response={r} />
    </I18nProvider>,
  );
}

const MATRIX: Array<[AppLocale, AppLocale]> = [
  ["de", "en"], // interface German, conversation English  -> note English, labels German
  ["en", "de"], // interface English, conversation German  -> note German,  labels English
  ["ru", "en"], // interface Russian, conversation English -> note English, labels Russian
  ["en", "ru"], // interface English, conversation Russian -> note Russian, labels English
  ["ru", "ru"], // both Russian                            -> everything Russian
];

describe("insufficient-evidence note: owned by the Mo CONVERSATION language, not the interface language", () => {
  for (const [ui, conv] of MATRIX) {
    it(`interface=${ui} conversation=${conv}: note in ${conv}`, () => {
      show(ui, conv, response());
      expect(screen.getByText(translate(conv, "coach.insufficientEvidence"))).toBeInTheDocument();
      if (ui !== conv) {
        expect(screen.queryByText(translate(ui, "coach.insufficientEvidence"))).not.toBeInTheDocument();
      }
    });
  }

  it("falls back to English for an unset/unsupported conversation language (never a raw key)", () => {
    show("de", "zz", response());
    expect(screen.getByText(translate("en", "coach.insufficientEvidence"))).toBeInTheDocument();
  });

  it("no note when the answer has evidence", () => {
    show("de", "de", response({ has_evidence: true }));
    expect(screen.queryByText(translate("de", "coach.insufficientEvidence"))).not.toBeInTheDocument();
  });
});

describe("source labels: owned by the INTERFACE language; source content verbatim", () => {
  const sources = [
    { title: "O*NET OnLine", source_url: "https://www.onetonline.org/", reference_year: 2025 },
    { title: null, occupation_title: null, source_url: null },
  ] as unknown as CareerChatResponse["sources"];

  for (const [ui, conv] of MATRIX) {
    it(`interface=${ui} conversation=${conv}: label in ${ui}, titles/URLs untouched`, () => {
      const { container } = show(ui, conv, response({ has_evidence: true, sources }));
      expect(screen.getByText(translate(ui, "prepare.evidenceSourcesOther", { n: 2 }))).toBeInTheDocument();
      // Verbatim source title + URL + year, regardless of either language setting.
      const link = screen.getByRole("link", { name: "O*NET OnLine" });
      expect(link).toHaveAttribute("href", "https://www.onetonline.org/");
      expect(container.textContent).toContain("2025");
      // Untitled source uses the INTERFACE-language fallback label.
      expect(screen.getByText(translate(ui, "prepare.sourceUntitled"))).toBeInTheDocument();
      // Screen-reader list: interface-language prefix, verbatim names.
      expect(container.querySelector(".sr-only")?.textContent).toBe(translate(ui, "prepare.sourcesAria", { names: "O*NET OnLine" }));
    });
  }

  it("singular/plural labels (1 source vs n sources) in every locale", () => {
    for (const ui of ["en", "de", "fr", "es", "it", "pt", "nl", "ru"] as AppLocale[]) {
      const { unmount } = show(ui, "en", response({ has_evidence: true, sources: [sources![0]] }));
      expect(screen.getByText(translate(ui, "prepare.evidenceSourcesOne"))).toBeInTheDocument();
      unmount();
    }
  });

  it("AgentSources (Agent Coach) uses the same interface-owned labels", () => {
    render(
      <I18nProvider initialLocale="ru">
        <AgentSources sources={[{ title: "ESCO", source_url: null } as never, { title: null, source_url: null } as never]} />
      </I18nProvider>,
    );
    expect(screen.getByText(translate("ru", "prepare.evidenceSourcesOther", { n: 2 }))).toBeInTheDocument();
    expect(screen.getByText("ESCO")).toBeInTheDocument();
    expect(screen.getByText(translate("ru", "prepare.sourceUntitled"))).toBeInTheDocument();
  });
});

describe("the three response-template headings in the answer are Mo prose, not UI chrome", () => {
  it("the component never rewrites or translates the model's answer text", () => {
    const answer = "Belege (aus Quellen): Keine Quellen abgerufen.\nEmpfehlung: Fügen Sie eine Stellenbeschreibung hinzu.";
    show("en", "de", response({ answer }));
    expect(screen.getByText(/Belege \(aus Quellen\)/)).toBeInTheDocument(); // rendered verbatim, English UI
  });
});
