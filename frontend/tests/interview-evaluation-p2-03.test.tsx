import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CATALOGS, translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES, type AppLocale } from "@/lib/i18n/locales";
import type { EvaluationOut } from "@/lib/api/types";
import { I18nProvider } from "@/components/i18n/I18nProvider";
import { InterviewEvaluation } from "@/components/interview/InterviewEvaluation";
import { ReportView } from "@/components/interview/ReportView";

/**
 * Pilot 2 P2-03: Interview Answer Score interpretation and labelling. The evaluation is LLM-backed, schema-validated and model-produced;
 * overall_score (0-100) is NOT computed from the seven rubric dimensions (1-10) by application code. These tests pin the labelling and the
 * absence of any invented formula or bands.
 */

const EVAL: EvaluationOut = {
  overall_score: 72, relevance: 7, structure: 7, evidence: 6, role_knowledge: 7, problem_solving: 7, communication: 7, credibility: 7,
  strengths: ["Clear structure"], improvement_areas: ["Add a metric"], missing_evidence: ["A concrete result"],
  stronger_answer_structure: "Situation, action, result.", improved_example_answer: "", follow_up_question: "What would you change?",
};
const t = (k: string, v?: Record<string, string | number>, l: AppLocale = "en") => translate(l, k, v);
const wrap = (ui: React.ReactElement, locale: AppLocale = "en") => render(<I18nProvider initialLocale={locale}>{ui}</I18nProvider>);

describe("P2-03 Interview Answer Score", () => {
  it("shows a visible 'Interview Answer Score' label with the value as 72 / 100", () => {
    wrap(<InterviewEvaluation evaluation={EVAL} />);
    const panel = screen.getByTestId("answer-score");
    expect(within(panel).getByText("Interview Answer Score")).toBeVisible();
    expect(panel.textContent).toContain("72");
    expect(panel.textContent).toContain("/ 100");
    // accessible combined name: "72 out of 100", associated with the label
    expect(screen.getByRole("group", { name: "Interview Answer Score: 72 out of 100" })).toBeInTheDocument();
  });

  it("says the score is for THIS answer, that the full interview has a separate Practice Readiness score, and keeps the hiring disclaimer", () => {
    wrap(<InterviewEvaluation evaluation={EVAL} />);
    const panel = screen.getByTestId("answer-score");
    expect(panel.textContent).toMatch(/this answer only/i);
    expect(panel.textContent).toMatch(/full interview receives a separate Practice Readiness score/i);
    expect(panel.textContent).toContain("Practice feedback only, not a hiring decision.");
    expect(panel.textContent).not.toMatch(/candidate score|employability|hiring score|probability|job[- ]fit|likelihood of/i);
  });

  it("renders all seven existing rubric dimensions with the exact backend values on a /10 scale", () => {
    wrap(<InterviewEvaluation evaluation={EVAL} />);
    const rubric = screen.getByTestId("rubric-scores");
    const expected: Record<string, [string, number]> = {
      relevance: ["Relevance", 7], structure: ["Structure & clarity", 7], evidence: ["Evidence & examples", 6], role_knowledge: ["Role knowledge", 7],
      problem_solving: ["Problem-solving", 7], communication: ["Communication", 7], credibility: ["Credibility & consistency", 7],
    };
    expect(rubric.querySelectorAll("[data-dimension]")).toHaveLength(7);
    for (const [field, [label, value]] of Object.entries(expected)) {
      const row = rubric.querySelector(`[data-dimension="${field}"]`) as HTMLElement;
      expect(within(row).getByText(label)).toBeInTheDocument();
      expect(row.textContent).toContain(`${value} / 10`);
      expect(within(row).getByText(`${label}: ${value} out of 10`)).toBeInTheDocument();      // screen-reader name ties label and value
      expect(row.textContent).not.toMatch(/\/ 100/);
    }
    // a dimension is a <dt>/<dd> pair, so the value is programmatically associated with its label
    expect(rubric.querySelectorAll("dt")).toHaveLength(7);
  });

  it("introduces no formula, average, weighting or score bands", () => {
    const { container } = wrap(<InterviewEvaluation evaluation={EVAL} />);
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/average|weighted|sum of|calculated from|formula is|excellent|good\b|fair\b|poor\b|\b(90|70|50)\s*(-|to)\s*(100|89|69)\b/i);
    expect(text).toContain("not presented as a formula");                                      // the explicit non-formula statement
    expect(text).not.toMatch(/=\s*\(|÷|\bmean\b/);
  });

  it("explains credibility as consistency and support in the answer text only, never deception, honesty or voice detection", () => {
    wrap(<InterviewEvaluation evaluation={EVAL} />);
    const desc = t("practice.dimCredibilityDesc");
    expect(desc).toMatch(/consistent and well supported/i);
    expect(desc).toMatch(/never at your voice/i);
    expect(desc).toMatch(/not a check of whether you are telling the truth/i);
    for (const locale of SUPPORTED_LOCALE_CODES) {
      expect(t("practice.dimCredibilityDesc", undefined, locale), locale).not.toMatch(/lie detect|detects? (lies|deception)|honesty score/i);
    }
  });

  it("points the candidate to the existing feedback sections for the next answer, without inventing a retry action", () => {
    wrap(<InterviewEvaluation evaluation={EVAL} />);
    expect(screen.getByTestId("next-step-cue").textContent).toBe(t("practice.nextStepCue"));
    expect(screen.queryByRole("button")).toBeNull();                                            // no new workflow action
    expect(screen.getByText(t("practice.evalWhatImprove"))).toBeInTheDocument();
    expect(screen.getByText(t("practice.evalMissingEvidence"))).toBeInTheDocument();
  });

  it("Deep Dive feedback uses the same score presentation (same component, deep-dive heading)", () => {
    wrap(<InterviewEvaluation evaluation={EVAL} heading={t("practice.ddFeedbackHeading")} />);
    expect(screen.getByRole("heading", { level: 2, name: t("practice.ddFeedbackHeading") })).toBeInTheDocument();
    expect(screen.getByTestId("answer-score").textContent).toContain("Interview Answer Score");
    expect(screen.getByTestId("rubric-scores").querySelectorAll("[data-dimension]")).toHaveLength(7);
  });

  it("keeps the session-level readiness score separate and unchanged in the final report", () => {
    wrap(<ReportView report={{ overall_readiness_score: 81 } as never} />);
    expect(screen.getByText(/Practice readiness/)).toBeInTheDocument();
    expect(screen.queryByText("Interview Answer Score")).toBeNull();
  });

  it("every new key exists in all eight locales and is translated", () => {
    const keys = Object.keys(CATALOGS.en.practice as Record<string, string>).filter((k) => /^(answerScore|rubric|dim|nextStepCue)/.test(k) || k === "evalScoreAria");
    expect(keys.length).toBeGreaterThanOrEqual(21);
    for (const locale of SUPPORTED_LOCALE_CODES) {
      for (const k of keys) {
        const v = t(`practice.${k}`, undefined, locale);
        expect(v, `${locale}.${k}`).not.toBe(`practice.${k}`);
        expect(v, `${locale}.${k}`).not.toMatch(/[—–]/);
        if (locale !== "en" && !/^dimRelevance$|^dimCommunication$/.test(k)) expect(v, `${locale}.${k}`).not.toBe(t(`practice.${k}`));
      }
    }
  });

  it("renders in German and Russian with real labels, no raw keys and the values intact", () => {
    for (const locale of ["de", "ru"] as const) {
      const { container, unmount } = wrap(<InterviewEvaluation evaluation={EVAL} />, locale);
      const text = container.textContent ?? "";
      expect(text).not.toMatch(/practice\.\w+/);
      expect(within(screen.getByTestId("answer-score")).getByText(t("practice.answerScoreLabel", undefined, locale))).toBeInTheDocument();
      expect(text).toContain("72");
      expect(text).toContain("6 / 10");
      expect(screen.getByTestId("rubric-scores").querySelectorAll("[data-dimension]")).toHaveLength(7);
      unmount();
    }
  });
});
