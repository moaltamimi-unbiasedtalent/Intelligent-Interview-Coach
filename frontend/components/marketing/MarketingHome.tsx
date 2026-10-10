"use client";

import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import { useT } from "@/components/i18n/I18nProvider";
import { ButtonLink } from "@/components/ui/Button";
import { MarketingIcon, type IconName } from "@/components/marketing/MarketingIcon";
import { CandidateStory } from "@/components/marketing/CandidateStory";

// P10B Wave 7: the public story is centred on the Opportunity (Wave 6) - one job, everything
// together - not a generic interview-question generator. Icons are restrained inline SVGs
// (never emoji). All copy is localized; no em dash (guarded).

// One connected system, per Opportunity. Icons are decorative (aria-hidden); text carries meaning.
const SYSTEM: [string, string, IconName][] = [
  ["marketing.featureOpportunityTitle", "marketing.featureOpportunityBody", "target"],
  ["marketing.featureCompanyTitle", "marketing.featureCompanyBody", "search"],
  ["marketing.featureEvidenceTitle", "marketing.featureEvidenceBody", "shield"],
  ["marketing.featurePrepareTitle", "marketing.featurePrepareBody", "chat"],
  ["marketing.featurePracticeTitle", "marketing.featurePracticeBody", "mic"],
  ["marketing.featureWorkspacesTitle", "marketing.featureWorkspacesBody", "users"],
];

const STEPS = [
  ["marketing.howStep1Title", "marketing.howStep1Body"],
  ["marketing.howStep2Title", "marketing.howStep2Body"],
  ["marketing.howStep3Title", "marketing.howStep3Body"],
  ["marketing.howStep4Title", "marketing.howStep4Body"],
  ["marketing.howStep5Title", "marketing.howStep5Body"],
  ["marketing.howStep6Title", "marketing.howStep6Body"],
] as const;

const WHY = [
  ["marketing.why1Title", "marketing.why1Body"],
  ["marketing.why2Title", "marketing.why2Body"],
  ["marketing.why3Title", "marketing.why3Body"],
  ["marketing.why4Title", "marketing.why4Body"],
] as const;

export function MarketingHome() {
  const t = useT();
  return (
    <div>
      {/* Hero */}
      <section className="mx-auto max-w-content px-4 py-16 text-center md:py-24">
        <p className="text-sm font-semibold uppercase tracking-wide text-accent">{t("common.tagline")}</p>
        <h1 className="mx-auto mt-3 max-w-3xl text-3xl font-bold tracking-tight md:text-5xl">
          {t("marketing.heroTitle")}
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-muted">{t("marketing.heroSubtitle")}</p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <ButtonLink href="/register">{t("marketing.heroPrimary")}</ButtonLink>
          <Link href="/product" className="text-sm font-medium text-foreground hover:underline">
            {t("marketing.heroSecondary")} &rarr;
          </Link>
        </div>
        <p className="mt-4 text-xs text-muted">{t("marketing.heroNote")}</p>
        {/* Wave 8 B0: documentary hero. Full width on desktop (natural 1840x854); a deliberate
            mobile crop keeps the subject, notes and folio (never the face/hands) via object-position. */}
        <figure className="mx-auto mt-10 overflow-hidden rounded-lg border border-border">
          <div className="relative aspect-[3/2] w-full sm:aspect-[1840/854]">
            <Image
              src="/images/ask4mo/ask4mo-home-hero-documentary.png"
              alt={t("marketing.heroImageAlt")}
              fill
              priority
              sizes="(max-width: 1024px) 100vw, 1152px"
              className="object-cover object-[72%_50%] sm:object-center"
            />
          </div>
        </figure>
      </section>

      {/* v4: static candidate story + workflow entry. Fictional candidate, AI-generated stills, no video, not customer proof. */}
      <section className="mx-auto max-w-content px-4 py-14" aria-labelledby="home-story-title">
        <h2 id="home-story-title" className="text-center text-2xl font-bold md:text-3xl">{t("homeStory.title")}</h2>
        <p className="mx-auto mt-3 max-w-2xl text-center text-muted">{t("homeStory.lead")}</p>
        <div className="mt-8"><CandidateStory compact /></div>
        <p className="mt-6 text-center">
          <Link href="/getting-started" className="text-sm font-semibold text-accent hover:underline">{t("homeStory.cta")} &rarr;</Link>
        </p>
      </section>

      {/* Trust strip */}
      <section className="border-y border-border bg-surface-2">
        <div className="mx-auto flex max-w-content flex-wrap items-center justify-center gap-x-8 gap-y-2 px-4 py-6 text-sm text-muted">
          <span className="font-semibold text-foreground">{t("marketing.trustStripTitle")}:</span>
          <TrustItem>{t("marketing.trustStripPrivate")}</TrustItem>
          <TrustItem>{t("marketing.trustStripSources")}</TrustItem>
          <TrustItem>{t("marketing.trustStripControl")}</TrustItem>
        </div>
      </section>

      {/* The candidate problem -> Opportunity resolves it */}
      <section className="mx-auto max-w-content px-4 py-16">
        <div className="grid gap-6 md:grid-cols-2">
          <div className="rounded-lg border border-border bg-surface p-6">
            <h2 className="text-xl font-bold">{t("marketing.problemTitle")}</h2>
            <p className="mt-3 text-muted">{t("marketing.problemBody")}</p>
          </div>
          <div className="rounded-lg border border-accent/40 bg-surface p-6">
            <h2 className="text-xl font-bold">{t("marketing.problemResolveTitle")}</h2>
            <p className="mt-3 text-muted">{t("marketing.problemResolveBody")}</p>
          </div>
        </div>
        {/* Wave 8 B0: overhead still life of scattered materials organised into one folder. Shown in
            full (object-contain, no crop) so both the scattered and organised sides stay visible. */}
        <figure className="mx-auto mt-8 max-w-[960px] overflow-hidden rounded-lg border border-border">
          <Image
            src="/images/ask4mo/ask4mo-home-preparation-still-life.png"
            alt={t("marketing.problemImageAlt")}
            width={1536}
            height={1024}
            sizes="(max-width: 960px) 100vw, 960px"
            className="h-auto w-full"
          />
        </figure>
      </section>

      {/* One connected system, per Opportunity */}
      <section className="border-t border-border bg-surface-2">
        <div className="mx-auto max-w-content px-4 py-16">
          <h2 className="text-center text-2xl font-bold md:text-3xl">{t("marketing.systemTitle")}</h2>
          <p className="mx-auto mt-3 max-w-2xl text-center text-muted">{t("marketing.systemLead")}</p>
          <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {SYSTEM.map(([title, body, icon]) => (
              <div key={title} className="rounded-lg border border-border bg-surface p-5">
                <MarketingIcon name={icon} className="h-6 w-6 text-accent" />
                <h3 className="mt-3 font-semibold">{t(title)}</h3>
                <p className="mt-1 text-sm text-muted">{t(body)}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works - the Opportunity journey */}
      <section className="mx-auto max-w-content px-4 py-16">
        <h2 className="text-center text-2xl font-bold md:text-3xl">{t("marketing.howTitle")}</h2>
        <p className="mx-auto mt-3 max-w-2xl text-center text-muted">{t("marketing.howLead")}</p>
        <ol className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map(([title, body], i) => (
            <li key={title} className="rounded-lg border border-border bg-surface p-5">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-sm font-bold text-accent-foreground">
                {i + 1}
              </div>
              <h3 className="mt-3 font-semibold">{t(title)}</h3>
              <p className="mt-1 text-sm text-muted">{t(body)}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Why Ask4Mo is different */}
      <section className="border-t border-border bg-surface-2">
        <div className="mx-auto max-w-content px-4 py-16">
          <h2 className="text-center text-2xl font-bold md:text-3xl">{t("marketing.whyTitle")}</h2>
          <div className="mt-10 grid gap-6 md:grid-cols-2">
            {WHY.map(([title, body]) => (
              <div key={title} className="flex gap-3 rounded-lg border border-border bg-surface p-5">
                <MarketingIcon name="check" className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
                <div>
                  <h3 className="font-semibold">{t(title)}</h3>
                  <p className="mt-1 text-sm text-muted">{t(body)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Trust + pricing teasers */}
      <section className="mx-auto max-w-content px-4 py-16">
        <div className="grid gap-6 md:grid-cols-2">
          <div className="rounded-lg border border-border bg-surface p-6">
            <h2 className="text-xl font-bold">{t("marketing.trustTitle")}</h2>
            <p className="mt-2 text-muted">{t("marketing.trustSubtitle")}</p>
            <Link href="/trust" className="mt-4 inline-block text-sm font-semibold text-accent hover:underline">
              {t("marketing.navTrust")} &rarr;
            </Link>
          </div>
          <div className="rounded-lg border border-border bg-surface p-6">
            <h2 className="text-xl font-bold">{t("marketing.homePricingTitle")}</h2>
            <p className="mt-2 text-muted">{t("marketing.homePricingBody")}</p>
            <Link href="/pricing" className="mt-4 inline-block text-sm font-semibold text-accent hover:underline">
              {t("marketing.homePricingCta")} &rarr;
            </Link>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="border-t border-border bg-surface-2">
        <div className="mx-auto max-w-content px-4 py-16 text-center">
          <h2 className="text-2xl font-bold md:text-3xl">{t("marketing.ctaTitle")}</h2>
          <p className="mx-auto mt-2 max-w-xl text-muted">{t("marketing.ctaBody")}</p>
          <div className="mt-6">
            <ButtonLink href="/register">{t("marketing.ctaButton")}</ButtonLink>
          </div>
        </div>
      </section>
    </div>
  );
}

function TrustItem({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <MarketingIcon name="check" className="h-4 w-4 text-accent" />
      {children}
    </span>
  );
}
