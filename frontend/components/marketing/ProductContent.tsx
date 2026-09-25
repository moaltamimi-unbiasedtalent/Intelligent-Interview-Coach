"use client";

import { useT } from "@/components/i18n/I18nProvider";
import { ButtonLink } from "@/components/ui/Button";

const SECTIONS = [
  ["marketing.featurePrepareTitle", "marketing.featurePrepareBody"],
  ["marketing.featurePracticeTitle", "marketing.featurePracticeBody"],
  ["marketing.featureEvidenceTitle", "marketing.featureEvidenceBody"],
  ["marketing.featureVoiceTitle", "marketing.featureVoiceBody"],
  ["marketing.featureMemoryTitle", "marketing.featureMemoryBody"],
  ["marketing.featureWorkspacesTitle", "marketing.featureWorkspacesBody"],
] as const;

export function ProductContent() {
  const t = useT();
  return (
    <div className="mx-auto max-w-content px-4 py-16">
      <h1 className="text-3xl font-bold md:text-4xl">{t("marketing.featuresTitle")}</h1>
      <div className="mt-10 space-y-8">
        {SECTIONS.map(([title, body]) => (
          <section key={title} className="rounded-lg border border-border bg-surface p-6">
            <h2 className="text-lg font-semibold">{t(title)}</h2>
            <p className="mt-2 text-muted">{t(body)}</p>
          </section>
        ))}
      </div>
      <div className="mt-10 text-center">
        <ButtonLink href="/register">{t("marketing.heroPrimary")}</ButtonLink>
      </div>
    </div>
  );
}
