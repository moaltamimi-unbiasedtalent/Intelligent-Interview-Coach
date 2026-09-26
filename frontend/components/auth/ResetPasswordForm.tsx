"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { AuthCard, LabelledField } from "./AuthCard";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { useT } from "@/components/i18n/I18nProvider";

const MIN_PASSWORD = 10;

export function ResetPasswordForm() {
  const t = useT();
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password.length < MIN_PASSWORD) {
      setError(t("auth.weakPassword", { min: MIN_PASSWORD }));
      return;
    }
    setBusy(true);
    try {
      await api.auth.resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.couldNotReset"));
    } finally {
      setBusy(false);
    }
  };

  if (!token) {
    return (
      <AuthCard title={t("auth.resetTitle")}>
        <Alert tone="danger">{t("auth.resetLinkInvalid")}</Alert>
        <div className="mt-4">
          <Link href="/forgot-password" className="font-semibold text-accent hover:underline">
            {t("auth.requestNewLink")}
          </Link>
        </div>
      </AuthCard>
    );
  }

  if (done) {
    return (
      <AuthCard title={t("auth.passwordUpdated")}>
        <Alert tone="info">{t("auth.passwordResetDone")}</Alert>
        <Button className="mt-4 w-full" onClick={() => router.replace("/sign-in")}>
          {t("auth.goToSignIn")}
        </Button>
      </AuthCard>
    );
  }

  return (
    <AuthCard title={t("auth.chooseNewPassword")}>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {error ? <Alert tone="danger">{error}</Alert> : null}
        <LabelledField
          label={t("auth.newPassword")}
          htmlFor="password"
          hint={t("auth.passwordHint", { min: MIN_PASSWORD })}
        >
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </LabelledField>
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? t("auth.updating") : t("auth.updatePassword")}
        </Button>
      </form>
    </AuthCard>
  );
}
