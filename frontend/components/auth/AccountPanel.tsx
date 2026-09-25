"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { useAuth } from "./AuthProvider";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/States";

export function AccountPanel() {
  const { account, status, isRealSession, refresh, signOut } = useAuth();
  const router = useRouter();
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (status === "loading") return <LoadingState label="Loading your account" />;
  if (!account) return <Alert tone="warning">You are not signed in.</Alert>;

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

  const requestDeletion = async () => {
    setError(null);
    try {
      // Capstone P8: permanent, application-controlled deletion (data + private files +
      // checkpoints). Signs out on completion.
      await api.auth.deleteAccount();
      await refresh();
      router.replace("/sign-in");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not process the request.");
    }
  };

  return (
    <div className="mx-auto w-full max-w-[640px] space-y-5 py-2">
      <h1 className="text-2xl font-bold text-foreground">Your account</h1>

      {notice ? <Alert tone="info">{notice}</Alert> : null}
      {error ? <Alert tone="danger">{error}</Alert> : null}

      <Card>
        <CardBody className="space-y-3">
          <Row label="Email" value={account.email || "—"} />
          <Row
            label="Email status"
            value={
              account.email_verified ? (
                <Badge>Verified</Badge>
              ) : (
                <span className="flex items-center gap-2">
                  <Badge>Unverified</Badge>
                  {isRealSession ? (
                    <button onClick={resend} className="text-sm text-accent hover:underline">
                      Resend link
                    </button>
                  ) : null}
                </span>
              )
            }
          />
          <Row label="Plan" value={<Badge>{account.tier === "premium" ? "Premium" : "Basic"}</Badge>} />
          {account.platform_role !== "user" ? (
            <Row label="Role" value={<Badge>{account.platform_role}</Badge>} />
          ) : null}
          <Row label="Sign-in method" value={methodLabel(account.auth_method)} />
        </CardBody>
      </Card>

      <div className="flex flex-wrap items-center gap-3">
        <a
          href="/settings"
          className="inline-flex min-h-[36px] items-center rounded border border-border px-3 text-sm font-semibold text-foreground hover:bg-surface-2"
        >
          Preparation memory &amp; preferences
        </a>
      </div>

      {isRealSession ? (
        <div className="flex flex-wrap gap-3">
          <Button variant="ghost" onClick={doSignOut}>
            Sign out
          </Button>
        </div>
      ) : (
        <Alert tone="info">
          You&apos;re using the local development identity. Sign in with a real account for the full
          session experience.
        </Alert>
      )}

      <Card>
        <CardBody className="space-y-3">
          <h2 className="text-base font-semibold text-foreground">Manage your data</h2>
          <p className="text-sm text-muted">
            Your data rights are always free. Manage what Ask4Mo keeps:
          </p>
          <div className="flex flex-wrap gap-2" data-testid="data-rights-links">
            <a href="/settings" className="inline-flex min-h-[36px] items-center rounded border border-border px-3 text-sm text-foreground hover:bg-surface-2">Manage Memory</a>
            <a href="/documents" className="inline-flex min-h-[36px] items-center rounded border border-border px-3 text-sm text-foreground hover:bg-surface-2">Manage documents</a>
            <a href="/workspaces" className="inline-flex min-h-[36px] items-center rounded border border-border px-3 text-sm text-foreground hover:bg-surface-2">Manage sharing</a>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardBody className="space-y-3">
          <h2 className="text-base font-semibold text-foreground">Privacy &amp; data</h2>
          <p className="text-sm text-muted">
            You can export a copy of your data, or permanently delete your account. Deletion
            removes your account and its application-controlled data (documents, private files,
            Practice history, Memory, Story Bank, sessions and agent context) and signs you out.
            Security/audit records are anonymized, not deleted; historical infrastructure backups
            age out per the provider&apos;s retention schedule.
          </p>
          <div className="flex flex-wrap gap-3">
            <a
              href={`${apiExportUrl()}`}
              className="inline-flex min-h-[36px] items-center rounded border border-border px-3 text-sm font-semibold text-foreground hover:bg-surface-2"
            >
              Export my data
            </a>
            {!confirmDelete ? (
              <Button variant="ghost" onClick={() => setConfirmDelete(true)}>
                Delete my account
              </Button>
            ) : (
              <span className="flex items-center gap-2">
                <span className="text-sm text-danger">Are you sure?</span>
                <Button variant="ghost" onClick={requestDeletion}>
                  Yes, delete
                </Button>
                <button className="text-sm text-muted hover:text-foreground" onClick={() => setConfirmDelete(false)}>
                  Cancel
                </button>
              </span>
            )}
          </div>
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

function methodLabel(method: string): string {
  if (method === "session") return "Password / social";
  if (method === "dev_header") return "Development header";
  return "Anonymous (development)";
}

function apiExportUrl(): string {
  // Direct link so the browser sends the session cookie and downloads the JSON.
  const base =
    (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "")) ||
    "http://localhost:8000/api/v1";
  return `${base}/auth/account/export`;
}
