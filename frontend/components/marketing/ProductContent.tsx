"use client";

import Image from "next/image";

import { useT } from "@/components/i18n/I18nProvider";
import { ButtonLink } from "@/components/ui/Button";
import { MarketingIcon, type IconName } from "@/components/marketing/MarketingIcon";

// P10B Wave 7: the product page explains Ask4Mo as ONE connected workflow centred on the
// Opportunity (Wave 6), not a feature catalogue. Reuses the marketing i18n keys; no emoji;
// no em dash (guarded).

const PARTS: [string, string, IconName][] = [
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

export function ProductContent() {
  const t = useT();
  return (
    <div className="mx-auto max-w-content px-4 py-16">
      <header className="max-w-reading">
        <h1 className="text-3xl font-bold md:text-4xl">{t("marketing.systemTitle")}</h1>
        <p className="mt-3 text-lg text-muted">{t("marketing.systemLead")}</p>
      </header>

      {/* Wave 8 B0: hand-drawn editorial illustration of the one connected system. Its warm paper
          background is preserved inside a clean bordered figure; shown full-frame (no crop). */}
      <figure className="mt-8 overflow-hidden rounded-lg border border-border">
        <Image
          src="/images/ask4mo/ask4mo-product-connected-system-editorial.png"
          alt={t("marketing.productImageAlt")}
          width={1536}
          height={1024}
          sizes="(max-width: 1152px) 100vw, 1152px"
          className="h-auto w-full"
        />
      </figure>

      {/* The parts of one system */}
      <div className="mt-10 grid gap-6 sm:grid-cols-2">
        {PARTS.map(([title, body, icon]) => (
          <section key={title} className="rounded-lg border border-border bg-surface p-6">
            <MarketingIcon name={icon} className="h-6 w-6 text-accent" />
            <h2 className="mt-3 text-lg font-semibold">{t(title)}</h2>
            <p className="mt-2 text-muted">{t(body)}</p>
          </section>
        ))}
      </div>

      {/* The Opportunity journey */}
      <section className="mt-16">
        <h2 className="text-2xl font-bold">{t("marketing.howTitle")}</h2>
        <p className="mt-2 text-muted">{t("marketing.howLead")}</p>
        <ol className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
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

      <div className="mt-12 text-center">
        <ButtonLink href="/register">{t("marketing.heroPrimary")}</ButtonLink>
      </div>
    </div>
  );
}
