"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { useAuth } from "./AuthProvider";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PlanSummary } from "@/components/account/PlanSummary";
import { Card, CardBody } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/States";
import { useT } from "@/components/i18n/I18nProvider";

export function AccountPanel() {
  const { account, status, isRealSession, signOut } = useAuth();
  const router = useRouter();
  const t = useT();
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (status === "loading") return <LoadingState label={t("account.loadingAccount")} />;
  if (!account) return <Alert tone="warning">{t("account.notSignedIn")}</Alert>;

  const resend = async () => {
    setError(null);
    try {
      const res = await api.auth.resendVerification();
      setNotice(res.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not resend the link.");
    }
  };

  const doSignOut = async () => {
    await signOut();
    router.replace("/sign-in");
  };

  return (
    <div className="mx-auto w-full max-w-[640px] space-y-5 py-2">
      <h1 className="text-2xl font-bold text-foreground">{t("account.title")}</h1>

      {notice ? <Alert tone="info">{notice}</Alert> : null}
      {error ? <Alert tone="danger">{error}</Alert> : null}

      <Card>
        <CardBody className="space-y-3">
          <Row label={t("account.email")} value={account.email || "-"} />
          <Row
            label={t("account.emailStatus")}
            value={
              account.email_verified ? (
                <Badge>{t("account.verified")}</Badge>
              ) : (
                <span className="flex items-center gap-2">
                  <Badge>{t("account.unverified")}</Badge>
                  {isRealSession ? (
                    <button onClick={resend} className="text-sm text-accent hover:underline">
                      {t("account.resendLink")}
                    </button>
                  ) : null}
                </span>
              )
            }
          />
          {account.platform_role !== "user" ? (
            <Row label={t("account.role")} value={<Badge>{account.platform_role}</Badge>} />
          ) : null}
          <Row label={t("account.signInMethod")} value={methodLabel(account.auth_method, t)} />
        </CardBody>
      </Card>

      <PlanSummary />

      <div className="flex flex-wrap items-center gap-3">
        <a
          href="/settings"
          className="inline-flex min-h-[36px] items-center rounded border border-border px-3 text-sm font-semibold text-foreground hover:bg-surface-2"
        >
          {t("account.memoryAndPreferences")}
        </a>
      </div>

      {isRealSession ? (
        <div className="flex flex-wrap gap-3">
          <Button variant="ghost" onClick={doSignOut}>
            {t("common.signOut")}
          </Button>
        </div>
      ) : (
        <Alert tone="info">{t("account.devIdentity")}</Alert>
      )}

      <Card>
        <CardBody className="space-y-3">
          <h2 className="text-base font-semibold text-foreground">{t("account.privacyData")}</h2>
          <p className="text-sm text-muted">{t("account.privacyDataDesc")}</p>
          <a
            href="/account/data"
            data-testid="data-privacy-link"
            className="inline-flex min-h-[44px] items-center rounded border border-border px-3 text-sm font-semibold text-foreground hover:bg-surface-2"
          >
            {t("dataPrivacy.title")}
          </a>
        </CardBody>
      </Card>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border pb-2 last:border-0 last:pb-0">
      <span className="text-sm text-muted">{label}</span>
      <span className="text-sm font-medium text-foreground">{value}</span>
    </div>
  );
}

function methodLabel(method: string, t: (key: string) => string): string {
  if (method === "session") return t("account.methodSession");
  if (method === "dev_header") return t("account.methodDev");
  return t("account.methodAnon");
}
