"use client";

/**
 * Remembered dictation recognition locale (Capstone P3 / E-dictation).
 *
 * The selected BCP-47 language code is a per-device UI convenience — NOT candidate
 * content, transcript or audio — so storing it in localStorage is safe (guarded in
 * try/catch). Resolution order:
 *   1. a previously stored, still-supported choice;
 *   2. otherwise the browser locale, IF its primary subtag maps to the supported set;
 *   3. otherwise the documented default (English).
 *
 * This is the DICTATION recognition locale only — deliberately separate from the
 * (future) application UI locale, the model profile and the response-detail
 * preference. The application language is never inferred from this choice, and no
 * personal characteristic is ever inferred from a language selection.
 */

import { useCallback, useEffect, useState } from "react";
import { DICTATION_LANGUAGES } from "@/components/ui/DictationControl";

const STORAGE_KEY = "ask4mo.dictationLang";
const DEFAULT = DICTATION_LANGUAGES[0].code; // documented default: English (en-US)
const ALLOWED = new Set(DICTATION_LANGUAGES.map((l) => l.code));

function primarySubtag(tag: string | undefined | null): string {
  return (tag || "").toLowerCase().split("-")[0];
}

/** Map a browser locale to a supported dictation locale by primary subtag, else null. */
function fromBrowserLocale(): string | null {
  try {
    const nav = primarySubtag(typeof navigator !== "undefined" ? navigator.language : "");
    if (!nav) return null;
    const match = DICTATION_LANGUAGES.find((l) => primarySubtag(l.code) === nav);
    return match ? match.code : null;
  } catch {
    return null;
  }
}

export function useDictationLanguage(): [string, (code: string) => void] {
  const [lang, setLang] = useState<string>(DEFAULT);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored && ALLOWED.has(stored)) {
        setLang(stored);
        return;
      }
    } catch {
      /* storage unavailable — fall through */
    }
    const fromLocale = fromBrowserLocale();
    if (fromLocale) setLang(fromLocale);
  }, []);

  const update = useCallback((code: string) => {
    if (!ALLOWED.has(code)) return;
    setLang(code);
    try {
      window.localStorage.setItem(STORAGE_KEY, code);
    } catch {
      /* ignore */
    }
  }, []);

  return [lang, update];
}
