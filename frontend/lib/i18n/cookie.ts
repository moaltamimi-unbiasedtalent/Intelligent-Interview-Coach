/**
 * Anonymous/first-use locale cookie (Capstone P3.5).
 *
 * A bounded, non-sensitive UI preference cookie for visitors without an account (or
 * before the account preference loads). After sign-in the server-persisted account
 * preference is authoritative. Stores ONLY a supported locale code — never candidate
 * content. Safe on the server (SameSite=Lax, not HttpOnly so the client can read it
 * for immediate switching; it carries no security value).
 */

import { type AppLocale, toSupportedLocale } from "./locales";

export const LOCALE_COOKIE = "ask4mo_locale";
const MAX_AGE = 60 * 60 * 24 * 365; // 1 year

export function readLocaleCookie(): AppLocale | null {
  if (typeof document === "undefined") return null;
  try {
    const match = document.cookie
      .split("; ")
      .find((c) => c.startsWith(`${LOCALE_COOKIE}=`));
    return match ? toSupportedLocale(decodeURIComponent(match.split("=")[1])) : null;
  } catch {
    return null;
  }
}

export function writeLocaleCookie(locale: AppLocale): void {
  if (typeof document === "undefined") return;
  try {
    document.cookie = `${LOCALE_COOKIE}=${encodeURIComponent(locale)}; path=/; max-age=${MAX_AGE}; samesite=lax`;
  } catch {
    /* ignore */
  }
}

export function browserLocale(): AppLocale | null {
  if (typeof navigator === "undefined") return null;
  return toSupportedLocale(navigator.language);
}
