"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { useAuth } from "./AuthProvider";
import { AuthCard, LabelledField } from "./AuthCard";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { useT } from "@/components/i18n/I18nProvider";

export function SignInForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { refresh } = useAuth();
  const t = useT();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.auth.login({ email, password });
      await refresh();
      const next = params.get("next");
      router.replace(next && next.startsWith("/") ? next : "/");
    } catch (err) {
      // Safe, generic message from the backend (no enumeration).
      setError(err instanceof ApiError ? err.message : t("auth.signInFailed"));
      setBusy(false);
    }
  };

  return (
    <AuthCard
      title={t("auth.signInTitle")}
      subtitle={t("auth.signInSubtitle")}
      footer={
        <>
          {t("auth.newHere")}{" "}
          <Link href="/register" className="font-semibold text-accent hover:underline">
            {t("auth.createAccount")}
          </Link>
        </>
      }
    >
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
        <LabelledField label={t("auth.password")} htmlFor="password">
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </LabelledField>
        <div className="flex items-center justify-between text-sm">
          <Link href="/forgot-password" className="text-accent hover:underline">
            {t("auth.forgotPassword")}
          </Link>
        </div>
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? t("auth.signingIn") : t("common.signIn")}
        </Button>
      </form>
    </AuthCard>
  );
}
