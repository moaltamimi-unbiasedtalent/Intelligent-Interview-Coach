"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useT } from "@/components/i18n/I18nProvider";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/States";
import { api, ApiError } from "@/lib/api/client";
import type { CheckoutAvailability, CheckoutStatusView } from "@/lib/api/types";
import { newIdempotencyKey, trustedCheckoutUrl } from "@/lib/billing/trustedRedirect";

type Phase = "idle" | "preparing" | "redirecting" | "unavailable_provider";

/**
 * Premium checkout entry (W12.4D-C). TRUTHFUL by construction: the Continue button exists only when the SERVER says checkout is enabled
 * for the plan, and the page never states that a payment succeeded, a subscription is active or Premium is unlocked: those facts need
 * verified provider evidence that does not exist in this wave. The client sends only a plan code; price, currency and return URLs are
 * the server's. The redirect target is re-validated against an allow-list before the browser is sent anywhere.
 */
export function PremiumSubscriptionPanel() {
  const t = useT();
  const [availability, setAvailability] = useState<CheckoutAvailability | null>(null);
  const [status, setStatus] = useState<CheckoutStatusView | null>(null);
  const [statusFailed, setStatusFailed] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const key = useRef<string | null>(null);

  const load = useCallback(() => {
    setStatusFailed(false);
    api.billing.availability("premium").then(setAvailability).catch(() => setAvailability({ plan: "premium", available: false, reason: "not_enabled" }));
    api.billing.status().then(setStatus).catch(() => setStatusFailed(true));
  }, []);
  useEffect(load, [load]);

  const start = async () => {
    setPhase("preparing");
    key.current = key.current ?? newIdempotencyKey();            // the SAME key on a retry of this click: it can never create a second session
    try {
      const out = await api.billing.startCheckout("premium", key.current);
      const url = trustedCheckoutUrl(out.redirect_url);
      if (!url) { setPhase("unavailable_provider"); return; }
      setPhase("redirecting");
      window.location.assign(url);
    } catch (err) {
      setPhase("unavailable_provider");
      if (err instanceof ApiError && err.status === 409) key.current = null;
    }
  };

  if (!availability && !status && !statusFailed) return <LoadingState label={t("checkout.stillChecking")} />;
  const pending = status?.confirmation === "pending";
  const canceled = status?.checkout === "canceled";
  const expired = status?.checkout === "expired";

  return (
    <Card>
      <CardBody className="space-y-3" data-testid="checkout-panel">
        <h2 className="text-base font-semibold text-foreground">{t("checkout.title")}</h2>
        {statusFailed ? <Alert tone="warning">{t("checkout.statusUnavailable")}</Alert> : null}
        {pending ? (
          <Alert tone="info" title={t("checkout.pendingTitle")}>{t("checkout.pendingBody")}</Alert>
        ) : canceled ? (
          <Alert tone="info" title={t("checkout.canceledTitle")}>{t("checkout.canceledBody")}</Alert>
        ) : expired ? (
          <Alert tone="info">{t("checkout.expired")}</Alert>
        ) : null}
        {phase === "unavailable_provider" ? <Alert tone="warning">{t("checkout.providerUnavailable")}</Alert> : null}
        {availability?.available && !pending ? (
          <>
            <p className="text-sm text-muted">{t("checkout.selectPlan")}</p>
            <Button onClick={start} disabled={phase === "preparing" || phase === "redirecting"} data-testid="checkout-start">
              {phase === "preparing" ? t("checkout.preparing") : phase === "redirecting" ? t("checkout.redirecting") : t("checkout.start")}
            </Button>
            <p className="text-xs text-muted">{t("checkout.sellerNote")} {t("checkout.manageNote")}</p>
          </>
        ) : availability && !pending ? (
          <p className="text-sm text-muted" data-testid="checkout-unavailable">{t("checkout.unavailable")}</p>
        ) : null}
        <p className="text-xs text-muted">{t("checkout.noInvoices")}</p>
      </CardBody>
    </Card>
  );
}
