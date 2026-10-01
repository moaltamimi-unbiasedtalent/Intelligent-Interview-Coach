"use client";

import type { CareerChatResponse } from "@/lib/api/types";
import { CoachMessage } from "@/components/coach/CoachMessage";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { useT } from "@/components/i18n/I18nProvider";
import { toSupportedLocale, DEFAULT_APP_LOCALE } from "@/lib/i18n/locales";
import { translate } from "@/lib/i18n/catalog";

/**
 * Renders a grounded Career response inside a coach turn. Preserves the backend's
 * insufficient-evidence behaviour: when the answer has no supporting evidence we
 * add a calm note — we never fabricate confidence or a readiness score.
 *
 * LANGUAGE OWNERSHIP (P10B-W9.7A): the labels below ("Career evidence: n sources", "Source", the
 * screen-reader list) are Ask4Mo UI chrome and follow the INTERFACE language (`t`). The first-person
 * insufficient-evidence note is Mo-voiced deterministic text standing in for Mo's own prose, so it follows
 * the Mo CONVERSATION language (the same language the backend now writes the answer in). The two are
 * independent settings; source titles/URLs and the answer text are rendered verbatim.
 */
export function CareerAnswer({ response }: { response: CareerChatResponse }) {
  const t = useT();
  const conversation =
    toSupportedLocale(useAuthOptional()?.account?.conversation_language ?? null) ?? DEFAULT_APP_LOCALE;
  const sourceCount = response.sources.length || response.citations.length;
  const sourceNames = response.sources
    .map((s) => s.title || s.occupation_title)
    .filter(Boolean) as string[];

  return (
    <CoachMessage from="coach">
      <p className="whitespace-pre-wrap">{response.answer}</p>

      {!response.has_evidence ? (
        <p className="mt-3 text-sm text-muted">
          {translate(conversation, "coach.insufficientEvidence")}
        </p>
      ) : null}

      {sourceCount > 0 ? (
        <div className="mt-3 text-sm text-muted">
          <details>
            <summary className="cursor-pointer text-foreground">
              {sourceCount === 1
                ? t("prepare.evidenceSourcesOne")
                : t("prepare.evidenceSourcesOther", { n: sourceCount })}
            </summary>
            <ul className="mt-2 space-y-1">
              {response.sources.map((s, i) => (
                <li key={i}>
                  {s.source_url ? (
                    <a
                      href={s.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent underline-offset-2 hover:underline"
                    >
                      {s.title || s.occupation_title || s.source_url}
                    </a>
                  ) : (
                    <span>{s.title || s.occupation_title || t("prepare.sourceUntitled")}</span>
                  )}
                  {s.reference_year ? <span className="text-muted"> · {s.reference_year}</span> : null}
                </li>
              ))}
              {response.sources.length === 0 && response.citations.length > 0
                ? response.citations.map((c, i) => (
                    <li key={`c${i}`}>{c.title || c.source || t("prepare.sourceUntitled")}</li>
                  ))
                : null}
            </ul>
          </details>
          {sourceNames.length > 0 ? (
            <p className="sr-only">{t("prepare.sourcesAria", { names: sourceNames.join(", ") })}</p>
          ) : null}
        </div>
      ) : null}
    </CoachMessage>
  );
}
