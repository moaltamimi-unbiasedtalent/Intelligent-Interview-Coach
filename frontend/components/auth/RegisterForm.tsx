"use client";

import Link from "next/link";
import { useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { AuthCard, LabelledField } from "./AuthCard";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { useT } from "@/components/i18n/I18nProvider";

const MIN_PASSWORD = 10;

export function RegisterForm() {
  const t = useT();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
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
      const res = await api.auth.register({
        email,
        password,
        display_name: displayName.trim() || null,
      });
      // Uniform, non-enumerating message from the backend.
      setDone(res.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.registrationFailed"));
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <AuthCard
        title={t("auth.checkEmail")}
        footer={
          <Link href="/sign-in" className="font-semibold text-accent hover:underline">
            {t("auth.goToSignIn")}
          </Link>
        }
      >
        <Alert tone="info">{done}</Alert>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title={t("auth.registerTitle")}
      subtitle={t("auth.registerSubtitle")}
      footer={
        <>
          {t("auth.haveAccount")}{" "}
          <Link href="/sign-in" className="font-semibold text-accent hover:underline">
            {t("auth.signIn")}
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {error ? <Alert tone="danger">{error}</Alert> : null}
        <LabelledField label={t("auth.name")} htmlFor="name">
          <Input
            id="name"
            type="text"
            autoComplete="name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
        </LabelledField>
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
        <LabelledField
          label={t("auth.password")}
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
          {busy ? t("auth.creatingAccount") : t("auth.createAccount")}
        </Button>
      </form>
    </AuthCard>
  );
}
