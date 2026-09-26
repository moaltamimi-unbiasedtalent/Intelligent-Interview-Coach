"use client";

import Link from "next/link";
import { useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { AuthCard, LabelledField } from "./AuthCard";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { useT } from "@/components/i18n/I18nProvider";

export function ForgotPasswordForm() {
  const t = useT();
  const [email, setEmail] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await api.auth.forgotPassword(email);
      setDone(res.message); // uniform message regardless of whether the email exists
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.genericError"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard
      title={t("auth.resetTitle")}
      subtitle={t("auth.resetSubtitle")}
      footer={
        <Link href="/sign-in" className="font-semibold text-accent hover:underline">
          {t("auth.backToSignIn")}
        </Link>
      }
    >
      {done ? (
        <Alert tone="info">{done}</Alert>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          {error ? <Alert tone="danger">{error}</Alert> : null}
          <LabelledField label={t("auth.email")} htmlFor="email">
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </LabelledField>
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? t("auth.sending") : t("auth.sendResetLink")}
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
