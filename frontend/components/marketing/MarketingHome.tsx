"use client";

import Link from "next/link";

import { useT } from "@/components/i18n/I18nProvider";
import { ButtonLink } from "@/components/ui/Button";

const FEATURES = [
  ["marketing.featurePrepareTitle", "marketing.featurePrepareBody", "📚"],
  ["marketing.featurePracticeTitle", "marketing.featurePracticeBody", "🎤"],
  ["marketing.featureEvidenceTitle", "marketing.featureEvidenceBody", "🔒"],
  ["marketing.featureVoiceTitle", "marketing.featureVoiceBody", "🗣️"],
  ["marketing.featureMemoryTitle", "marketing.featureMemoryBody", "🧠"],
  ["marketing.featureWorkspacesTitle", "marketing.featureWorkspacesBody", "🤝"],
] as const;

const STEPS = [
  ["marketing.howStep1Title", "marketing.howStep1Body"],
  ["marketing.howStep2Title", "marketing.howStep2Body"],
  ["marketing.howStep3Title", "marketing.howStep3Body"],
] as const;

export function MarketingHome() {
  const t = useT();
  return (
    <div>
      {/* Hero */}
      <section className="mx-auto max-w-content px-4 py-16 text-center md:py-24">
        <p className="text-sm font-semibold uppercase tracking-wide text-accent">Ask More. Be More.</p>
        <h1 className="mx-auto mt-3 max-w-3xl text-3xl font-bold tracking-tight md:text-5xl">
          {t("marketing.heroTitle")}
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-muted">{t("marketing.heroSubtitle")}</p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <ButtonLink href="/register">{t("marketing.heroPrimary")}</ButtonLink>
          <Link href="/product" className="text-sm font-medium text-foreground hover:underline">
            {t("marketing.heroSecondary")} →
          </Link>
        </div>
        <p className="mt-4 text-xs text-muted">{t("marketing.heroNote")}</p>
      </section>

      {/* Trust strip */}
      <section className="border-y border-border bg-surface-2">
        <div className="mx-auto flex max-w-content flex-wrap items-center justify-center gap-x-8 gap-y-2 px-4 py-6 text-sm text-muted">
          <span className="font-semibold text-foreground">{t("marketing.trustStripTitle")}:</span>
          <span>✓ {t("marketing.trustStripPrivate")}</span>
          <span>✓ {t("marketing.trustStripSources")}</span>
          <span>✓ {t("marketing.trustStripControl")}</span>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-content px-4 py-16">
        <h2 className="text-center text-2xl font-bold md:text-3xl">{t("marketing.featuresTitle")}</h2>
        <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(([title, body, icon]) => (
            <div key={title} className="rounded-lg border border-border bg-surface p-5">
              <div className="text-2xl" aria-hidden>{icon}</div>
              <h3 className="mt-2 font-semibold">{t(title)}</h3>
              <p className="mt-1 text-sm text-muted">{t(body)}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="border-t border-border bg-surface-2">
        <div className="mx-auto max-w-content px-4 py-16">
          <h2 className="text-center text-2xl font-bold md:text-3xl">{t("marketing.howTitle")}</h2>
          <ol className="mt-10 grid gap-6 md:grid-cols-3">
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
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-content px-4 py-16 text-center">
        <h2 className="text-2xl font-bold md:text-3xl">{t("marketing.ctaTitle")}</h2>
        <p className="mx-auto mt-2 max-w-xl text-muted">{t("marketing.ctaBody")}</p>
        <div className="mt-6">
          <ButtonLink href="/register">{t("marketing.ctaButton")}</ButtonLink>
        </div>
      </section>
    </div>
  );
}
