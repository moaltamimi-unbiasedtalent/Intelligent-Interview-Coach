"use client";

/**
 * Header account control (Capstone P1/E1 · P10B Wave 1).
 *
 * Signed in → initials avatar that opens an accessible menu with Account, **Settings** and
 * Sign out (fixes the founder finding that Settings was only reachable via Progress → Manage).
 * Signed out → a "Sign in" link. Purely presentational auth state; it grants nothing
 * (authorization stays server-side).
 */

import Link from "@/components/ui/VerifiedLink";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";
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
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  const close = useCallback((focusButton = false) => {
    setOpen(false);
    if (focusButton) buttonRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close(true);
    };
    const onClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) close();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    rootRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open, close]);

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
    close();
    await signOut();
    router.replace("/sign-in");
  };

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={t("nav.account")}
        title={account.email || t("nav.account")}
        onClick={() => setOpen((v) => !v)}
        className="grid h-8 w-8 place-items-center rounded-full bg-secondary text-xs font-bold text-[#3a3324]"
      >
        {initials(account.email, account.display_name)}
      </button>

      {open ? (
        <div
          id={menuId}
          role="menu"
          aria-label={t("nav.account")}
          className="absolute right-0 z-40 mt-1 w-52 overflow-hidden rounded-[10px] border border-border bg-surface shadow-soft"
        >
          <Link
            href="/account"
            role="menuitem"
            onClick={() => close()}
            className="flex min-h-[44px] items-center px-3.5 py-2 text-sm font-medium text-foreground hover:bg-surface-2 focus:bg-surface-2 focus:outline-none"
          >
            {t("nav.account")}
          </Link>
          <Link
            href="/settings"
            role="menuitem"
            onClick={() => close()}
            className="flex min-h-[44px] items-center px-3.5 py-2 text-sm font-medium text-foreground hover:bg-surface-2 focus:bg-surface-2 focus:outline-none"
          >
            {t("settings.title")}
          </Link>
          <Link
            href="/account/data"
            role="menuitem"
            onClick={() => close()}
            className="flex min-h-[44px] items-center px-3.5 py-2 text-sm font-medium text-foreground hover:bg-surface-2 focus:bg-surface-2 focus:outline-none"
          >
            {t("trustUx.navDataPrivacy")}
          </Link>
          <Link
            href="/trust"
            role="menuitem"
            onClick={() => close()}
            className="flex min-h-[44px] items-center px-3.5 py-2 text-sm font-medium text-foreground hover:bg-surface-2 focus:bg-surface-2 focus:outline-none"
          >
            {t("trustUx.navTrust")}
          </Link>
          {isRealSession ? (
            <button
              type="button"
              role="menuitem"
              onClick={handleSignOut}
              className="flex w-full min-h-[44px] items-center px-3.5 py-2 text-left text-sm text-muted hover:bg-surface-2 hover:text-foreground focus:bg-surface-2 focus:outline-none"
            >
              {t("common.signOut")}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
