"use client";

import type { AgentConversationMessage, AgentRunResponse } from "@/lib/api/types";
import { Markdown } from "@/components/coach/Markdown";
import { AgentSources } from "./AgentSources";
import { AgentAnswer } from "./AgentAnswer";
import { activityFromEvents } from "./labels";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { VoicePlaybackControl } from "@/components/ui/VoicePlaybackControl";
import { isSpeechOutputLocale, toSpeechLocale } from "@/lib/speech/ttsLocales";
import { useT } from "@/components/i18n/I18nProvider";

/** The coaching conversation: safe user/assistant turns, latest evidence, and a
 * live activity line while the agent is working (observable status, not reasoning). */
export function AgentConversation({
  run,
  busy,
  messages,
}: {
  run: AgentRunResponse | null;
  busy: boolean;
  messages: AgentConversationMessage[];
}) {
  const t = useT();
  const auth = useAuthOptional();
  const responseDetail = auth?.responseDetail ?? "brief";
  // Speech-output locale follows the Mo conversation language (§11), never the UI locale
  // and never career geography (§12). Falls back to en-US.
  const speechLang = toSpeechLocale(auth?.account?.conversation_language);
  // Languages without speech support (e.g. Russian) get no Listen control: never an English voice
  // reading another language. The text stays on screen.
  const speechSupported = isSpeechOutputLocale(auth?.account?.conversation_language);
  // Apply progressive disclosure to the CURRENT answer only (the last assistant turn),
  // and only when the run carries a presentation contract with real details and is not
  // mid-flight/awaiting a human decision. Everything else renders in full — no content
  // is ever hidden or truncated.
  const lastAssistantIndex = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return i;
    }
    return -1;
  })();
  const presentation =
    run && !busy && !run.awaiting_human_input ? run.presentation ?? null : null;

  return (
    <div className="space-y-4">
      <ol className="space-y-4" aria-label={t("prepare.coachingConversation")}>
        {messages.map((m, i) => {
          const usePresentation =
            m.role === "assistant" &&
            i === lastAssistantIndex &&
            presentation != null &&
            presentation.has_details;
          // Compute the body as a variable (rather than an inline ternary between JSX
          // tags) so no code expression is rendered as visible-looking text.
          let body: React.ReactNode;
          if (m.role === "user") {
            body = <p className="whitespace-pre-wrap break-words text-sm">{m.content}</p>;
          } else if (usePresentation && presentation) {
            body = <AgentAnswer presentation={presentation} detailed={responseDetail === "detailed"} />;
          } else {
            body = <Markdown text={m.content} />;
          }
          return (
            <li key={i} className={m.role === "user" ? "flex justify-end" : ""}>
              <div
                className={
                  m.role === "user"
                    ? "max-w-[85%] rounded-2xl bg-accent px-4 py-2.5 text-accent-foreground"
                    : "max-w-[92%] rounded-2xl bg-surface-2 px-4 py-2.5"
                }
              >
                {body}
                {/* Listen to the PRIMARY visible answer (brief-first, §6). Assistant turns
                    only; speaks the same text the candidate can read. */}
                {m.role === "assistant" && m.content.trim() && speechSupported ? (
                  <div className="mt-1.5">
                    <VoicePlaybackControl
                      text={usePresentation && presentation ? presentation.answer : m.content}
                      lang={speechLang}
                    />
                  </div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>

      {/* Latest evidence lives under the most recent assistant answer. */}
      {run && !busy && run.sources.length ? <AgentSources sources={run.sources} /> : null}

      {busy ? (
        <div role="status" aria-live="polite" className="flex items-center gap-2 text-sm text-muted">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" aria-hidden />
          {run ? activityFromEvents(run.events) : t("prepare.moUnderstanding")}
        </div>
      ) : null}
    </div>
  );
}
