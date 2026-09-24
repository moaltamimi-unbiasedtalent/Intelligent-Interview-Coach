"use client";

/**
 * Header account control (Capstone P1/E1).
 *
 * Signed in → initials avatar linking to the account page. A real session also shows
 * a sign-out control. Signed out → a "Sign in" link. Purely presentational auth state;
 * it grants nothing (authorization is server-side).
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";
import { useT } from "@/components/i18n/I18nProvider";

function initials(email: string | null, displayName: string | null): string {
  const source = (displayName || email || "").trim();
  if (!source) return "?";
  const parts = source.split(/[\s@.]+/).filter(Boolean);
  const letters = parts.length >= 2 ? parts[0][0] + parts[1][0] : source.slice(0, 2);
  return letters.toUpperCase();
}

export function AccountMenu() {
  const { account, status, isRealSession, signOut } = useAuth();
  const router = useRouter();
  const t = useT();

  if (status === "loading") {
    return <span className="h-8 w-8 animate-pulse rounded-full bg-surface-2" aria-hidden />;
  }

  if (status === "unauthenticated" || !account) {
    return (
      <Link
        href="/sign-in"
        className="inline-flex min-h-[36px] items-center rounded border border-border px-3 text-sm font-semibold text-foreground hover:bg-surface-2"
      >
        {t("common.signIn")}
      </Link>
    );
  }

  const handleSignOut = async () => {
    await signOut();
    router.replace("/sign-in");
  };

  return (
    <div className="flex items-center gap-2">
      <Link
        href="/account"
        aria-label={t("nav.account")}
        title={account.email || t("nav.account")}
        className="grid h-8 w-8 place-items-center rounded-full bg-secondary text-xs font-bold text-[#3a3324]"
      >
        {initials(account.email, account.display_name)}
      </Link>
      {isRealSession ? (
        <button
          type="button"
          onClick={handleSignOut}
          className="hidden text-sm font-medium text-muted hover:text-foreground sm:inline"
        >
          {t("common.signOut")}
        </button>
      ) : null}
    </div>
  );
}
