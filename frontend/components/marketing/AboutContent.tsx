"use client";

import Image from "next/image";

import { useT } from "@/components/i18n/I18nProvider";
import { ButtonLink } from "@/components/ui/Button";

// P10B-W9.6: localized body for the About page. Extracted from app/about/page.tsx so it can use
// useT(); the server page keeps its `export const metadata`. The Trust / AI transparency cross-links
// reuse the existing marketing namespace labels. See lib/i18n/messages/w96/legal.ts.
export function AboutContent() {
  const t = useT();
  return (
    <div className="mx-auto max-w-reading px-4 py-16">
      <h1 className="text-3xl font-bold md:text-4xl">{t("about.pageTitle")}</h1>
      <p className="mt-4 text-muted">{t("about.lead")}</p>
      <p className="mt-4 text-muted">{t("about.trust")}</p>
      <p className="mt-4 text-muted">
        {t("about.capstone")} {t("about.seeAlso")}:{" "}
        <a href="/trust" className="underline">{t("marketing.navTrust")}</a>,{" "}
        <a href="/ai-transparency" className="underline">{t("marketing.footerAi")}</a>.
      </p>
      {/* Wave 8 B0: candid coaching conversation. Illustrative AI-generated brand photography - the
          depicted people are not Ask4Mo employees, customers or testimonial subjects. */}
      <figure className="mt-8 overflow-hidden rounded-lg border border-border">
        <Image
          src="/images/ask4mo/ask4mo-about-human-conversation.png"
          alt={t("about.imageAlt")}
          width={1448}
          height={1086}
          sizes="(max-width: 720px) 100vw, 720px"
          className="h-auto w-full"
        />
      </figure>
      <p className="mt-6 text-sm text-muted">{t("about.contact")}</p>
      <div className="mt-8">
        <ButtonLink href="/register">{t("marketing.heroPrimary")}</ButtonLink>
      </div>
    </div>
  );
}
