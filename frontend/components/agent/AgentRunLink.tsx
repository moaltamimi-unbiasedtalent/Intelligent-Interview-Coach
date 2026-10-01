"use client";

import Link from "next/link";
import { useT } from "@/components/i18n/I18nProvider";

/** Secondary link from the Coach to the safe Agent Inspector for this run. */
export function AgentRunLink({ runId }: { runId: string }) {
  const t = useT();
  return (
    <Link
      href={`/review/agent?run=${encodeURIComponent(runId)}`}
      className="text-xs font-medium text-muted underline hover:text-foreground"
    >
      {t("prepare.viewRunDetails")}
    </Link>
  );
}
