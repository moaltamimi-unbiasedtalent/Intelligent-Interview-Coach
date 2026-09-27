"use client";

/**
 * Bounded Mo coaching-style selector (P10B Wave 2). ONE Mo, configured — the candidate chooses the
 * TONE of coaching, not a persona. Reused by onboarding and Settings. Accessible radiogroup with
 * real radio semantics; emits only a bounded code. It never changes scoring — the note says so.
 */

import { useId } from "react";
import { useI18n } from "@/components/i18n/I18nProvider";

export const COACHING_STYLES = ["supportive", "balanced", "direct", "challenging"] as const;
export type CoachingStyle = (typeof COACHING_STYLES)[number];

export function CoachingStyleField({
  value,
  onChange,
  disabled = false,
}: {
  value: CoachingStyle;
  onChange: (value: CoachingStyle) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const name = useId();
  return (
    <fieldset className="grid gap-2" disabled={disabled}>
      <legend className="text-sm font-medium text-foreground">{t("coaching.title")}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {COACHING_STYLES.map((style) => {
          const selected = value === style;
          return (
            <label
              key={style}
              className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors ${
                selected ? "border-accent bg-surface-2" : "border-border hover:bg-surface-2"
              }`}
            >
              <input
                type="radio"
                name={name}
                value={style}
                checked={selected}
                onChange={() => onChange(style)}
                disabled={disabled}
                className="mt-1 h-4 w-4"
              />
              <span>
                <span className="block text-sm font-semibold text-foreground">{t(`coaching.${style}`)}</span>
                <span className="mt-0.5 block text-xs text-muted">{t(`coaching.${style}Desc`)}</span>
              </span>
            </label>
          );
        })}
      </div>
      <p className="text-xs text-muted">{t("coaching.scoringNote")}</p>
    </fieldset>
  );
}
