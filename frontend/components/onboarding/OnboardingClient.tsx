"use client";

/**
 * Premium first-run onboarding (P10B Wave 2).
 *
 * Configures the candidate's account defaults so the first authenticated experience reads as setting
 * up a personal AI coach, not a generic tutorial. It REUSES the existing preference architecture
 * (`api.auth.updatePreferences`, `LanguageSettings`, `ResponseDetailPreference`) — no parallel store.
 * Progress is persisted server-side (`api.auth.onboarding`) so an interrupted flow resumes. On
 * completion it routes to /app and starts NOTHING (no mic, interview, agent run or processing).
 *
 * Boundaries: coaching style is tone only (never scoring); career geography is independent of any
 * language; nothing sensitive/protected is collected; values are DATA, never placed in a prompt here.
 */

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api/client";
import { useAuth } from "@/components/auth/AuthProvider";
import { useI18n } from "@/components/i18n/I18nProvider";
import { APP_HOME } from "@/lib/auth/routes";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";
import { Alert } from "@/components/ui/Alert";
import { LanguageSettings } from "@/components/settings/LanguageSettings";
import { ResponseDetailPreference } from "@/components/settings/ResponseDetailPreference";
import { CoachingStyleField, type CoachingStyle } from "@/components/settings/CoachingStyleField";
import { CareerGeographyField, type CareerGeography } from "@/components/settings/CareerGeographyField";

const STEP_KEYS = ["stepWelcome", "stepAbout", "stepCareer", "stepCoaching", "stepLanguage", "stepPrivacy", "stepReview"] as const;
const TOTAL = STEP_KEYS.length; // 7 configuration steps (0..6); completion routes to /app

export function OnboardingClient() {
  const { t } = useI18n();
  const { account, refresh } = useAuth();
  const router = useRouter();

  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [geography, setGeography] = useState<CareerGeography>("");
  const [coaching, setCoaching] = useState<CoachingStyle>("balanced");
  const [hydrated, setHydrated] = useState(false);

  // Resume from the persisted account state exactly once (never clobber in-flight edits).
  useEffect(() => {
    if (hydrated || !account) return;
    setName(account.display_name ?? "");
    setTargetRole(account.target_role ?? "");
    setGeography((account.career_geography ?? "") as CareerGeography);
    setCoaching(((account.coaching_style as CoachingStyle) || "balanced"));
    setStep(Math.min(Math.max(account.onboarding_step ?? 0, 0), TOTAL - 1));
    setHydrated(true);
  }, [account, hydrated]);

  // Persist the account-backed fields owned by the current step. Language + response detail persist
  // themselves via their own controls, so this covers name/role/geography/coaching only.
  const saveCurrentStep = useCallback(async () => {
    if (step === 1) await api.auth.updatePreferences({ display_name: name.trim() });
    else if (step === 2) await api.auth.updatePreferences({ target_role: targetRole.trim(), career_geography: geography });
    else if (step === 3) await api.auth.updatePreferences({ coaching_style: coaching });
  }, [step, name, targetRole, geography, coaching]);

  const goNext = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await saveCurrentStep();
      const next = Math.min(step + 1, TOTAL - 1);
      await api.auth.onboarding({ step: next });
      setStep(next);
    } finally {
      setBusy(false);
    }
  }, [saveCurrentStep, step]);

  const goBack = useCallback(() => { setError(null); setStep((s) => Math.max(0, s - 1)); }, []);

  const finish = useCallback(async () => {
    // Guard against a duplicate completion while one is already in flight.
    if (busy) return;
    setBusy(true);
    setError(null);  // clear any previous completion error when a retry begins
    try {
      // Safety re-save of all account-backed fields, then mark complete. The completion API is
      // authoritative: only on success do we refresh the account and enter the app.
      await api.auth.updatePreferences({
        display_name: name.trim(), target_role: targetRole.trim(),
        career_geography: geography, coaching_style: coaching,
      });
      await api.auth.onboarding({ complete: true });
      await refresh();
      router.replace(APP_HOME);
    } catch {
      // Stay on onboarding, keep every saved choice, and surface a safe, recoverable message
      // (never a raw API/provider error, never a logged preference value). The candidate can retry.
      setError(t("onboarding.completionError"));
      setBusy(false);
    }
  }, [busy, name, targetRole, geography, coaching, refresh, router, t]);

  const pct = Math.round(((step + 1) / TOTAL) * 100);

  return (
    <section className="mx-auto max-w-2xl animate-enter">
      {/* Accessible progress. */}
      <div className="mb-6">
        <p className="text-sm font-medium text-muted" role="status" aria-live="polite">
          {t("onboarding.progress", { n: step + 1, total: TOTAL })} · {t(`onboarding.${STEP_KEYS[step]}`)}
        </p>
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-2"
             role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}
             aria-label={t("onboarding.progress", { n: step + 1, total: TOTAL })}>
          <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <Card>
        <CardBody className="space-y-5">
          {step === 0 ? (
            <StepBody title={t("onboarding.welcomeTitle")} body={t("onboarding.welcomeBody")} />
          ) : null}

          {step === 1 ? (
            <>
              <StepBody title={t("onboarding.aboutTitle")} body={t("onboarding.aboutBody")} />
              <label className="grid gap-1">
                <span className="text-sm font-medium text-foreground">{t("onboarding.nameLabel")}</span>
                <span className="text-xs text-muted">{t("onboarding.nameHelp")}</span>
                <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={255} disabled={busy} />
              </label>
            </>
          ) : null}

          {step === 2 ? (
            <>
              <StepBody title={t("onboarding.careerTitle")} body={t("onboarding.careerBody")} />
              <label className="grid gap-1">
                <span className="text-sm font-medium text-foreground">{t("onboarding.targetRoleLabel")}</span>
                <span className="text-xs text-muted">{t("onboarding.targetRoleHelp")}</span>
                <Input value={targetRole} onChange={(e) => setTargetRole(e.target.value)} maxLength={200} disabled={busy} />
              </label>
              <CareerGeographyField value={geography} onChange={setGeography} disabled={busy} />
            </>
          ) : null}

          {step === 3 ? (
            <>
              <StepBody title={t("onboarding.coachingTitle")} body={t("onboarding.coachingBody")} />
              <CoachingStyleField value={coaching} onChange={setCoaching} disabled={busy} />
              <div className="border-t border-border pt-4">
                <h3 className="mb-2 text-sm font-semibold text-foreground">{t("onboarding.detailSectionTitle")}</h3>
                <ResponseDetailPreference />
              </div>
            </>
          ) : null}

          {step === 4 ? (
            <>
              <StepBody title={t("onboarding.languageTitle")} body={t("onboarding.languageBody")} />
              <LanguageSettings />
            </>
          ) : null}

          {step === 5 ? (
            <>
              <StepBody title={t("onboarding.privacyTitle")} />
              <ul className="grid gap-2 text-sm text-muted">
                <li>{t("onboarding.privacyMemory")}</li>
                <li>{t("onboarding.privacyDocuments")}</li>
                <li>{t("onboarding.privacyAudio")}</li>
                <li>{t("onboarding.privacyControl")}</li>
              </ul>
            </>
          ) : null}

          {step === 6 ? (
            <>
              <StepBody title={t("onboarding.reviewTitle")} body={t("onboarding.reviewBody")} />
              <dl className="grid gap-2 text-sm">
                <ReviewRow label={t("onboarding.rowName")} value={name || t("onboarding.notSet")} onEdit={() => setStep(1)} editLabel={t("onboarding.edit")} />
                <ReviewRow label={t("onboarding.rowTargetRole")} value={targetRole || t("onboarding.notSet")} onEdit={() => setStep(2)} editLabel={t("onboarding.edit")} />
                <ReviewRow label={t("onboarding.rowGeography")} value={t(geography ? `geography.${geography}` : "geography.unspecified")} onEdit={() => setStep(2)} editLabel={t("onboarding.edit")} />
                <ReviewRow label={t("onboarding.rowCoaching")} value={t(`coaching.${coaching}`)} onEdit={() => setStep(3)} editLabel={t("onboarding.edit")} />
                <ReviewRow label={t("onboarding.rowInterface")} value={account?.interface_locale ?? "en"} onEdit={() => setStep(4)} editLabel={t("onboarding.edit")} />
                <ReviewRow label={t("onboarding.rowConversation")} value={account?.conversation_language ?? "en"} onEdit={() => setStep(4)} editLabel={t("onboarding.edit")} />
              </dl>
            </>
          ) : null}

          {/* Recoverable completion error (announced via Alert's role="alert"). The candidate stays
              in onboarding with all choices saved and can retry "Enter Ask4Mo". */}
          {error ? <Alert tone="danger">{error}</Alert> : null}

          {/* Navigation. Welcome uses a single Get started; Review offers Enter Ask4Mo. */}
          <div className="flex items-center justify-between gap-2 pt-2">
            {step > 0 ? (
              <Button variant="ghost" onClick={goBack} disabled={busy}>{t("onboarding.back")}</Button>
            ) : <span />}
            {step === 0 ? (
              <Button onClick={goNext} disabled={busy} aria-busy={busy}>{t("onboarding.getStarted")}</Button>
            ) : step < TOTAL - 1 ? (
              <Button onClick={goNext} disabled={busy} aria-busy={busy}>{busy ? t("onboarding.saving") : t("onboarding.next")}</Button>
            ) : (
              <Button onClick={finish} disabled={busy} aria-busy={busy}>{busy ? t("onboarding.saving") : t("onboarding.finish")}</Button>
            )}
          </div>
        </CardBody>
      </Card>
    </section>
  );
}

function StepBody({ title, body }: { title: string; body?: string }) {
  return (
    <div>
      <h1 className="text-xl font-semibold text-foreground md:text-2xl">{title}</h1>
      {body ? <p className="mt-2 text-sm text-muted">{body}</p> : null}
    </div>
  );
}

function ReviewRow({ label, value, onEdit, editLabel }: { label: string; value: string; onEdit: () => void; editLabel: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border pb-2">
      <span className="min-w-0">
        <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
        <dd className="text-foreground">{value}</dd>
      </span>
      <button type="button" onClick={onEdit} className="shrink-0 text-sm font-medium text-accent hover:underline">
        {editLabel}
      </button>
    </div>
  );
}
