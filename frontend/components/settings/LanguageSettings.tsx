"use client";

/**
 * Language settings (Capstone P3.5) — THREE independent controls, never merged:
 *   1. Interface language      — the UI language (persisted account + cookie).
 *   2. Mo conversation language — the language Mo coaches in (persisted account).
 *   3. Dictation language       — speech-to-text recognition locale (P3, per device).
 *
 * Changing any of these NEVER changes labour-market geography, and one control never
 * silently changes another. Language access is available to every tier (not premium).
 */

import { useId, useState } from "react";
import { api } from "@/lib/api/client";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { useI18n } from "@/components/i18n/I18nProvider";
import { APP_LOCALES, type AppLocale, toSupportedLocale } from "@/lib/i18n/locales";
import { DICTATION_LANGUAGES } from "@/components/ui/DictationControl";
import { useDictationLanguage } from "@/lib/speech/useDictationLanguage";

function Row({
  labelId,
  label,
  help,
  children,
}: {
  labelId: string;
  label: string;
  help: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <label id={labelId} className="block text-sm font-medium text-foreground">
        {label}
      </label>
      <p className="text-sm text-muted">{help}</p>
      <div className="pt-1">{children}</div>
    </div>
  );
}

const selectClass =
  "rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent";

export function LanguageSettings() {
  const { t, locale, setLocale } = useI18n();
  const auth = useAuthOptional();
  const [dictationLang, setDictationLang] = useDictationLanguage();
  const [conversation, setConversation] = useState<AppLocale>(
    toSupportedLocale(auth?.account?.conversation_language ?? null) ?? "en",
  );
  const ifaceId = useId();
  const convId = useId();
  const dictId = useId();

  const changeConversation = async (value: AppLocale) => {
    setConversation(value);
    if (auth?.status === "authenticated") {
      try {
        await api.auth.updatePreferences({ conversation_language: value });
        await auth.refresh?.();
      } catch {
        /* keep local selection */
      }
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-base font-semibold">{t("settings.language")}</h2>
        <p className="mt-1 text-sm text-muted">{t("settings.languageIndependenceNote")}</p>
      </div>

      <Row labelId={ifaceId} label={t("settings.interfaceLanguage")} help={t("settings.interfaceLanguageHelp")}>
        <select
          aria-labelledby={ifaceId}
          className={selectClass}
          value={locale}
          onChange={(e) => setLocale(e.target.value as AppLocale)}
        >
          {APP_LOCALES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.nativeLabel}
            </option>
          ))}
        </select>
      </Row>

      <Row labelId={convId} label={t("settings.conversationLanguage")} help={t("settings.conversationLanguageHelp")}>
        <select
          aria-labelledby={convId}
          className={selectClass}
          value={conversation}
          onChange={(e) => changeConversation(e.target.value as AppLocale)}
        >
          {APP_LOCALES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.nativeLabel}
            </option>
          ))}
        </select>
      </Row>

      <Row labelId={dictId} label={t("settings.dictationLanguage")} help={t("settings.dictationLanguageHelp")}>
        <select
          aria-labelledby={dictId}
          className={selectClass}
          value={dictationLang}
          onChange={(e) => setDictationLang(e.target.value)}
        >
          {DICTATION_LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>
      </Row>
    </div>
  );
}
