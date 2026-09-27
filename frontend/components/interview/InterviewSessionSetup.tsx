"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";
import { useI18n } from "@/components/i18n/I18nProvider";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { toSupportedLocale, type AppLocale, DEFAULT_APP_LOCALE } from "@/lib/i18n/locales";
import { DocumentPicker } from "@/components/documents/DocumentPicker";
import { ConversationLanguageField } from "@/components/i18n/ConversationLanguageField";

const labelize = (id: string) => id.charAt(0).toUpperCase() + id.slice(1).replace(/_/g, " ");

/**
 * Standalone interview setup — start Practice WITHOUT an Agent Coach handoff (P10B Wave 4).
 * Reads coherently as Target role → Your evidence → Interview, reuses the ONE governed document
 * system for JD/CV selection, and exposes the interview (conversation) language in-flow. The
 * backend-owned taxonomies (career levels) stay the single source of truth; the server resolves
 * any selected document/evidence, so no raw candidate text is held in the browser.
 */
export function InterviewSessionSetup({ onCreated, opportunityId = null }: {
  onCreated: (sessionId: string) => void;
  opportunityId?: number | null;
}) {
  const { t } = useI18n();
  const account = useAuthOptional()?.account;
  const [role, setRole] = useState("");
  const [industry, setIndustry] = useState("");
  const [careerLevels, setCareerLevels] = useState<string[]>([]);
  const [careerLevel, setCareerLevel] = useState("");
  const [count, setCount] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Wave 4 governed context + language.
  const [jdDocId, setJdDocId] = useState<number | null>(null);
  const [useEvidence, setUseEvidence] = useState(false);
  const [conversationLanguage, setConversationLanguage] = useState<AppLocale>(
    toSupportedLocale(account?.conversation_language ?? null) ?? DEFAULT_APP_LOCALE,
  );
  // Optional customisation (backend-owned taxonomies; empty = backend default).
  const [showCustomise, setShowCustomise] = useState(false);
  const [interviewTypeOptions, setInterviewTypeOptions] = useState<string[]>([]);
  const [difficultyOptions, setDifficultyOptions] = useState<string[]>([]);
  const [interviewTypes, setInterviewTypes] = useState<string[]>([]);
  const [difficulty, setDifficulty] = useState("");

  // Keep the language default in sync once the account preference loads.
  useEffect(() => {
    const pref = toSupportedLocale(account?.conversation_language ?? null);
    if (pref) setConversationLanguage(pref);
  }, [account?.conversation_language]);

  // P10B Wave 6: when started from an Opportunity, pre-populate role + JD (the candidate can still
  // edit them). Opportunity context is an initial value, never an override of an explicit choice.
  const [savedNote, setSavedNote] = useState(false);
  useEffect(() => {
    if (opportunityId == null) return;
    let alive = true;
    api.opportunities.get(opportunityId)
      .then((o) => {
        if (!alive) return;
        setSavedNote(true);
        setRole((cur) => cur || o.target_role || "");
        if (o.jd_available && o.job_description_document_id) {
          setJdDocId((cur) => cur ?? o.job_description_document_id ?? null);
        }
      })
      .catch(() => { /* foreign/unknown id: prefill nothing */ });
    return () => { alive = false; };
  }, [opportunityId]);

  useEffect(() => {
    let alive = true;
    api.interviews.options()
      .then((o) => {
        if (!alive) return;
        setCareerLevels(o.career_levels);
        setCareerLevel((prev) => prev || o.career_levels[0] || "");
        setInterviewTypeOptions(o.interview_types ?? []);
        setDifficultyOptions(o.difficulty_levels ?? []);
      })
      .catch(() => { /* options are non-critical; the form still submits with defaults */ });
    return () => { alive = false; };
  }, []);

  const canSubmit = role.trim() && industry.trim() && careerLevel && !busy;

  function toggleType(ty: string) {
    setInterviewTypes((prev) => (prev.includes(ty) ? prev.filter((x) => x !== ty) : [...prev, ty]));
  }

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      const state = await api.interviews.create({
        configuration: {
          target_role: role.trim(),
          industry_or_sector: industry.trim(),
          career_level: careerLevel,
          number_of_questions: count,
          conversation_language: conversationLanguage,
          ...(jdDocId ? { job_description_document_id: jdDocId } : {}),
          ...(useEvidence ? { use_candidate_evidence: true } : {}),
          ...(interviewTypes.length ? { interview_types: interviewTypes } : {}),
          ...(difficulty ? { difficulty } : {}),
        },
        // Owner-scoped organising link (P10B Wave 6); server verifies ownership.
        ...(opportunityId != null ? { opportunity_id: opportunityId } : {}),
      });
      onCreated(state.session_id);
    } catch (e) {
      const err = e as ApiError;
      setError(err.userMessage ?? t("practice.startError"));
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardBody>
        <h1 className="text-lg font-semibold">{t("practice.title")}</h1>
        <p className="mt-1 text-sm text-muted">{t("practice.setupSubtitle")}</p>
        {savedNote ? (
          <p className="mt-2 rounded border border-border bg-surface-2 px-3 py-2 text-sm text-muted">
            {t("opportunity.savedNote")}
          </p>
        ) : null}

        {/* TARGET ROLE */}
        <section className="mt-5 grid gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">{t("prepctx.targetRoleSection")}</h2>
          <Labeled label={t("practice.targetRole")}>
            <Input value={role} onChange={(e) => setRole(e.target.value)}
                   placeholder={t("practice.targetRolePlaceholder")} disabled={busy} />
          </Labeled>
          <Labeled label={t("practice.industry")}>
            <Input value={industry} onChange={(e) => setIndustry(e.target.value)}
                   placeholder={t("practice.industryPlaceholder")} disabled={busy} />
          </Labeled>
          <DocumentPicker category="job_description" value={jdDocId} onChange={setJdDocId}
                          label={t("prepctx.jobDescriptionDoc")} disabled={busy} />
          <p className="text-xs text-muted">{t("prepctx.jobDescriptionDocHelp")}</p>
        </section>

        {/* YOUR EVIDENCE */}
        <section className="mt-6 grid gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">{t("prepctx.yourEvidence")}</h2>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-1 h-4 w-4" checked={useEvidence}
                   onChange={(e) => setUseEvidence(e.target.checked)} disabled={busy} />
            <span>
              <span className="font-medium text-foreground">{t("prepctx.useEvidence")}</span>
              <span className="mt-0.5 block text-xs text-muted">{t("prepctx.useEvidenceHelp")}</span>
            </span>
          </label>
        </section>

        {/* INTERVIEW */}
        <section className="mt-6 grid gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">{t("prepctx.interviewSection")}</h2>
          <Labeled label={t("practice.careerLevel")}>
            <select
              value={careerLevel}
              onChange={(e) => setCareerLevel(e.target.value)}
              disabled={busy || careerLevels.length === 0}
              className="min-h-[44px] rounded border border-border bg-surface px-2 text-sm"
              aria-label={t("practice.careerLevel")}
            >
              {careerLevels.length === 0 ? <option value="">{t("common.loading")}</option> : null}
              {careerLevels.map((lvl) => <option key={lvl} value={lvl}>{labelize(lvl)}</option>)}
            </select>
          </Labeled>
          <Labeled label={t("practice.numberOfQuestions")}>
            <Input type="number" min={1} max={20} value={count}
                   onChange={(e) => setCount(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
                   disabled={busy} />
          </Labeled>
          <ConversationLanguageField value={conversationLanguage} onChange={setConversationLanguage} disabled={busy} />
        </section>

        <button
          type="button"
          onClick={() => setShowCustomise((s) => !s)}
          aria-expanded={showCustomise}
          className="mt-3 text-sm font-medium text-accent"
        >
          {showCustomise ? `− ${t("practice.hideOptions")}` : `＋ ${t("practice.customise")}`}
        </button>

        {showCustomise ? (
          <div className="mt-3 grid gap-4 rounded-lg border border-border bg-surface-2 p-4">
            {interviewTypeOptions.length ? (
              <fieldset className="grid gap-2">
                <legend className="text-sm font-medium">{t("practice.questionTypes")}</legend>
                <p className="text-xs text-muted">{t("practice.questionTypesHelp")}</p>
                <div className="flex flex-wrap gap-x-4 gap-y-2">
                  {interviewTypeOptions.map((ty) => (
                    <label key={ty} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={interviewTypes.includes(ty)}
                        onChange={() => toggleType(ty)}
                        disabled={busy}
                        className="h-4 w-4"
                      />
                      {labelize(ty)}
                    </label>
                  ))}
                </div>
              </fieldset>
            ) : null}
            {difficultyOptions.length ? (
              <Labeled label={t("practice.difficulty")}>
                <select
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                  disabled={busy}
                  className="min-h-[44px] rounded border border-border bg-surface px-2 text-sm"
                  aria-label={t("practice.difficulty")}
                >
                  <option value="">{t("practice.difficultyDefault")}</option>
                  {difficultyOptions.map((d) => <option key={d} value={d}>{labelize(d)}</option>)}
                </select>
              </Labeled>
            ) : null}
          </div>
        ) : null}

        {error ? <p className="mt-3 text-sm text-danger" role="alert">{error}</p> : null}

        <div className="mt-5 flex justify-end">
          <Button onClick={submit} disabled={!canSubmit} aria-busy={busy}>
            {busy ? t("practice.starting") : t("practice.start")}
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="grid gap-1">
      <span className="text-sm font-medium">{label}</span>
      {children}
    </label>
  );
}
