"use client";

import { useEffect, useState } from "react";

import { useT } from "@/components/i18n/I18nProvider";
import { MarketingIcon, type IconName } from "@/components/marketing/MarketingIcon";

const FACTS: {
  value: string;
  titleKey: string;
  bodyKey: string;
  icon: IconName;
  detailKeys: string[];
}[] = [
  {
    value: "7",
    titleKey: "marketing.systemTitle",
    bodyKey: "marketing.systemLead",
    icon: "target",
    detailKeys: ["workflow.opportunityTitle", "workflow.contextTitle", "workflow.evidenceTitle", "workflow.prepareTitle", "workflow.practiceTitle", "workflow.feedbackTitle", "workflow.progressTitle"],
  },
  {
    value: "1",
    titleKey: "marketing.featureOpportunityTitle",
    bodyKey: "marketing.featureOpportunityBody",
    icon: "search",
    detailKeys: ["marketing.howStep1Title", "marketing.howStep2Title", "marketing.howStep3Title"],
  },
  {
    value: "€0",
    titleKey: "marketing.planBasicName",
    bodyKey: "marketing.pricingBasicIncludes",
    icon: "check",
    detailKeys: ["marketing.featurePracticeTitle", "marketing.featureEvidenceTitle", "marketing.featureCompanyTitle"],
  },
  {
    value: "",
    titleKey: "marketing.trustStripPrivate",
    bodyKey: "marketing.why3Body",
    icon: "shield",
    detailKeys: ["marketing.trustStripSources", "marketing.trustStripControl", "marketing.why4Title"],
  },
];

const ROTATION_MS = 6500;

/** A compact, factual overview. It rotates until the visitor pauses or selects a fact. */
export function ProofCarousel() {
  const t = useT();
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);

  // Respect reduced motion: never auto-advance for visitors who ask for less motion (they can still select a fact).
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) setPaused(true);
  }, []);

  useEffect(() => {
    if (paused) return;
    const timer = window.setInterval(() => setActive((current) => (current + 1) % FACTS.length), ROTATION_MS);
    return () => window.clearInterval(timer);
  }, [paused]);

  const fact = FACTS[active];
  return (
    <section data-testid="proof-carousel" className="bg-[#183f42] text-white" aria-roledescription="carousel" aria-label={t("proofCarousel.label")}>
      <div className="mx-auto grid min-h-[15rem] max-w-content items-center gap-7 px-4 py-8 md:grid-cols-[10rem_1fr_auto] md:px-8">
        <div className="flex items-center gap-4 md:block" aria-hidden="true">
          <span className="grid h-14 w-14 place-items-center rounded-2xl bg-white/10 text-[#a8dbb8] md:h-16 md:w-16">
            <MarketingIcon name={fact.icon} className="h-7 w-7" />
          </span>
          {fact.value ? <span className="text-4xl font-bold tracking-tight md:mt-3 md:block md:text-5xl">{fact.value}</span> : null}
        </div>

        <div aria-live="polite" aria-atomic="true">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#a8dbb8]">
            {t("proofCarousel.label")} {active + 1}/{FACTS.length}
          </p>
          <h2 className="mt-2 max-w-3xl text-2xl font-bold leading-tight md:text-3xl">{t(fact.titleKey)}</h2>
          <p className="mt-3 max-w-3xl leading-relaxed text-white/80">{t(fact.bodyKey)}</p>
          <ul className="mt-4 flex flex-wrap gap-2" aria-label={t("proofCarousel.detailLabel")}>
            {fact.detailKeys.map((key) => (
              <li key={key} className="rounded-full border border-white/20 bg-white/[0.07] px-3 py-1 text-xs text-white/85">
                {t(key)}
              </li>
            ))}
          </ul>
        </div>

        <div className="flex items-center gap-2 md:flex-col md:items-end">
          <button
            type="button"
            onClick={() => setPaused((current) => !current)}
            className="rounded-full border border-white/25 px-3 py-2 text-xs font-semibold text-white hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-white"
          >
            {paused ? t("proofCarousel.resume") : t("proofCarousel.pause")}
          </button>
          <div className="flex gap-1.5">
            {FACTS.map((_, index) => (
              <button
                key={index}
                type="button"
                aria-label={t("proofCarousel.goTo", { n: index + 1, total: FACTS.length })}
                aria-current={index === active ? "true" : undefined}
                onClick={() => { setActive(index); setPaused(true); }}
                className={`h-2.5 w-2.5 rounded-full border border-white/70 focus:outline-none focus-visible:ring-2 focus-visible:ring-white ${index === active ? "bg-white" : "bg-transparent"}`}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
