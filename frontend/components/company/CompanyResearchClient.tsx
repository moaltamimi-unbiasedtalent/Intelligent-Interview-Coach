"use client";

/**
 * Company Intelligence - directable candidate experience (P10B Wave 5).
 *
 * A candidate enters a company (and, ideally, its official website) and deliberately requests
 * research. The server enforces capability + operator pause + per-user cost and resolves any
 * selected JD owner-scoped. This component owns only the form, the request lifecycle and the
 * empty/loading/error/result states; the report rendering (with FACT/REVIEW/MODEL_INFERENCE
 * separation) lives in CompanyReport. All copy is localized; no emoji, no em dash.
 */

import { useCallback, useState } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { CompanyIntelligenceReport } from "@/lib/api/types";
import { useI18n } from "@/components/i18n/I18nProvider";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { DocumentPicker } from "@/components/documents/DocumentPicker";
import { CompanyReport } from "@/components/company/CompanyReport";

export function CompanyResearchClient() {
  const { t } = useI18n();

  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [country, setCountry] = useState("");
  const [website, setWebsite] = useState("");
  const [role, setRole] = useState("");
  const [jdDocId, setJdDocId] = useState<number | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; requestId?: string | null } | null>(null);
  const [report, setReport] = useState<CompanyIntelligenceReport | null>(null);

  const canSubmit = name.trim().length > 0 && !busy;

  const submit = useCallback(async () => {
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.company.research({
        company_name: name.trim(),
        location: location.trim() || null,
        country: country.trim().toUpperCase() || null,
        website: website.trim() || null,
        target_role: role.trim() || null,
        job_description_document_id: jdDocId,
      });
      setReport(result);
    } catch (err) {
      // Surface a safe, localized message only (never a raw provider error).
      const message = err instanceof ApiError ? err.message : t("company.errorBody");
      const requestId = err instanceof ApiError ? err.requestId : null;
      setError({ message: message || t("company.errorBody"), requestId });
    } finally {
      setBusy(false);
    }
  }, [name, location, country, website, role, jdDocId, busy, t]);

  const reset = useCallback(() => {
    setReport(null);
    setError(null);
  }, []);

  return (
    <section className="mx-auto max-w-content space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-foreground">{t("company.title")}</h1>
        <p className="max-w-reading text-muted">{t("company.subtitle")}</p>
      </header>

      <Card>
        <CardBody className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-foreground">{t("company.discoverTitle")}</h2>
            <p className="mt-1 text-sm text-muted">{t("company.discoverBody")}</p>
          </div>

          <form
            className="grid gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
          >
            <Field label={t("company.nameLabel")} required>
              <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={200}
                     placeholder={t("company.namePlaceholder")} disabled={busy} autoFocus />
            </Field>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("company.locationLabel")}>
                <Input value={location} onChange={(e) => setLocation(e.target.value)} maxLength={200}
                       placeholder={t("company.locationPlaceholder")} disabled={busy} />
              </Field>
              <Field label={t("company.countryLabel")}>
                <Input value={country} onChange={(e) => setCountry(e.target.value)} maxLength={2}
                       placeholder={t("company.countryPlaceholder")} disabled={busy} />
              </Field>
            </div>

            <Field label={t("company.websiteLabel")} help={t("company.websiteHelp")}>
              <Input value={website} onChange={(e) => setWebsite(e.target.value)} maxLength={500}
                     placeholder={t("company.websitePlaceholder")} inputMode="url" disabled={busy} />
            </Field>

            <Field label={t("company.roleLabel")}>
              <Input value={role} onChange={(e) => setRole(e.target.value)} maxLength={200}
                     placeholder={t("company.rolePlaceholder")} disabled={busy} />
            </Field>

            <DocumentPicker category="job_description" value={jdDocId} onChange={setJdDocId}
                            label={t("company.jdLabel")} disabled={busy} />

            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" disabled={!canSubmit} aria-busy={busy}>
                {busy ? t("company.researching") : t("company.research")}
              </Button>
              {report || error ? (
                <Button type="button" variant="ghost" onClick={reset} disabled={busy}>
                  {t("company.reset")}
                </Button>
              ) : null}
            </div>
          </form>
        </CardBody>
      </Card>

      {/* Result region: empty / loading / error / report. */}
      <div aria-live="polite">
        {busy ? (
          <LoadingState label={t("company.loadingTitle")} />
        ) : error ? (
          <ErrorState message={error.message} requestId={error.requestId} onRetry={() => void submit()} />
        ) : report ? (
          report.status === "needs_clarification" ? (
            <>
              <EmptyState title={t("company.needsWebsiteTitle")} description={t("company.needsWebsiteBody")} />
              <div className="mt-4">
                <CompanyReport report={report} />
              </div>
            </>
          ) : (
            <CompanyReport report={report} />
          )
        ) : (
          <EmptyState title={t("company.emptyTitle")} description={t("company.emptyBody")} />
        )}
      </div>
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
