"use client";

/**
 * Create-opportunity wizard (P10B Wave 6): Role -> Company -> Job description -> Review.
 *
 * Deliberate and fast (about a minute when a JD already exists). Only the role is required;
 * everything else is optional. Reuses the governed DocumentPicker for the JD (no second uploader).
 * All copy localized; no emoji, no em dash.
 */

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { useI18n } from "@/components/i18n/I18nProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Input, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/Alert";
import { DocumentPicker } from "@/components/documents/DocumentPicker";

const STEPS = ["stepRole", "stepCompany", "stepJd", "stepReview"] as const;

export function OpportunityCreate({ onCancel, onCreated }: {
  onCancel: () => void;
  onCreated: (id: number) => void;
}) {
  const { t } = useI18n();
  const router = useRouter();

  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [role, setRole] = useState("");
  const [label, setLabel] = useState("");
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");
  const [country, setCountry] = useState("");
  const [website, setWebsite] = useState("");
  const [jdDocId, setJdDocId] = useState<number | null>(null);
  const [notes, setNotes] = useState("");

  const derivedTitle = useMemo(
    () => [role.trim(), company.trim(), location.trim()].filter(Boolean).join(" - ") || role.trim(),
    [role, company, location]);

  const canNext = step !== 0 || role.trim().length > 0;

  const submit = useCallback(async () => {
    if (busy || !role.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.opportunities.create({
        target_role: role.trim(),
        title: label.trim() || null,
        company_name: company.trim() || null,
        company_location: location.trim() || null,
        company_country: country.trim().toUpperCase() || null,
        company_domain: website.trim() || null,
        job_description_document_id: jdDocId,
        notes: notes.trim() || null,
      });
      router.prefetch?.(`/opportunities/${created.id}`);
      onCreated(created.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("opportunity.errorCreate"));
      setBusy(false);
    }
  }, [busy, role, label, company, location, country, website, jdDocId, notes, router, onCreated, t]);

  return (
    <section className="mx-auto max-w-content space-y-6">
      <PageHeader title={t("opportunity.createTitle")} />

      {/* Step indicator (accessible, text-based). */}
      <ol className="flex flex-wrap gap-2 text-sm" aria-label={t("opportunity.createTitle")}>
        {STEPS.map((key, i) => (
          <li key={key} aria-current={i === step ? "step" : undefined}
              className={`rounded border px-2 py-1 ${i === step ? "border-accent text-accent" : "border-border text-muted"}`}>
            {i + 1}. {t(`opportunity.${key}`)}
          </li>
        ))}
      </ol>

      <Card>
        <CardBody className="space-y-4">
          {step === 0 ? (
            <>
              <Field label={t("opportunity.roleLabel")} required>
                <Input value={role} onChange={(e) => setRole(e.target.value)} maxLength={200}
                       placeholder={t("opportunity.rolePlaceholder")} disabled={busy} autoFocus />
              </Field>
              <Field label={t("opportunity.labelLabel")} help={t("opportunity.labelHelp")}>
                <Input value={label} onChange={(e) => setLabel(e.target.value)} maxLength={200}
                       placeholder={t("opportunity.labelPlaceholder")} disabled={busy} />
              </Field>
            </>
          ) : null}

          {step === 1 ? (
            <>
              <Field label={t("opportunity.companyLabel")}>
                <Input value={company} onChange={(e) => setCompany(e.target.value)} maxLength={200}
                       placeholder={t("opportunity.companyPlaceholder")} disabled={busy} />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={t("opportunity.locationLabel")}>
                  <Input value={location} onChange={(e) => setLocation(e.target.value)} maxLength={200}
                         placeholder={t("opportunity.locationPlaceholder")} disabled={busy} />
                </Field>
                <Field label={t("opportunity.countryLabel")}>
                  <Input value={country} onChange={(e) => setCountry(e.target.value)} maxLength={2}
                         placeholder={t("opportunity.countryPlaceholder")} disabled={busy} />
                </Field>
              </div>
              <Field label={t("opportunity.websiteLabel")}>
                <Input value={website} onChange={(e) => setWebsite(e.target.value)} maxLength={500}
                       placeholder={t("opportunity.websitePlaceholder")} inputMode="url" disabled={busy} />
              </Field>
            </>
          ) : null}

          {step === 2 ? (
            <>
              <p className="text-sm text-muted">{t("opportunity.jdSkip")}</p>
              <DocumentPicker category="job_description" value={jdDocId} onChange={setJdDocId}
                              label={t("opportunity.jdSelect")} disabled={busy} />
              <Field label={t("opportunity.notesLabel")}>
                <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={4000}
                          placeholder={t("opportunity.notesPlaceholder")} disabled={busy}
                          className="min-h-[80px]" />
              </Field>
            </>
          ) : null}

          {step === 3 ? (
            <>
              <p className="text-sm text-muted">{t("opportunity.reviewIntro")}</p>
              <dl className="grid gap-2 text-sm">
                <ReviewRow label={t("opportunity.labelLabel")} value={label.trim() || derivedTitle} />
                <ReviewRow label={t("opportunity.roleLabel")} value={role.trim()} />
                {company.trim() ? <ReviewRow label={t("opportunity.companyLabel")} value={company.trim()} /> : null}
                {location.trim() ? <ReviewRow label={t("opportunity.locationLabel")} value={location.trim()} /> : null}
                {website.trim() ? <ReviewRow label={t("opportunity.websiteLabel")} value={website.trim()} /> : null}
                <ReviewRow label={t("opportunity.jdStatus")}
                           value={jdDocId ? t("opportunity.jdLinked") : t("opportunity.jdNone")} />
              </dl>
            </>
          ) : null}

          {error ? <Alert tone="danger">{error}</Alert> : null}

          <div className="flex items-center justify-between gap-2 pt-2">
            <Button variant="ghost" onClick={step === 0 ? onCancel : () => setStep((s) => s - 1)} disabled={busy}>
              {step === 0 ? t("opportunity.cancel") : t("opportunity.back")}
            </Button>
            {step < STEPS.length - 1 ? (
              <Button onClick={() => setStep((s) => s + 1)} disabled={!canNext || busy}>
                {t("opportunity.next")}
              </Button>
            ) : (
              <Button onClick={submit} disabled={busy || !role.trim()} aria-busy={busy}>
                {busy ? t("opportunity.creating") : t("opportunity.createButton")}
              </Button>
            )}
          </div>
        </CardBody>
      </Card>
    </section>
  );
}

function Field({ label, help, required, children }: {
  label: string; help?: string; required?: boolean; children: React.ReactNode;
}) {
  return (
    <label className="grid gap-1">
      <span className="text-sm font-medium text-foreground">
        {label}{required ? <span className="text-danger"> *</span> : null}
      </span>
      {help ? <span className="text-xs text-muted">{help}</span> : null}
      {children}
    </label>
  );
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2 border-b border-border pb-1">
      <dt className="text-muted">{label}:</dt>
      <dd className="min-w-0 break-words text-foreground">{value}</dd>
    </div>
  );
}
