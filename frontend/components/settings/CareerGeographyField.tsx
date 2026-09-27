"use client";

/**
 * Account-default career-geography selector (P10B Wave 2). A bounded, validated set of career
 * markets, DELIBERATELY independent of interface/conversation/dictation language — never inferred
 * from a locale. Reused by onboarding and Settings. Emits only an allow-listed code ("" = unset).
 */

import { useId } from "react";
import { useI18n } from "@/components/i18n/I18nProvider";

// Mirrors the backend allow-list (src/persistence.py CAREER_GEOGRAPHIES).
export const CAREER_GEOGRAPHIES = [
  "", "global", "de", "at", "ch", "fr", "es", "it", "pt", "nl", "be", "lu",
  "gb", "ie", "us", "ca", "au", "nz", "other",
] as const;
export type CareerGeography = (typeof CAREER_GEOGRAPHIES)[number];

function labelKey(code: string): string {
  return code === "" ? "geography.unspecified" : `geography.${code}`;
}

export function CareerGeographyField({
  value,
  onChange,
  disabled = false,
}: {
  value: CareerGeography;
  onChange: (value: CareerGeography) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const id = useId();
  return (
    <div className="grid gap-1">
      <label htmlFor={id} className="text-sm font-medium text-foreground">{t("geography.label")}</label>
      <p className="text-xs text-muted">{t("onboarding.geographyHelp")}</p>
      <select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value as CareerGeography)}
        className="min-h-[44px] w-full max-w-xs rounded-lg border border-border bg-surface px-2 text-sm"
      >
        {CAREER_GEOGRAPHIES.map((code) => (
          <option key={code || "unspecified"} value={code}>{t(labelKey(code))}</option>
        ))}
      </select>
    </div>
  );
}
