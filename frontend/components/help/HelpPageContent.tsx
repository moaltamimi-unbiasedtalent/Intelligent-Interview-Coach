"use client";

import Image from "next/image";

import { PageHeader } from "@/components/layout/PageHeader";
import { HelpCenter } from "@/components/help/HelpCenter";
import { useT } from "@/components/i18n/I18nProvider";
import VerifiedLink from "@/components/ui/VerifiedLink";

// P10B-W9.6: localized shell for the Help page. Extracted from app/help/page.tsx so the page header
// and figure can use useT(); the server page keeps its `export const metadata`. The searchable Help
// Center content itself lives in HelpCenter. See lib/i18n/messages/w96/legal.ts.
export function HelpPageContent() {
  const t = useT();
  return (
    <section data-tour="help">
      <PageHeader
        eyebrow={t("help.eyebrow")}
        title={t("help.heading")}
        description={t("help.description")}
      />
      {/* Wave 8 B0: hand-painted watercolor journey (understand -> converse -> practise -> reflect).
          Editorial illustration; its warm paper background is kept inside a clean bordered figure. */}
      <figure className="mx-auto my-8 max-w-[960px] overflow-hidden rounded-lg border border-border">
        <Image
          src="/images/ask4mo/ask4mo-help-journey-watercolor.png"
          alt={t("help.journeyImageAlt")}
          width={1536}
          height={1024}
          sizes="(max-width: 960px) 100vw, 960px"
          className="h-auto w-full"
        />
      </figure>
      <HelpCenter />
      <div className="mx-auto mt-10 max-w-[960px] rounded-lg border border-border bg-surface px-5 py-4">
        <p className="text-sm text-muted">{t("support.helpPrompt")}</p>
        <div className="mt-3">
          <VerifiedLink
            href="/support"
            className="inline-flex min-h-[44px] items-center justify-center rounded border border-border px-[18px] text-[15px] font-semibold text-foreground hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2"
          >
            {t("support.contactCta")}
          </VerifiedLink>
        </div>
      </div>
    </section>
  );
}
