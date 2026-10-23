"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { AuthCard, LabelledField } from "./AuthCard";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { useI18n } from "@/components/i18n/I18nProvider";
import { BetaPricingStatement } from "@/components/plan/BetaPricingStatement";

const MIN_PASSWORD = 10;
const INVITATION_FRAGMENT = /(?:^|[#&])invitation=([^&]+)/;

export function RegisterForm() {
  const { t, locale } = useI18n();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [invitation, setInvitation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // A copied invitation link carries the code in the URL FRAGMENT (never sent to a server, a proxy log or a Referer header). Read it once, then
  // remove it from the address bar and history entry; it lives only in this component's state (never storage, never a cookie).
  useEffect(() => {
    const match = INVITATION_FRAGMENT.exec(window.location.hash);
    if (!match) return;
    try {
      setInvitation(decodeURIComponent(match[1]).slice(0, 128));
    } catch {
      /* a malformed fragment is ignored */
    }
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
  }, []);

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
        locale, // the recipient's interface language for the verification email
        invitation_code: invitation.trim() || null,
      });
      // Uniform, non-enumerating outcome; the copy is localised here (the server text is only the fallback).
      setDone(t("auth.registerSent") || res.message);
    } catch (err) {
      // One uniform, localized refusal for every unusable invitation (the server never says why, nor whether the email exists).
      if (err instanceof ApiError && err.code === "invitation_required") setError(t("auth.invitationRequired"));
      else setError(err instanceof ApiError ? err.message : t("auth.registrationFailed"));
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
      <BetaPricingStatement className="mb-4 text-sm text-muted" testId="register-beta-pricing" />
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {error ? <Alert tone="danger">{error}</Alert> : null}
        <LabelledField label={t("auth.invitationLabel")} htmlFor="invitation" hint={t("auth.invitationHint")}>
          <Input
            id="invitation"
            type="text"
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            maxLength={128}
            value={invitation}
            onChange={(e) => setInvitation(e.target.value)}
          />
        </LabelledField>
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
