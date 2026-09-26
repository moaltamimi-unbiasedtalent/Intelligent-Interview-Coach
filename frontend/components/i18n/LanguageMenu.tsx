"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";

import { cn } from "@/lib/utils";
import { useI18n } from "@/components/i18n/I18nProvider";
import { APP_LOCALES, type AppLocale } from "@/lib/i18n/locales";

/**
 * Global interface-language control (P10B Wave 1). Discoverable in BOTH the public marketing
 * chrome (anonymous visitors) and the authenticated app header. Selecting a locale calls the
 * existing `setLocale`, which preserves account → cookie → browser → English resolution and
 * persists to the account when signed in. It changes ONLY the interface locale — never the Mo
 * conversation language, dictation language, or career geography.
 *
 * Accessible: labelled trigger with aria-haspopup/expanded, opens on click, closes on select /
 * outside-click / Escape, arrow-key navigation, and the current locale marked aria-checked.
 */
export function LanguageMenu({ className }: { className?: string }) {
  const { locale, setLocale, t } = useI18n();
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
    rootRef.current?.querySelector<HTMLElement>('[role="menuitemradio"]')?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open, close]);

  const onMenuKeyDown = (e: React.KeyboardEvent) => {
    const items = Array.from(
      rootRef.current?.querySelectorAll<HTMLElement>('[role="menuitemradio"]') ?? [],
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

  const choose = (code: AppLocale) => {
    void setLocale(code);
    close(true);
  };

  const label = t("common.language");

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={label}
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-[36px] items-center gap-1 rounded-[8px] border border-border px-2.5 py-1.5 text-sm font-medium text-foreground hover:bg-surface-2"
        data-testid="language-menu-button"
      >
        {/* Non-emoji globe glyph (decorative); the visible current locale + aria-label name it. */}
        <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.6">
          <circle cx="12" cy="12" r="9" />
          <path d="M3 12h18M12 3c2.5 2.7 2.5 15.3 0 18M12 3c-2.5 2.7-2.5 15.3 0 18" />
        </svg>
        <span className="uppercase">{locale}</span>
      </button>

      {open ? (
        <div
          id={menuId}
          role="menu"
          aria-label={label}
          onKeyDown={onMenuKeyDown}
          className="absolute right-0 z-40 mt-1 w-44 overflow-hidden rounded-[10px] border border-border bg-surface shadow-soft"
        >
          {APP_LOCALES.map((l) => (
            <button
              key={l.code}
              type="button"
              role="menuitemradio"
              aria-checked={l.code === locale}
              onClick={() => choose(l.code)}
              className={cn(
                "flex w-full min-h-[40px] items-center justify-between px-3.5 py-2 text-left text-sm transition-colors hover:bg-surface-2 focus:bg-surface-2 focus:outline-none",
                l.code === locale ? "font-semibold text-foreground" : "text-foreground",
              )}
            >
              <span>{l.nativeLabel}</span>
              <span className="text-xs uppercase text-muted">{l.code}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
