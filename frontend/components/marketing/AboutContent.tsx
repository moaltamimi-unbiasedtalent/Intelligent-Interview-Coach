"use client";

import Image from "next/image";

import { useT } from "@/components/i18n/I18nProvider";
import { ButtonLink } from "@/components/ui/Button";

export function AboutContent() {
  const t = useT();
  return (
    <div className="mx-auto max-w-content px-4 py-12 md:py-16">
      <header className="mx-auto max-w-3xl text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent">{t("common.tagline")}</p>
        <h1 className="mt-3 text-4xl font-bold tracking-tight md:text-6xl">{t("about.pageTitle")}</h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg leading-relaxed text-muted">{t("about.lead")}</p>
      </header>

      <section className="mt-12 grid overflow-hidden rounded-[2rem] bg-[#183f42] text-white shadow-soft md:grid-cols-[0.72fr_1.28fr]" aria-labelledby="founder-title">
        {/* Approved founder portrait (supplied by Mo; local copy, never hotlinked). 4:5 crop; the face stays in the upper part of the frame
            (object-top), so the mobile and desktop crops keep it safely in view in both themes. Shown here only. */}
        <div className="relative aspect-[4/5] max-h-[34rem] w-full overflow-hidden bg-[#102f31] md:aspect-auto md:max-h-none md:min-h-[38rem]">
          <Image
            src="/images/ask4mo/mo-al-tamimi-founder-portrait.jpg"
            alt={t("about.founderPortraitAlt")}
            fill
            sizes="(max-width: 768px) 100vw, 420px"
            className="object-cover object-top"
          />
        </div>
        <div className="flex flex-col justify-center p-7 md:p-10 lg:p-12">
          <p className="text-sm font-semibold uppercase tracking-[0.14em] text-[#a9d7cd]">{t("about.founderEyebrow")}</p>
          <h2 id="founder-title" className="mt-2 text-3xl font-bold md:text-4xl">{t("about.founderName")}</h2>
          <p className="mt-2 max-w-2xl font-semibold text-[#f4cdb9]">{t("about.founderRole")}</p>
          <p className="mt-6 leading-relaxed text-white/75">{t("about.founderBio")}</p>
          <p className="mt-4 leading-relaxed text-white"><strong>{t("about.founderWhy")}</strong></p>
          <p className="mt-4 leading-relaxed text-white/75">{t("about.founderApproach")}</p>
          <blockquote className="mt-7 border-l-2 border-[#f4cdb9] pl-5 text-lg font-medium leading-relaxed text-white">
            “{t("about.founderQuote")}”
          </blockquote>
          <a href="https://www.linkedin.com/in/moaltamimi/" target="_blank" rel="noopener noreferrer" className="mt-7 inline-flex items-center text-sm font-semibold text-[#a9d7cd] hover:underline">
            {t("about.founderLink")} &rarr;
          </a>
        </div>
      </section>

      <section className="mt-8 grid gap-4 md:grid-cols-2" aria-label={t("about.pageTitle")}>
        <div className="rounded-[1.5rem] border border-border bg-surface p-6 shadow-sm">
          <h2 className="text-xl font-bold">{t("marketing.trustTitle")}</h2>
          <p className="mt-3 leading-relaxed text-muted">{t("about.trust")}</p>
          <a href="/trust" className="mt-5 inline-flex text-sm font-semibold text-accent underline">{t("marketing.navTrust")} &rarr;</a>
        </div>
        <div className="rounded-[1.5rem] bg-[#e9e2f0] p-6 text-[#173f42]">
          <h2 className="text-xl font-bold">{t("marketing.footerAi")}</h2>
          <p className="mt-3 leading-relaxed text-[#43595a]">{t("about.capstone")}</p>
          <a href="/ai-transparency" className="mt-5 inline-flex text-sm font-semibold underline">{t("marketing.footerAi")} &rarr;</a>
        </div>
      </section>

      <div className="mx-auto mt-10 max-w-reading text-center">
        <p className="mt-6 text-sm text-muted">{t("about.contact")}</p>
        <div className="mt-8">
          <ButtonLink href="/register">{t("marketing.heroPrimary")}</ButtonLink>
        </div>
      </div>
    </div>
  );
}
