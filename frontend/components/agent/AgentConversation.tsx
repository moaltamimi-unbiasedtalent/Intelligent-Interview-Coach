"use client";

import type { AgentConversationMessage, AgentRunResponse } from "@/lib/api/types";
import { Markdown } from "@/components/coach/Markdown";
import { AgentSources } from "./AgentSources";
import { activityFromEvents } from "./labels";

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
  return (
    <div className="space-y-4">
      <ol className="space-y-4" aria-label="Coaching conversation">
        {messages.map((m, i) => (
          <li key={i} className={m.role === "user" ? "flex justify-end" : ""}>
            <div
              className={
                m.role === "user"
                  ? "max-w-[85%] rounded-2xl bg-accent px-4 py-2.5 text-accent-foreground"
                  : "max-w-[92%] rounded-2xl bg-surface-2 px-4 py-2.5"
              }
            >
              {m.role === "user" ? (
                <p className="whitespace-pre-wrap break-words text-sm">{m.content}</p>
              ) : (
                <Markdown text={m.content} />
              )}
            </div>
          </li>
        ))}
      </ol>

      {/* Latest evidence lives under the most recent assistant answer. */}
      {run && !busy && run.sources.length ? <AgentSources sources={run.sources} /> : null}

      {busy ? (
        <div role="status" aria-live="polite" className="flex items-center gap-2 text-sm text-muted">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" aria-hidden />
          {run ? activityFromEvents(run.events) : "Understanding your request…"}
        </div>
      ) : null}
    </div>
  );
}
