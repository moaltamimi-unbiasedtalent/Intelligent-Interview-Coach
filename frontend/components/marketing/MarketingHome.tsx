"use client";

import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import { BetaPricingStatement } from "@/components/plan/BetaPricingStatement";
import { useT } from "@/components/i18n/I18nProvider";
import { ButtonLink } from "@/components/ui/Button";
import { MarketingIcon } from "@/components/marketing/MarketingIcon";
import { CandidateStory } from "@/components/marketing/CandidateStory";
import { ProofCarousel } from "@/components/marketing/ProofCarousel";
import { ResearchEvidence } from "@/components/marketing/ResearchEvidence";

// P10B Wave 7: the public story is centred on the Opportunity (Wave 6) - one job, everything
// together - not a generic interview-question generator. Icons are restrained inline SVGs
// (never emoji). All copy is localized; no em dash (guarded).

export function MarketingHome() {
  const t = useT();
  return (
    <div>
      {/* Hero */}
      <section className="mx-auto max-w-content px-4 py-10 md:py-16">
        <div className="grid overflow-hidden rounded-[2rem] bg-[#f2ebe4] text-[#173f42] shadow-soft lg:grid-cols-[0.88fr_1.12fr]">
          <div className="flex flex-col justify-center p-7 text-left md:p-12">
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[#6f5687]">{t("common.tagline")}</p>
            <h1 className="mt-4 max-w-3xl text-4xl font-bold tracking-tight md:text-6xl lg:text-7xl">
              {t("marketing.heroTitle")}
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-[#43595a]">{t("marketing.heroSubtitle")}</p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <ButtonLink href="/register">{t("marketing.heroPrimary")}</ButtonLink>
              <Link href="/product" className="text-sm font-semibold text-[#173f42] hover:underline">
                {t("marketing.heroSecondary")} &rarr;
              </Link>
            </div>
            <p className="mt-4 text-xs text-[#5f6667]">{t("marketing.heroNote")}</p>
          </div>
          {/* Documentary hero. The tighter editorial crop creates a human focal point while keeping
              enough of the candidate's preparation environment visible. */}
          <figure className="overflow-hidden">
            <div className="relative min-h-[26rem] w-full md:min-h-[38rem]">
            <Image
              src="/images/ask4mo/ask4mo-home-hero-documentary.png"
              alt={t("marketing.heroImageAlt")}
              fill
              priority
              sizes="(max-width: 1024px) 100vw, 640px"
              className="object-cover object-[66%_50%]"
            />
            </div>
          </figure>
          </div>
      </section>

      <ProofCarousel />

      <ResearchEvidence />

      {/* v4: static candidate story + workflow entry. Fictional candidate, AI-generated stills, no video, not customer proof. */}
      <section className="mx-auto max-w-content px-4 py-14" aria-labelledby="home-story-title">
        <h2 id="home-story-title" className="text-center text-2xl font-bold md:text-3xl">{t("homeStory.title")}</h2>
        <p className="mx-auto mt-3 max-w-2xl text-center text-muted">{t("homeStory.lead")}</p>
        <div className="mt-8"><CandidateStory compact /></div>
        <p className="mt-6 text-center">
          <Link href="/product#how-it-works" className="text-sm font-semibold text-accent hover:underline">{t("homeStory.cta")} &rarr;</Link>
        </p>
      </section>

      <section className="mx-auto max-w-content px-4 py-8" aria-label={t("about.founderName")}>
        <figure className="rounded-[2rem] bg-[#e9e2f0] px-7 py-10 text-[#173f42] md:px-12 md:py-14">
          <blockquote className="max-w-5xl text-2xl font-semibold leading-snug tracking-tight md:text-4xl">
            “{t("about.founderHomeQuote")}”
          </blockquote>
          <figcaption className="mt-7 text-sm font-semibold text-[#43595a]">
            {t("about.founderHomeAttribution")}
          </figcaption>
        </figure>
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
          <div className="rounded-[1.5rem] bg-[#f4cdb9] p-7 text-[#173f42]">
            <h2 className="text-xl font-bold">{t("marketing.problemTitle")}</h2>
            <p className="mt-3 text-[#43595a]">{t("marketing.problemBody")}</p>
          </div>
          <div className="rounded-[1.5rem] bg-[#183f42] p-7 text-white">
            <h2 className="text-xl font-bold">{t("marketing.problemResolveTitle")}</h2>
            <p className="mt-3 text-white/70">{t("marketing.problemResolveBody")}</p>
          </div>
        </div>
        {/* Wave 8 B0: overhead still life of scattered materials organised into one folder. Shown in
            full (object-contain, no crop) so both the scattered and organised sides stay visible. */}
        <figure className="mx-auto mt-8 max-w-[960px] overflow-hidden rounded-[1.75rem] border border-border shadow-sm">
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

      {/* Trust + pricing teasers */}
      <section className="mx-auto max-w-content px-4 py-16">
        <div className="grid gap-6 md:grid-cols-2">
          <div className="rounded-[1.5rem] border border-border bg-surface p-7 shadow-sm">
            <h2 className="text-xl font-bold">{t("marketing.trustTitle")}</h2>
            <p className="mt-2 text-muted">{t("marketing.trustSubtitle")}</p>
            <Link href="/trust" className="mt-4 inline-block text-sm font-semibold text-accent hover:underline">
              {t("marketing.navTrust")} &rarr;
            </Link>
          </div>
          <div className="rounded-[1.5rem] bg-[#e9e2f0] p-7 text-[#173f42]">
            <h2 className="text-xl font-bold">{t("marketing.homePricingTitle")}</h2>
            <BetaPricingStatement className="mt-2 text-[#43595a]" testId="home-beta-pricing" />
            <Link href="/pricing" className="mt-4 inline-block text-sm font-semibold text-[#173f42] hover:underline">
              {t("marketing.homePricingCta")} &rarr;
            </Link>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="mx-auto max-w-content px-4 pb-4 pt-10">
        <div className="rounded-[2rem] bg-[#183f42] px-6 py-16 text-center text-white md:px-12">
          <h2 className="text-2xl font-bold md:text-3xl">{t("marketing.ctaTitle")}</h2>
          <p className="mx-auto mt-2 max-w-xl text-white/70">{t("marketing.ctaBody")}</p>
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
