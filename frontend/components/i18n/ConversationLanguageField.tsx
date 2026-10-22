"use client";

/**
 * Conversation-language selector for Prepare/Practice setup (P10B Wave 4 · §9).
 *
 * Surfaces the interview/coaching language IN the setup flow so the candidate does not have to
 * visit Settings to see or change it, and clearly distinguishes it from the interface and
 * dictation languages. It writes only a bounded locale code into the caller's request; it never
 * changes career geography and never introduces a competing preference store (the default comes
 * from the existing account preference, resolved by the caller).
 */

import { useId } from "react";
import { type AppLocale } from "@/lib/i18n/locales";
import { useOfferedLocales } from "@/lib/i18n/offeredLocales";
import { useI18n } from "@/components/i18n/I18nProvider";

export function ConversationLanguageField({
  value,
  onChange,
  disabled = false,
}: {
  value: AppLocale;
  onChange: (code: AppLocale) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const { options, noneAvailable } = useOfferedLocales();
  const id = useId();
  return (
    <div className="grid gap-1">
      <label htmlFor={id} className="text-sm font-medium text-foreground">
        {t("prepctx.conversationLanguage")}
      </label>
      <p className="text-xs text-muted">{t("prepctx.conversationLanguageHelp")}</p>
      <select
        id={id}
        value={value}
        disabled={disabled || noneAvailable}
        onChange={(e) => onChange(e.target.value as AppLocale)}
        className="min-h-[44px] w-full max-w-xs rounded-lg border border-border bg-surface px-2 text-sm"
      >
        {options.map((l) => (
          <option key={l.code} value={l.code}>{l.unqualified ? `${l.nativeLabel} (${t("common.languageUnqualified")})` : l.nativeLabel}</option>
        ))}
      </select>
      {noneAvailable ? (
        <p role="note" data-testid="language-none-available" className="text-xs text-muted">{t("common.languagesNoneAvailable")}</p>
      ) : null}
    </div>
  );
}
