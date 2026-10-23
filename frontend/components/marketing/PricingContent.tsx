"use client";

import { BetaPricingStatement } from "@/components/plan/BetaPricingStatement";
import { useT } from "@/components/i18n/I18nProvider";
import { ButtonLink } from "@/components/ui/Button";
import { MarketingIcon } from "@/components/marketing/MarketingIcon";
import { PlanOverview } from "@/components/plan/PlanOverview";
import { COACHING_COMPARISON, CONSIDERATION_ROWS, PRICE_BENCHMARK, PRICE_BENCHMARK_REVIEWED, PRICING_PLANS } from "@/lib/pricing";

const PACKAGE_FEATURES = {
  basic: [
    CONSIDERATION_ROWS[0],
    CONSIDERATION_ROWS[1],
    "marketing.featurePrepareTitle",
    "marketing.featurePracticeTitle",
    "gettingStarted.step5Title",
    "workflow.feedbackTitle",
    CONSIDERATION_ROWS[2],
    CONSIDERATION_ROWS[3],
  ],
  premium: CONSIDERATION_ROWS.slice(4),
} as const;

// Pricing presentation (Capstone P8 §6/§7). Premium selection begins with account creation;
// the payment provider completes the secure subscription step when billing is configured.
export function PricingContent() {
  const t = useT();
  return (
    <div className="mx-auto max-w-content px-4 py-12 md:py-16">
      <header className="relative overflow-hidden rounded-[2rem] bg-[#e9e2f0] px-6 py-14 text-center text-[#173f42] shadow-soft md:px-12 md:py-20">
        <span aria-hidden="true" className="absolute -right-16 -top-20 h-56 w-56 rounded-full bg-[#f4cdb9]" />
        <span aria-hidden="true" className="absolute -bottom-24 -left-20 h-64 w-64 rounded-full border-[3rem] border-[#d4e5df]" />
        <div className="relative">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#6f5687]">Ask4Mo</p>
        <h1 className="mx-auto mt-3 max-w-4xl text-4xl font-bold tracking-tight md:text-6xl">{t("marketing.pricingTitle")}</h1>
        <p className="mx-auto mt-4 max-w-2xl text-[#43595a]">{t("marketing.pricingSubtitle")}</p>
        <div className="mx-auto mt-7 flex max-w-2xl flex-wrap justify-center gap-2 text-xs font-semibold">
          {["marketing.trustStripPrivate", "marketing.trustStripSources", "marketing.trustStripControl"].map((key) => (
            <span key={key} className="rounded-full border border-[#173f42]/15 bg-white/65 px-3 py-1.5">{t(key)}</span>
          ))}
        </div>
        </div>
      </header>

      <section className="mt-12" data-testid="pricing-plans" aria-labelledby="package-preview-title">
        <div className="mx-auto max-w-3xl text-center">
          <p id="package-preview-title" className="inline-flex rounded-full border border-accent/25 bg-accent/5 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-accent">{t("pricingV4.considerLabel")}</p>
          <p className="mx-auto mt-4 max-w-2xl text-sm leading-relaxed text-muted">{t("pricingV4.considerLead")}</p>
        </div>

        <div className="mx-auto mt-6 grid max-w-5xl items-stretch gap-6 md:grid-cols-2">
        {PRICING_PLANS.map((plan) => (
          <div
            key={plan.id}
            className={`relative flex h-full flex-col overflow-hidden rounded-[2rem] border ${plan.featured ? "border-[#183f42] bg-[#183f42] text-white shadow-soft" : "border-border bg-surface"}`}
            data-testid={`plan-${plan.id}`}
          >
            {plan.featured ? <div className="absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-[#f4cdb9] via-[#a9d7cd] to-[#bca6cb]" /> : null}
            <div className="px-7 pb-6 pt-8 md:px-9 md:pt-10">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-xl font-semibold">{t(plan.nameKey)}</h2>
                <span className={plan.featured ? "grid h-12 w-12 place-items-center rounded-full bg-white/10 text-[#f4cdb9]" : "grid h-12 w-12 place-items-center rounded-full bg-accent/10 text-accent"}>
                  <MarketingIcon name={plan.featured ? "target" : "check"} className="h-5 w-5" />
                </span>
              </div>
              {plan.purchasable || plan.ctaKind === "register" ? (
                // 04D: no price on any candidate surface. Ask4Mo is a free, invitation-only private beta; Basic is simply free to use in it.
                <p className="mt-3">
                  <span className="text-3xl font-bold tracking-tight md:text-4xl" data-testid="beta-free">{t("betaPricing.freeInBeta")}</span>
                </p>
              ) : (
                // Premium (W12.4D-P3, 04D): not available, no price and no purchase path. The ONE beta statement says so in the same words everywhere.
                <div className="mt-3" data-testid="premium-status">
                  <p className="text-3xl font-bold tracking-tight md:text-4xl">{t("planUx.pricing_notAvailable")}</p>
                  <BetaPricingStatement className={plan.featured ? "mt-2 text-xs text-white/70" : "mt-2 text-xs text-muted"} testId="premium-beta-statement" />
                </div>
              )}
              {plan.featured ? <span className="mt-4 inline-flex rounded-full bg-[#f4cdb9] px-3 py-1 text-xs font-semibold text-[#173f42]">{t("pricingV4.colPremium")}</span> : null}
              <p className={plan.featured ? "mt-4 text-sm leading-relaxed text-white/70" : "mt-4 text-sm leading-relaxed text-muted"}>{t(plan.includesKey)}</p>
            </div>

            <div className="flex flex-1 flex-col px-7 pb-7 md:px-9 md:pb-9">
              <p className={plan.featured ? "border-t border-white/15 pt-5 text-xs font-semibold uppercase tracking-[0.14em] text-[#a9d7cd]" : "border-t border-border pt-5 text-xs font-semibold uppercase tracking-[0.14em] text-accent"}>{t("pricingV4.considerLabel")}</p>
              <ul className="mt-4 space-y-3 text-sm">
                {PACKAGE_FEATURES[plan.id].map((key) => (
                  <li key={key} className="flex items-start gap-2.5">
                    <MarketingIcon name="check" className={plan.featured ? "mt-0.5 h-4 w-4 shrink-0 text-[#a9d7cd]" : "mt-0.5 h-4 w-4 shrink-0 text-accent"} />
                    <span>{t(key)}</span>
                  </li>
                ))}
              </ul>

              <div className="mt-auto pt-7">
              {/* Both plans start with account creation; Premium continues into the secure purchase flow. */}
              {plan.ctaHref ? (
                <ButtonLink href={plan.ctaHref} variant={plan.featured ? "primary" : "ghost"} className="w-full justify-center">
                  {t(plan.ctaKey)}
                </ButtonLink>
              ) : (
                // Not a button and not a link: nothing can be clicked to start a payment, and the status is plain text.
                <p className="w-full rounded-lg border border-white/25 px-4 py-2.5 text-center text-sm font-semibold" data-testid={`plan-status-${plan.id}`}>{t(plan.ctaKey)}</p>
              )}
              {plan.noteKey ? (
                <p className={plan.featured ? "mt-3 text-xs text-white/55" : "mt-3 text-xs text-muted"} data-testid={`plan-note-${plan.id}`}>
                  {t(plan.noteKey)}
                </p>
              ) : null}
              </div>
            </div>
          </div>
        ))}
        </div>
      </section>

      <p className="mx-auto mt-8 max-w-2xl text-center text-sm text-foreground">
        {t("marketing.pricingAlwaysFree")}
      </p>
      <BetaPricingStatement className="mx-auto mt-2 max-w-2xl text-center text-sm text-muted" testId="pricing-billing-note" />

      <section className="mx-auto mt-10 max-w-3xl" aria-label={t("planUx.title")}>
        <PlanOverview />
      </section>

      <section className="mt-16" aria-labelledby="pricing-value-title">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Ask4Mo</p>
          <h2 id="pricing-value-title" className="mt-3 text-3xl font-bold md:text-5xl">{t("pricingV4.coachingTitle")}</h2>
          <p className="mx-auto mt-4 max-w-2xl text-muted">{t("pricingV4.coachingLead")}</p>
        </div>
        <ol className="mt-8 grid gap-4 md:grid-cols-3">
          {[1, 2, 3].map((n, index) => (
            <li key={n} className={index === 1 ? "rounded-[1.5rem] bg-[#e9e2f0] p-6 text-sm leading-relaxed text-[#43595a]" : "rounded-[1.5rem] border border-border bg-surface p-6 text-sm leading-relaxed text-muted shadow-sm"}>
              <span className="mb-6 grid h-10 w-10 place-items-center rounded-full bg-[#183f42] font-bold text-white">{n}</span>
              {t(`pricingV4.point${n}`)}
            </li>
          ))}
        </ol>
      </section>

      {/* v4: coaching-format comparison (neutral trade-offs). */}
      <section className="mx-auto mt-16 max-w-content" aria-labelledby="coaching-title">
        <h2 id="coaching-title" className="text-2xl font-bold md:text-3xl">{t("pricingV4.complements")}</h2>
        <div className="mt-4 overflow-x-auto rounded-[1.25rem] border border-border bg-surface shadow-sm">
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
                  <td className="bg-accent/5 px-4 py-3 font-medium">{t(a)}</td>
                  <td className="px-4 py-3 text-muted">{t(c)}</td>
                  <td className="px-4 py-3 text-muted">{t(k)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-sm font-medium text-foreground" data-testid="complements-note">{t("pricingV4.complements")}</p>
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
