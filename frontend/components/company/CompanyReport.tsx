"use client";

/**
 * Company Intelligence report (P10B Wave 5).
 *
 * Presentational only. Renders the governed report with a STRICT visual separation of claim kinds -
 * FACT (company/official source), REVIEW (third-party opinion; not integrated in Wave 5) and
 * MODEL_INFERENCE (an Ask4Mo suggestion, never a verified fact). Every fact links to its source;
 * provider status and limitations are shown honestly so a partial/unavailable result never looks
 * complete. All copy comes from the 7-locale catalogue (no hardcoded English, no emoji, no em dash).
 */

import type {
  CompanyClaim,
  CompanyClaimKind,
  CompanyIntelligenceReport,
  CompanyProviderState,
  CompanySourceRef,
} from "@/lib/api/types";
import { useI18n } from "@/components/i18n/I18nProvider";
import { Card, CardBody } from "@/components/ui/Card";
import { Disclosure } from "@/components/ui/Disclosure";

const KIND_STYLE: Record<CompanyClaimKind, string> = {
  fact: "border-success/50 text-success",
  review: "border-warning/60 text-warning",
  model_inference: "border-accent/50 text-accent",
};
const KIND_LABEL: Record<CompanyClaimKind, string> = {
  fact: "company.kindFact",
  review: "company.kindReview",
  model_inference: "company.kindInference",
};
const KIND_HINT: Record<CompanyClaimKind, string> = {
  fact: "company.kindFactHint",
  review: "company.kindReviewHint",
  model_inference: "company.kindInferenceHint",
};
const PROVIDER_LABEL: Record<CompanyProviderState, string> = {
  configured: "company.providerConfigured",
  unavailable: "company.providerUnavailable",
  disabled: "company.providerDisabled",
  partial: "company.providerPartial",
  failed: "company.providerFailed",
  stale: "company.providerStale",
  not_integrated: "company.providerNotIntegrated",
  live_unvalidated: "company.providerLiveUnvalidated",
};

export function CompanyReport({ report }: { report: CompanyIntelligenceReport }) {
  const { t } = useI18n();
  const sourceById = new Map(report.sources.map((s) => [s.id, s]));

  return (
    <div className="space-y-5">
      {report.status === "partial" ? (
        <p role="status" className="rounded border border-warning/50 bg-surface px-3 py-2 text-sm text-warning">
          {t("company.partialNotice")}
        </p>
      ) : null}
      {report.cache_hit ? (
        <p className="text-xs text-muted">{t("company.staleNotice")}</p>
      ) : null}

      {/* Snapshot */}
      <Card>
        <CardBody className="space-y-2">
          <h2 className="text-lg font-semibold text-foreground">{t("company.sectionSnapshot")}</h2>
          <p className="text-sm text-muted">
            {report.identity.confidence === "confirmed"
              ? t("company.identityConfirmed")
              : t("company.identityNeedsWebsite")}
          </p>
          {report.snapshot.description ? (
            <p className="text-foreground">{report.snapshot.description}</p>
          ) : null}
          <dl className="grid grid-cols-1 gap-1 text-sm sm:grid-cols-2">
            {report.snapshot.website ? (
              <Row label={t("company.websiteLabel")} value={report.snapshot.website} />
            ) : null}
            {report.identity.location ? (
              <Row label={t("company.locationLabel")} value={report.identity.location} />
            ) : null}
            {report.snapshot.retrieved_at ? (
              <Row label={t("company.retrieved")} value={formatDate(report.snapshot.retrieved_at)} />
            ) : null}
          </dl>
        </CardBody>
      </Card>

      <ClaimSection title={t("company.sectionBusiness")} claims={report.business_market} sources={sourceById} />
      <ClaimSection title={t("company.sectionDevelopments")} claims={report.recent_developments} sources={sourceById} />
      <ClaimSection title={t("company.sectionCulture")} claims={report.culture} sources={sourceById} />

      {/* Employee review signals - not integrated in Wave 5 (honest). */}
      <Card>
        <CardBody className="space-y-2">
          <h2 className="text-lg font-semibold text-foreground">{t("company.sectionReviews")}</h2>
          <p className="text-sm text-muted">{t("company.reviewsNotIntegrated")}</p>
          <ul className="flex flex-wrap gap-2 pt-1">
            {report.provider_statuses
              .filter((p) => ["glassdoor", "kununu", "google"].includes(p.key))
              .map((p) => (
                <li key={p.key}>
                  {p.external_url ? (
                    <a href={p.external_url} target="_blank" rel="noopener noreferrer nofollow"
                       className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-sm text-accent hover:bg-surface-2">
                      {p.label}
                      <span className="text-xs text-muted">({t("company.openSource")})</span>
                    </a>
                  ) : (
                    <span className="text-sm text-muted">{p.label}</span>
                  )}
                </li>
              ))}
          </ul>
        </CardBody>
      </Card>

      <ClaimSection title={t("company.sectionRoleRelevance")} claims={report.role_relevance} sources={sourceById} />

      {/* Interview preparation (all MODEL_INFERENCE). */}
      {report.interview_preparation.topics.length > 0
        || report.interview_preparation.questions_to_ask.length > 0
        || report.interview_preparation.clarify.length > 0 ? (
        <Card>
          <CardBody className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground">{t("company.sectionInterviewPrep")}</h2>
            <SubList title={t("company.topics")} claims={report.interview_preparation.topics} sources={sourceById} />
            <SubList title={t("company.questionsToAsk")} claims={report.interview_preparation.questions_to_ask} sources={sourceById} />
            <SubList title={t("company.clarify")} claims={report.interview_preparation.clarify} sources={sourceById} />
          </CardBody>
        </Card>
      ) : null}

      {/* Sources (progressive disclosure). */}
      {report.sources.length > 0 ? (
        <Card>
          <CardBody className="space-y-3">
            <h2 className="text-lg font-semibold text-foreground">{t("company.sectionSources")}</h2>
            <ul className="space-y-2">
              {report.sources.map((s) => (
                <SourceItem key={s.id} source={s} />
              ))}
            </ul>
          </CardBody>
        </Card>
      ) : null}

      {/* Provider status + limitations (progressive disclosure to avoid overload). */}
      <Card>
        <CardBody className="space-y-3">
          <Disclosure showLabel={t("company.sectionProviders")} hideLabel={t("company.sectionProviders")}>
            <ul className="space-y-1 text-sm">
              {report.provider_statuses.map((p) => (
                <li key={p.key} className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border pb-1">
                  <span className="text-foreground">{p.label}</span>
                  <span className="text-muted">
                    {t(PROVIDER_LABEL[p.state])}{p.detail ? ` - ${p.detail}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          </Disclosure>
          {report.limitations.length > 0 ? (
            <div>
              <h3 className="text-sm font-semibold text-foreground">{t("company.sectionLimitations")}</h3>
              <ul className="mt-1 list-disc pl-5 text-sm text-muted">
                {report.limitations.map((code) => (
                  <li key={code}>{limitationText(t, code)}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <p className="pt-1 text-xs text-muted">{t("company.disclaimer")}</p>
        </CardBody>
      </Card>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="text-muted">{label}:</dt>
      <dd className="min-w-0 break-words text-foreground">{value}</dd>
    </div>
  );
}

function KindTag({ kind }: { kind: CompanyClaimKind }) {
  const { t } = useI18n();
  return (
    <span
      title={t(KIND_HINT[kind])}
      className={`inline-block shrink-0 rounded border px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${KIND_STYLE[kind]}`}
    >
      {t(KIND_LABEL[kind])}
    </span>
  );
}

function ClaimRow({ claim, sources }: { claim: CompanyClaim; sources: Map<string, CompanySourceRef> }) {
  const refs = claim.source_ids.map((id) => sources.get(id)).filter(Boolean) as CompanySourceRef[];
  return (
    <li className="flex flex-col gap-1 border-b border-border pb-2 last:border-0 sm:flex-row sm:items-start sm:gap-3">
      <KindTag kind={claim.kind} />
      <div className="min-w-0">
        <p className="text-foreground">{claim.text}</p>
        {refs.length > 0 ? (
          <p className="mt-1 flex flex-wrap gap-2 text-xs text-muted">
            {refs.map((r) =>
              r.url ? (
                <a key={r.id} href={r.url} target="_blank" rel="noopener noreferrer nofollow" className="text-accent hover:underline">
                  {r.title}
                </a>
              ) : (
                <span key={r.id}>{r.title}</span>
              )
            )}
          </p>
        ) : null}
      </div>
    </li>
  );
}

function ClaimSection({ title, claims, sources }: {
  title: string; claims: CompanyClaim[]; sources: Map<string, CompanySourceRef>;
}) {
  if (claims.length === 0) return null;
  return (
    <Card>
      <CardBody className="space-y-2">
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        <ul className="space-y-2">
          {claims.map((c, i) => (
            <ClaimRow key={i} claim={c} sources={sources} />
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}

function SubList({ title, claims, sources }: {
  title: string; claims: CompanyClaim[]; sources: Map<string, CompanySourceRef>;
}) {
  if (claims.length === 0) return null;
  return (
    <div>
      <h3 className="mb-1 text-sm font-semibold text-foreground">{title}</h3>
      <ul className="space-y-2">
        {claims.map((c, i) => (
          <ClaimRow key={i} claim={c} sources={sources} />
        ))}
      </ul>
    </div>
  );
}

function SourceItem({ source }: { source: CompanySourceRef }) {
  const { t } = useI18n();
  return (
    <li className="flex flex-col gap-0.5 border-b border-border pb-2 last:border-0">
      <div className="flex flex-wrap items-baseline gap-2">
        {source.url ? (
          <a href={source.url} target="_blank" rel="noopener noreferrer nofollow" className="font-medium text-accent hover:underline">
            {source.title}
          </a>
        ) : (
          <span className="font-medium text-foreground">{source.title}</span>
        )}
        <span className="text-xs text-muted">
          {source.self_reported ? t("company.selfReported") : t("company.independent")}
        </span>
      </div>
      {source.retrieved_at ? (
        <span className="text-xs text-muted">{t("company.retrieved")}: {formatDate(source.retrieved_at)}</span>
      ) : null}
    </li>
  );
}

function limitationText(t: (k: string) => string, code: string): string {
  const map: Record<string, string> = {
    company_website_missing: "company.limCompanyWebsiteMissing",
    company_web_unavailable: "company.limCompanyWebUnavailable",
    no_company_evidence: "company.limNoCompanyEvidence",
    reviews_not_integrated: "company.limReviewsNotIntegrated",
    market_data_unvalidated: "company.limMarketDataUnvalidated",
  };
  return map[code] ? t(map[code]) : code;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toISOString().slice(0, 10);
}
