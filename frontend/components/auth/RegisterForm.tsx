"use client";

import Link from "next/link";
import { useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { AuthCard, LabelledField } from "./AuthCard";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";

const MIN_PASSWORD = 10;

export function RegisterForm() {
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
      setError(`Password must be at least ${MIN_PASSWORD} characters.`);
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
      setError(err instanceof ApiError ? err.message : "Registration failed. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <AuthCard
        title="Check your email"
        footer={
          <Link href="/sign-in" className="font-semibold text-accent hover:underline">
            Go to sign in
          </Link>
        }
      >
        <Alert tone="info">{done}</Alert>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Create your account"
      subtitle="Prepare with evidence, practise with purpose. Ask More. Be More."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/sign-in" className="font-semibold text-accent hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {error ? <Alert tone="danger">{error}</Alert> : null}
        <LabelledField label="Name (optional)" htmlFor="name">
          <Input
            id="name"
            type="text"
            autoComplete="name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
        </LabelledField>
        <LabelledField label="Email" htmlFor="email">
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
          label="Password"
          htmlFor="password"
          hint={`At least ${MIN_PASSWORD} characters.`}
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
          {busy ? "Creating account…" : "Create account"}
        </Button>
      </form>
    </AuthCard>
  );
}
