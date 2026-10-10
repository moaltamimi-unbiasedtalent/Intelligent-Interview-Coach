"use client";

import { useT } from "@/components/i18n/I18nProvider";
import { ButtonLink } from "@/components/ui/Button";
import { AVAILABLE_TODAY, COACHING_COMPARISON, CONSIDERATION_ROWS, PRICE_BENCHMARK, PRICE_BENCHMARK_REVIEWED, PRICING_PLANS } from "@/lib/pricing";

// Pricing PRESENTATION only (Capstone P8 §6/§7). No checkout, no card fields, no "Buy now".
// Premium's CTA is a truthful preview request (there is no online purchase path).
export function PricingContent() {
  const t = useT();
  return (
    <div className="mx-auto max-w-content px-4 py-16">
      <h1 className="text-center text-3xl font-bold md:text-4xl">{t("marketing.pricingTitle")}</h1>
      <p className="mx-auto mt-3 max-w-2xl text-center text-muted">{t("marketing.pricingSubtitle")}</p>

      <div className="mx-auto mt-10 grid max-w-3xl gap-6 md:grid-cols-2">
        {PRICING_PLANS.map((plan) => (
          <div
            key={plan.id}
            className={`rounded-lg border p-6 ${plan.featured ? "border-accent shadow-soft" : "border-border"} bg-surface`}
            data-testid={`plan-${plan.id}`}
          >
            <h2 className="text-lg font-semibold">{t(plan.nameKey)}</h2>
            <p className="mt-2">
              <span className="text-3xl font-bold">{plan.priceDisplay}</span>{" "}
              <span className="text-sm text-muted">{t(plan.cadenceKey)}</span>
            </p>
            <p className="mt-3 text-sm text-muted">{t(plan.includesKey)}</p>
            <div className="mt-5">
              {/* Truthful CTA: Basic registers (a real free path); Premium requests a preview. */}
              <ButtonLink href={plan.ctaHref} variant={plan.featured ? "primary" : "ghost"}>
                {t(plan.ctaKey)}
              </ButtonLink>
            </div>
            {plan.noteKey ? (
              <p className="mt-3 text-xs text-muted" data-testid={`plan-note-${plan.id}`}>
                {t(plan.noteKey)}
              </p>
            ) : null}
          </div>
        ))}
      </div>

      <p className="mx-auto mt-8 max-w-2xl text-center text-sm text-foreground">
        {t("marketing.pricingAlwaysFree")}
      </p>
      <p className="mx-auto mt-2 max-w-2xl text-center text-xs text-muted" data-testid="no-billing-note">
        {t("marketing.pricingBillingNote")}
      </p>

      {/* v4: truthful "Available today" table, mirroring the backend entitlements. */}
      <section className="mx-auto mt-14 max-w-3xl" aria-labelledby="available-today-title">
        <h2 id="available-today-title" className="text-xl font-bold">{t("pricingV4.availableTitle")}</h2>
        <p className="mt-2 text-sm text-muted">{t("pricingV4.availableLead")}</p>
        <div className="mt-4 overflow-x-auto rounded-lg border border-border bg-surface">
          <table className="w-full min-w-[32rem] text-left text-sm" data-testid="available-today">
            <thead className="bg-surface-2 text-xs uppercase tracking-wide text-muted">
              <tr>
                <th scope="col" className="px-4 py-3">{t("pricingV4.colFeature")}</th>
                <th scope="col" className="px-4 py-3">{t("pricingV4.colBasic")}</th>
                <th scope="col" className="px-4 py-3">{t("pricingV4.colPremium")}</th>
              </tr>
            </thead>
            <tbody>
              {AVAILABLE_TODAY.map((row) => (
                <tr key={row.key} className="border-t border-border" data-entitlement={row.key}>
                  <th scope="row" className="px-4 py-3 font-medium">{t(row.labelKey)}</th>
                  <td className="px-4 py-3">{row.basic ? t("pricingV4.included") : t("pricingV4.notIncluded")}</td>
                  <td className="px-4 py-3">{row.preview ? t("pricingV4.previewOnly") : row.premium ? t("pricingV4.included") : t("pricingV4.notIncluded")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-muted">{t("pricingV4.tableNote")}</p>
      </section>

      {/* v4: proposed package ideas, visibly labelled and not part of any plan today. */}
      <section className="mx-auto mt-10 max-w-3xl rounded-lg border border-dashed border-border bg-surface-2 p-5" aria-labelledby="consider-title" data-testid="under-consideration">
        <h2 id="consider-title" className="flex flex-wrap items-center gap-2 text-lg font-bold">
          {t("pricingV4.considerTitle")}
          <span className="rounded-full border border-border bg-surface px-2 py-0.5 text-xs font-semibold">{t("pricingV4.considerLabel")}</span>
        </h2>
        <p className="mt-2 text-sm text-muted">{t("pricingV4.considerLead")}</p>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted">
          {CONSIDERATION_ROWS.map((k) => <li key={k}>{t(k)}</li>)}
        </ul>
      </section>

      {/* v4: coaching-format comparison (neutral trade-offs). */}
      <section className="mx-auto mt-14 max-w-content" aria-labelledby="coaching-title">
        <h2 id="coaching-title" className="text-xl font-bold">{t("pricingV4.coachingTitle")}</h2>
        <p className="mt-2 max-w-3xl text-sm text-muted">{t("pricingV4.coachingLead")}</p>
        <div className="mt-4 overflow-x-auto rounded-lg border border-border bg-surface">
          <table className="w-full min-w-[44rem] text-left text-sm" data-testid="coaching-comparison">
            <thead className="bg-surface-2 text-xs uppercase tracking-wide text-muted">
              <tr>
                <td className="px-4 py-3" />
                <th scope="col" className="px-4 py-3">{t("pricingV4.colAsk4mo")}</th>
                <th scope="col" className="px-4 py-3">{t("pricingV4.colCoach")}</th>
                <th scope="col" className="px-4 py-3">{t("pricingV4.colCourse")}</th>
              </tr>
            </thead>
            <tbody>
              {COACHING_COMPARISON.map(([row, a, c, k]) => (
                <tr key={row} className="border-t border-border align-top">
                  <th scope="row" className="px-4 py-3 font-medium">{t(row)}</th>
                  <td className="px-4 py-3">{t(a)}</td>
                  <td className="px-4 py-3 text-muted">{t(c)}</td>
                  <td className="px-4 py-3 text-muted">{t(k)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-sm font-medium text-foreground" data-testid="complements-note">{t("pricingV4.complements")}</p>
        <ol className="mt-4 grid gap-3 md:grid-cols-3">
          {[1, 2, 3].map((n) => <li key={n} className="rounded-lg border border-border bg-surface p-4 text-sm text-muted">{t(`pricingV4.point${n}`)}</li>)}
        </ol>
      </section>

      {/* v4: dated public-price benchmark with methodology. Indicative, original currencies, no conversion, no savings claim. */}
      <section className="mx-auto mt-14 max-w-content" aria-labelledby="benchmark-title" data-testid="price-benchmark">
        <h2 id="benchmark-title" className="text-xl font-bold">{t("pricingV4.benchmarkTitle")}</h2>
        <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-muted"><time dateTime={PRICE_BENCHMARK_REVIEWED}>{t("pricingV4.benchmarkDate")}</time></p>
        <p className="mt-3 max-w-3xl text-sm text-muted">{t("pricingV4.benchmarkLead")}</p>
        <p className="mt-2 text-xs text-muted">{t("pricingV4.benchmarkNoConvert")}</p>
        <details className="mt-4 rounded-lg border border-border bg-surface">
          <summary className="cursor-pointer px-4 py-3 text-sm font-semibold">{t("pricingV4.benchmarkSourcesTitle")}</summary>
          <div className="border-t border-border p-4">
            <p className="text-sm text-muted">{t("pricingV4.benchmarkMethod")}</p>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[40rem] text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-muted">
                  <tr>
                    <th scope="col" className="py-2 pr-4">{t("pricingV4.benchmarkColProvider")}</th>
                    <th scope="col" className="py-2 pr-4">{t("pricingV4.benchmarkColPrice")}</th>
                    <th scope="col" className="py-2">{t("pricingV4.benchmarkColNote")}</th>
                  </tr>
                </thead>
                <tbody>
                  {PRICE_BENCHMARK.map((b) => (
                    <tr key={b.provider} className="border-t border-border align-top">
                      <th scope="row" className="py-2 pr-4 font-medium">
                        <a href={b.url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">{b.provider}</a>
                      </th>
                      <td className="py-2 pr-4">{b.price}</td>
                      <td className="py-2 text-muted">{b.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </details>
      </section>
    </div>
  );
}
