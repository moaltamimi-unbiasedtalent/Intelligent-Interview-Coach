"use client";

import Image from "next/image";

import { useT } from "@/components/i18n/I18nProvider";
import { ButtonLink } from "@/components/ui/Button";
import { MarketingIcon, type IconName } from "@/components/marketing/MarketingIcon";
import { WorkflowMap } from "@/components/marketing/WorkflowMap";

const FEATURES: [string, string, IconName][] = [
  ["marketing.featureOpportunityTitle", "marketing.featureOpportunityBody", "target"],
  ["marketing.featureCompanyTitle", "marketing.featureCompanyBody", "search"],
  ["marketing.featureEvidenceTitle", "marketing.featureEvidenceBody", "shield"],
  ["marketing.featurePrepareTitle", "marketing.featurePrepareBody", "chat"],
  ["marketing.featurePracticeTitle", "marketing.featurePracticeBody", "mic"],
  ["marketing.featureWorkspacesTitle", "marketing.featureWorkspacesBody", "users"],
];

const DIFFERENTIATORS = [
  ["marketing.why1Title", "marketing.why1Body"],
  ["marketing.why2Title", "marketing.why2Body"],
  ["marketing.why3Title", "marketing.why3Body"],
  ["marketing.why4Title", "marketing.why4Body"],
] as const;

// Product and How it works now form one page: product capabilities and differentiation first,
// followed by the interactive Opportunity workflow. Reuses the marketing i18n keys; no emoji.

export function ProductContent() {
  const t = useT();
  return (
    <div className="mx-auto max-w-content px-4 py-10 md:py-16">
      <section className="grid overflow-hidden rounded-[2rem] bg-[#f2ebe4] text-[#173f42] shadow-soft lg:grid-cols-[0.9fr_1.1fr]" aria-labelledby="product-title">
        <div className="flex flex-col justify-center p-7 md:p-12">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#6f5687]">{t("common.tagline")}</p>
          <h1 id="product-title" className="mt-4 text-4xl font-bold tracking-tight md:text-6xl">{t("marketing.systemTitle")}</h1>
          <p className="mt-5 max-w-xl text-lg leading-relaxed text-[#43595a]">{t("marketing.systemLead")}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <ButtonLink href="/register">{t("marketing.heroPrimary")}</ButtonLink>
            <ButtonLink href="#how-it-works" variant="ghost" className="!border-[#173f42]/20 !text-[#173f42] hover:!bg-white/60">{t("marketing.heroSecondary")}</ButtonLink>
          </div>
          <div className="mt-8 flex flex-wrap gap-2 text-xs font-semibold">
            {["marketing.trustStripPrivate", "marketing.trustStripSources", "marketing.trustStripControl"].map((key) => (
              <span key={key} className="rounded-full border border-[#173f42]/15 bg-white/65 px-3 py-1.5">{t(key)}</span>
            ))}
          </div>
        </div>

        <figure className="relative min-h-[30rem] overflow-hidden bg-[#183f42]">
          <Image
            src="/images/ask4mo/ask4mo-about-human-conversation.png"
            alt={t("about.imageAlt")}
            fill
            priority
            sizes="(max-width: 1024px) 100vw, 650px"
            className="object-cover object-center"
          />
          <div className="absolute inset-x-4 bottom-4 rounded-[1.4rem] border border-white/30 bg-white/90 p-4 text-[#173f42] shadow-xl backdrop-blur-md md:inset-x-6 md:bottom-6 md:p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="font-bold">{t("workflow.opportunityTitle")}</p>
              <span className="rounded-full bg-[#dbe9e4] px-2.5 py-1 text-xs font-semibold">{t("gettingStarted.workflowStep", { n: 4, total: 7 })}</span>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2 text-xs font-semibold">
              {["workflow.contextTitle", "workflow.evidenceTitle", "workflow.prepareTitle"].map((key) => (
                <span key={key} className="flex items-center gap-1.5 rounded-xl bg-[#f7f7f5] px-2 py-2">
                  <MarketingIcon name="check" className="h-3.5 w-3.5 shrink-0 text-[#1a5e63]" />
                  {t(key)}
                </span>
              ))}
            </div>
          </div>
        </figure>
      </section>

      <section className="mt-8 grid gap-4 md:grid-cols-3" aria-label={t("marketing.systemTitle")}>
        {FEATURES.slice(0, 3).map(([title, body, icon], index) => (
          <article key={title} className={index === 1 ? "rounded-[1.5rem] bg-[#e9e2f0] p-6 text-[#173f42]" : "rounded-[1.5rem] border border-border bg-surface p-6 shadow-sm"}>
            <span className="grid h-11 w-11 place-items-center rounded-full bg-accent/10 text-accent">
              <MarketingIcon name={icon} className="h-5 w-5" />
            </span>
            <h2 className="mt-5 text-xl font-bold">{t(title)}</h2>
            <p className={index === 1 ? "mt-2 text-sm leading-relaxed text-[#43595a]" : "mt-2 text-sm leading-relaxed text-muted"}>{t(body)}</p>
          </article>
        ))}
      </section>

      <section className="mt-16 overflow-hidden rounded-[2rem] bg-[#183f42] p-6 text-white md:p-10" aria-labelledby="product-capabilities-title">
        <div className="grid gap-8 lg:grid-cols-[0.75fr_1.25fr]">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#a9d7cd]">Ask4Mo</p>
            <h2 id="product-capabilities-title" className="mt-3 text-3xl font-bold md:text-5xl">{t("marketing.featuresTitle")}</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {FEATURES.slice(3).map(([title, body, icon], index) => (
              <article key={title} className={index === 0 ? "rounded-[1.5rem] bg-[#f4cdb9] p-6 text-[#173f42] sm:row-span-2" : "rounded-[1.5rem] bg-white/10 p-6"}>
                <MarketingIcon name={icon} className={index === 0 ? "h-7 w-7 text-[#173f42]" : "h-7 w-7 text-[#a9d7cd]"} />
                <h3 className="mt-8 text-xl font-bold">{t(title)}</h3>
                <p className={index === 0 ? "mt-3 text-sm leading-relaxed text-[#43595a]" : "mt-3 text-sm leading-relaxed text-white/70"}>{t(body)}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-16 overflow-hidden rounded-[2rem] bg-surface-2 p-6 md:p-10" aria-labelledby="product-difference-title">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent">Ask4Mo</p>
          <h2 id="product-difference-title" className="mt-3 text-3xl font-bold md:text-5xl">{t("marketing.whyTitle")}</h2>
        </div>
        <div className="mt-8 grid gap-4 md:grid-cols-2">
          {DIFFERENTIATORS.map(([title, body], index) => (
            <article key={title} className={index === 1 ? "rounded-[1.5rem] bg-[#e9e2f0] p-6 text-[#173f42]" : "rounded-[1.5rem] border border-border bg-surface p-6"}>
              <div className="flex gap-3">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-accent text-accent-foreground">
                  <MarketingIcon name="check" className="h-4 w-4" />
                </span>
                <div>
                  <h3 className="text-lg font-bold">{t(title)}</h3>
                  <p className={index === 1 ? "mt-2 text-sm leading-relaxed text-[#43595a]" : "mt-2 text-sm leading-relaxed text-muted"}>{t(body)}</p>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section id="how-it-works" className="mt-20 scroll-mt-32">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">{t("common.tagline")}</p>
          <h2 className="mt-2 text-3xl font-bold md:text-5xl">{t("marketing.howTitle")}</h2>
          <p className="mt-3 text-lg text-muted">{t("marketing.howLead")}</p>
        </div>
        <div className="mt-8"><WorkflowMap /></div>
      </section>

      <div className="mt-12 text-center">
        <ButtonLink href="/register">{t("marketing.heroPrimary")}</ButtonLink>
      </div>

    </div>
  );
}
