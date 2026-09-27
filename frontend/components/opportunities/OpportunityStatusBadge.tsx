"use client";

import type { OpportunityStatus } from "@/lib/api/types";
import { useI18n } from "@/components/i18n/I18nProvider";

const LABEL: Record<OpportunityStatus, string> = {
  active: "opportunity.statusActive",
  interviewing: "opportunity.statusInterviewing",
  offer: "opportunity.statusOffer",
  closed: "opportunity.statusClosed",
  archived: "opportunity.statusArchived",
};

// Status is never conveyed by colour alone - the text label is always present.
const TONE: Record<OpportunityStatus, string> = {
  active: "border-accent/50 text-accent",
  interviewing: "border-accent/50 text-accent",
  offer: "border-success/50 text-success",
  closed: "border-border text-muted",
  archived: "border-border text-muted",
};

export function OpportunityStatusBadge({ status }: { status: OpportunityStatus }) {
  const { t } = useI18n();
  return (
    <span className={`shrink-0 rounded border px-2 py-0.5 text-xs font-semibold ${TONE[status]}`}>
      {t(LABEL[status])}
    </span>
  );
}
