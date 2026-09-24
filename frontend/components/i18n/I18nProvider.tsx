"use client";

/**
 * Interface-language context (Capstone P3.5).
 *
 * Resolves the active UI locale and exposes a translator `t()` plus locale-aware
 * date/number formatters. Resolution order:
 *   1. the authenticated account's `interface_locale` (authoritative once loaded);
 *   2. the anonymous locale cookie;
 *   3. the browser locale if it maps to a supported language;
 *   4. English.
 *
 * `setLocale` persists to the account when signed in (server-authoritative across
 * devices) and always mirrors to the cookie for immediate, pre-auth switching. This is
 * the INTERFACE language only — independent of the dictation and Mo-conversation
 * languages, and it never changes labour-market geography.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api } from "@/lib/api/client";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { type AppLocale, DEFAULT_APP_LOCALE, toSupportedLocale } from "@/lib/i18n/locales";
import { translate, type MessageKey } from "@/lib/i18n/catalog";
import { browserLocale, readLocaleCookie, writeLocaleCookie } from "@/lib/i18n/cookie";

interface I18nValue {
  locale: AppLocale;
  t: (key: MessageKey | string, vars?: Record<string, string | number>) => string;
  setLocale: (locale: AppLocale) => Promise<void>;
  formatDate: (value: string | number | Date, opts?: Intl.DateTimeFormatOptions) => string;
  formatNumber: (value: number, opts?: Intl.NumberFormatOptions) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({
  initialLocale,
  children,
}: {
  initialLocale?: AppLocale;
  children: ReactNode;
}) {
  const auth = useAuthOptional();
  const accountLocale = toSupportedLocale(auth?.account?.interface_locale ?? null);
  const [locale, setLocaleState] = useState<AppLocale>(initialLocale ?? DEFAULT_APP_LOCALE);

  // First-use resolution (cookie → browser) before/without an account.
  useEffect(() => {
    if (initialLocale) return; // server already provided a locale from the cookie
    const resolved = readLocaleCookie() ?? browserLocale();
    if (resolved) setLocaleState(resolved);
  }, [initialLocale]);

  // The authenticated account preference is authoritative once loaded.
  useEffect(() => {
    if (accountLocale) setLocaleState(accountLocale);
  }, [accountLocale]);

  // Keep <html lang> in sync for assistive tech and correct rendering.
  useEffect(() => {
    try {
      document.documentElement.lang = locale;
    } catch {
      /* ignore */
    }
  }, [locale]);

  const setLocale = useCallback(
    async (next: AppLocale) => {
      setLocaleState(next);
      writeLocaleCookie(next);
      // Persist server-side when signed in (authoritative, cross-device).
      if (auth?.status === "authenticated") {
        try {
          await api.auth.updatePreferences({ interface_locale: next });
          await auth.refresh?.();
        } catch {
          /* keep the local switch even if the server update fails */
        }
      }
    },
    [auth],
  );

  const value = useMemo<I18nValue>(
    () => ({
      locale,
      t: (key, vars) => translate(locale, key, vars),
      setLocale,
      formatDate: (v, opts) => {
        try {
          return new Intl.DateTimeFormat(locale, opts).format(new Date(v));
        } catch {
          return String(v);
        }
      },
      formatNumber: (v, opts) => {
        try {
          return new Intl.NumberFormat(locale, opts).format(v);
        } catch {
          return String(v);
        }
      },
    }),
    [locale, setLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    // Safe fallback so a component rendered without the provider (e.g. an isolated unit
    // test) still works in English rather than throwing.
    return {
      locale: DEFAULT_APP_LOCALE,
      t: (key, vars) => translate(DEFAULT_APP_LOCALE, key, vars),
      setLocale: async () => {},
      formatDate: (v) => String(v),
      formatNumber: (v) => String(v),
    };
  }
  return ctx;
}

/** Convenience hook: just the translator. */
export function useT() {
  return useI18n().t;
}
