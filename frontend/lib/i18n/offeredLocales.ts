"use client";

/**
 * Language activation in the browser (06H, REQ-LANG-11/13/14). The SERVER decides which locales are offered (`GET /capabilities`:
 * `active_candidate_locales` is the OFFERED set, `unqualified_locales` the ones labelled UNQUALIFIED in development/test). The
 * browser only reflects that decision; the server enforces it again on every new activity, so hiding an option is a courtesy, not
 * the control. While the answer is unknown (loading, offline, signed out in a test without a backend) the static seven are shown,
 * unlabelled, exactly as before 06H; an explicit empty list from the server means NO language is offered.
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import type { CapabilitiesResponse } from "@/lib/api/types";
import { SELECTABLE_LOCALES, type AppLocale } from "@/lib/i18n/locales";

export type LocaleOption = (typeof SELECTABLE_LOCALES)[number] & { unqualified: boolean };

export interface OfferedLocales {
  options: LocaleOption[];
  /** True once the server answered. */
  known: boolean;
  /** Hosted environment with no qualified language: nothing can be selected. */
  noneAvailable: boolean;
}

const UNKNOWN: OfferedLocales = {
  options: SELECTABLE_LOCALES.map((l) => ({ ...l, unqualified: false })),
  known: false,
  noneAvailable: false,
};

/** Pure projection of the capabilities response (unit-tested). */
export function offeredLocalesFrom(caps: Pick<CapabilitiesResponse, "active_candidate_locales" | "unqualified_locales"> | null | undefined): OfferedLocales {
  if (!caps || !Array.isArray(caps.active_candidate_locales)) return UNKNOWN;
  const offered = new Set(caps.active_candidate_locales);
  const unqualified = new Set(caps.unqualified_locales ?? []);
  const options = SELECTABLE_LOCALES.filter((l) => offered.has(l.code)).map((l) => ({ ...l, unqualified: unqualified.has(l.code) }));
  return { options, known: true, noneAvailable: options.length === 0 };
}

let cached: Promise<OfferedLocales> | null = null;

export function resetOfferedLocalesCache(): void {
  cached = null;
}

function load(): Promise<OfferedLocales> {
  if (!cached) {
    cached = Promise.resolve()
      .then(() => api.capabilities())
      .then((c) => offeredLocalesFrom(c))
      .catch(() => UNKNOWN);
  }
  return cached;
}

export function useOfferedLocales(): OfferedLocales {
  const [state, setState] = useState<OfferedLocales>(UNKNOWN);
  useEffect(() => {
    let live = true;
    void load().then((v) => {
      if (live) setState(v);
    });
    return () => {
      live = false;
    };
  }, []);
  return state;
}

export type { AppLocale };
