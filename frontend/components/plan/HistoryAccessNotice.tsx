"use client";

import { useT } from "@/components/i18n/I18nProvider";
import { Alert } from "@/components/ui/Alert";
import type { HistoryAccess } from "@/lib/api/types";

/** Shown ONLY when the server says this caller's history view is restricted. States that older interviews are retained, not deleted, and points to data rights. No upgrade or purchase action. */
export function HistoryAccessNotice({ access, shown }: { access?: HistoryAccess; shown: number }) {
  const t = useT();
  if (!access || !access.restricted || access.hidden_count <= 0) return null;
  return (
    <div className="mb-4" data-testid="history-access-notice">
      <Alert tone="info" title={t("planUx.history_title")}>
        <p>{t("planUx.history_body", { shown: String(shown), n: String(access.hidden_count) })}</p>
        <p className="mt-1">{t("planUx.history_rights")} <a href="/account" className="font-medium text-accent underline">{t("planUx.history_accountLink")}</a></p>
      </Alert>
    </div>
  );
}
