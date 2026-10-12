"use client";

// Reusable provenance label (Pilot 2 P2-04). Visible text always (never colour or icon alone); the explanation is visible text too,
// not a tooltip. Bounded kinds only.

import { useT } from "@/components/i18n/I18nProvider";
import type { ProvenanceKind } from "@/lib/provenance";
import { cn } from "@/lib/utils";

const KEYS: Record<ProvenanceKind, { label: string; explain: string }> = {
  ai: { label: "provenance.aiLabel", explain: "provenance.aiExplain" },
  external_source: { label: "provenance.sourcesLabel", explain: "provenance.sourcesExplain" },
  candidate_evidence: { label: "provenance.yourEvidenceLabel", explain: "provenance.yourEvidenceExplain" },
  candidate_reviewed: { label: "provenance.reviewedLabel", explain: "provenance.reviewedExplain" },
};

const TONE: Record<ProvenanceKind, string> = {
  ai: "border-border bg-surface-2 text-foreground",
  external_source: "border-accent/40 bg-surface text-foreground",
  candidate_evidence: "border-accent bg-surface text-foreground",
  candidate_reviewed: "border-border bg-surface text-foreground",
};

export function ProvenanceBadge({ kind, explain = false, className }: { kind: ProvenanceKind; explain?: boolean; className?: string }) {
  const t = useT();
  return (
    <span className={cn("inline-flex max-w-full flex-col", className)} data-provenance={kind}>
      <span className={cn("inline-flex w-fit items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold", TONE[kind])}>{t(KEYS[kind].label)}</span>
      {explain ? <span className="mt-1 text-xs text-muted">{t(KEYS[kind].explain)}</span> : null}
    </span>
  );
}

/** Small "What these labels mean" disclosure: the labels themselves stay visible elsewhere; this only defines them. */
export function ProvenanceExplainer({ className }: { className?: string }) {
  const t = useT();
  return (
    <details className={cn("rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs", className)} data-testid="provenance-explainer">
      <summary className="cursor-pointer font-medium text-foreground">{t("provenance.explainerTitle")}</summary>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-muted">
        <li>{t("provenance.explainerAi")}</li>
        <li>{t("provenance.explainerSource")}</li>
        <li>{t("provenance.explainerYours")}</li>
        <li>{t("provenance.explainerReviewed")}</li>
      </ul>
    </details>
  );
}
