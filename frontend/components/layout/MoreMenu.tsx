"use client";

import Link from "@/components/ui/VerifiedLink";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useT } from "@/components/i18n/I18nProvider";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import { INTERNAL_NAV, SECONDARY_NAV } from "./nav-items";

/**
 * "More" — a compact secondary-navigation menu for supporting destinations
 * (Sources, Review & Diagnostics). Present in the header on all breakpoints, so both
 * desktop and mobile can reach these routes without cluttering the primary nav or the
 * mobile bottom bar. Settings is NOT here (it lives under the account control).
 *
 * Accessible menu semantics: aria-haspopup / aria-expanded, opens on click (not hover),
 * closes on select / outside-click / Escape, and supports keyboard focus + arrow keys.
 */
export function MoreMenu() {
  const pathname = usePathname();
  const t = useT();
  // Capability-aware Admin entry: visible ONLY with server-resolved admin permissions. Derived from
  // trusted account state (`admin_permissions`, server-provided), never a client override. `account` is null until the session
  // resolves, so the privileged item never flashes during loading/unknown. Hiding the link
  // is a UX affordance, NOT the security boundary — the API stays authoritative.
  const auth = useAuthOptional();
  const granted = adminPermissions(auth?.account);
  const internalItems = INTERNAL_NAV.filter((item) => hasAnyPermission(granted, item.anyOf));
  const isAdmin = internalItems.length > 0;
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  // A supporting destination is active → mark the More control (not a primary tab). Internal
  // destinations count too, but only when the caller is an admin (others never see them).
  const supportingActive =
    SECONDARY_NAV.some((item) => pathname === item.href || pathname.startsWith(item.href + "/")) ||
    (isAdmin && internalItems.some((item) => pathname === item.href || pathname.startsWith(item.href + "/")));

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
    // Move focus to the first menu item when opened by keyboard/click.
    const first = rootRef.current?.querySelector<HTMLElement>('[role="menuitem"]');
    first?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open, close]);

  const onMenuKeyDown = (e: React.KeyboardEvent) => {
    const items = Array.from(
      rootRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [],
    );
    const idx = items.indexOf(document.activeElement as HTMLElement);
    if (e.key === "ArrowDown") {
      e.preventDefault();
      items[(idx + 1) % items.length]?.focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      items[(idx - 1 + items.length) % items.length]?.focus();
    }
  };

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex min-h-[40px] items-center gap-1 rounded-[8px] px-3 py-1.5 text-sm font-medium transition-colors",
          supportingActive ? "bg-surface-2 text-foreground" : "text-muted hover:text-foreground",
        )}
      >
        {t("nav.more")}
        <span aria-hidden="true" className="text-xs">▾</span>
      </button>

      {open ? (
        <div
          id={menuId}
          role="menu"
          aria-label={t("nav.moreDestinations")}
          onKeyDown={onMenuKeyDown}
          className="absolute right-0 z-40 mt-1 w-60 overflow-hidden rounded-[10px] border border-border bg-surface shadow-soft"
        >
          {SECONDARY_NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                role="menuitem"
                aria-current={active ? "page" : undefined}
                onClick={() => close()}
                className={cn(
                  "flex min-h-[44px] flex-col justify-center gap-0.5 px-3.5 py-2 text-sm transition-colors hover:bg-surface-2 focus:bg-surface-2 focus:outline-none",
                  active ? "text-foreground" : "text-foreground",
                )}
              >
                <span className="font-medium">{t(item.labelKey)}</span>
                {item.description ? (
                  <span className="text-xs text-muted">{item.description}</span>
                ) : null}
              </Link>
            );
          })}
          {/* INTERNAL destinations (Review & Diagnostics, Admin) — rendered ONLY for a
              server-authoritative PLATFORM_ADMIN. Ordinary candidates never see these items.
              Each destination's backend is independently authorized (hiding is UX only). */}
          {isAdmin
            ? internalItems.map((item) => {
                const active = pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    role="menuitem"
                    aria-current={active ? "page" : undefined}
                    onClick={() => close()}
                    className="flex min-h-[44px] flex-col justify-center gap-0.5 px-3.5 py-2 text-sm text-foreground transition-colors hover:bg-surface-2 focus:bg-surface-2 focus:outline-none"
                  >
                    <span className="font-medium">{"labelKey" in item ? t(item.labelKey) : item.label}</span>
                    {item.description ? <span className="text-xs text-muted">{item.description}</span> : null}
                  </Link>
                );
              })
            : null}
        </div>
      ) : null}
    </div>
  );
}
