"use client";

import { useT } from "@/components/i18n/I18nProvider";

// Reusable legal/policy page shell (Capstone P8 §10/§11/§12). Every policy surface carries a
// visible ENGINEERING DRAFT / legal-review-required banner and a "last updated" line. Bodies
// are authored in English pending localization + legal review (see the release matrix); this
// is honest about status rather than claiming reviewed/compliant copy.
export function LegalPage({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: React.ReactNode;
}) {
  const t = useT();
  return (
    <article className="mx-auto max-w-reading px-4 py-12">
      <div
        role="note"
        className="mb-6 rounded-md border border-warning/50 bg-warning/10 px-4 py-3 text-sm"
        data-testid="legal-draft-banner"
      >
        {t("marketing.draftBanner")}
      </div>
      <h1 className="text-3xl font-bold">{title}</h1>
      <p className="mt-1 text-xs text-muted">Last updated: {updated} · Engineering draft</p>
      <div className="prose mt-6 space-y-4 text-sm leading-relaxed text-foreground [&_h2]:mt-8 [&_h2]:text-lg [&_h2]:font-semibold [&_ul]:list-disc [&_ul]:pl-6 [&_li]:mt-1">
        {children}
      </div>
    </article>
  );
}
