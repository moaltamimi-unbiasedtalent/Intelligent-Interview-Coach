"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useT } from "@/components/i18n/I18nProvider";
import { Alert } from "@/components/ui/Alert";
import { LoadingState } from "@/components/ui/States";
import { api } from "@/lib/api/client";

type State = "recording" | "pending" | "canceled" | "unavailable";

/**
 * Where the payment partner sends the browser back. A browser return PROVES NOTHING about payment: this page records that the browser
 * returned and shows "waiting for confirmation" (or "canceled"). It never says a payment succeeded, a subscription is active or
 * Premium is unlocked, whatever the query string says, and the `outcome` parameter is only a hint the server re-checks against its own record.
 */
export function ReturnPanel() {
  const t = useT();
  const params = useSearchParams();
  const session = params.get("session") || "";
  const outcome = params.get("outcome") === "cancel" ? "cancel" : "success";
  const [state, setState] = useState<State>(session ? "recording" : "unavailable");
  const ran = useRef(false);

  useEffect(() => {
    if (!session || ran.current) return;
    ran.current = true;
    api.billing
      .recordReturn(session, outcome)
      .then((res) => setState(res.status === "canceled" ? "canceled" : res.status === "expired" ? "unavailable" : "pending"))
      .catch(() => setState("unavailable"));
  }, [session, outcome]);

  return (
    <div className="mx-auto max-w-xl space-y-4 px-4 py-12" data-testid="billing-return">
      <h1 className="text-2xl font-bold">{t("checkout.returnTitle")}</h1>
      {state === "recording" ? <LoadingState label={t("checkout.stillChecking")} /> : null}
      {state === "pending" ? <Alert tone="info" title={t("checkout.pendingTitle")}>{t("checkout.pendingBody")}</Alert> : null}
      {state === "canceled" ? <Alert tone="info" title={t("checkout.canceledTitle")}>{t("checkout.canceledBody")}</Alert> : null}
      {state === "unavailable" ? <Alert tone="warning">{t("checkout.statusUnavailable")}</Alert> : null}
      <a href="/account" className="inline-flex min-h-[44px] items-center rounded border border-border px-4 text-sm font-semibold hover:bg-surface-2">
        {t("checkout.backToAccount")}
      </a>
    </div>
  );
}
