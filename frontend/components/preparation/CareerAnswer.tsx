import type { CareerChatResponse } from "@/lib/api/types";
import { CoachMessage } from "@/components/coach/CoachMessage";

/**
 * Renders a grounded Career response inside a coach turn. Preserves the backend's
 * insufficient-evidence behaviour: when the answer has no supporting evidence we
 * add a calm note — we never fabricate confidence or a readiness score.
 */
export function CareerAnswer({ response }: { response: CareerChatResponse }) {
  const sourceCount = response.sources.length || response.citations.length;
  const sourceNames = response.sources
    .map((s) => s.title || s.occupation_title)
    .filter(Boolean) as string[];

  return (
    <CoachMessage from="coach">
      <p className="whitespace-pre-wrap">{response.answer}</p>

      {!response.has_evidence ? (
        <p className="mt-3 text-sm text-muted">
          I don&rsquo;t have enough reliable evidence to answer that confidently.
          Adding a job description or more about the role can help.
        </p>
      ) : null}

      {sourceCount > 0 ? (
        <div className="mt-3 text-sm text-muted">
          <details>
            <summary className="cursor-pointer text-foreground">
              Career evidence: {sourceCount} source{sourceCount === 1 ? "" : "s"}
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
                    <span>{s.title || s.occupation_title || "source"}</span>
                  )}
                  {s.reference_year ? <span className="text-muted"> · {s.reference_year}</span> : null}
                </li>
              ))}
              {response.sources.length === 0 && response.citations.length > 0
                ? response.citations.map((c, i) => (
                    <li key={`c${i}`}>{c.title || c.source || "source"}</li>
                  ))
                : null}
            </ul>
          </details>
          {sourceNames.length > 0 ? (
            <p className="sr-only">Sources: {sourceNames.join(", ")}</p>
          ) : null}
        </div>
      ) : null}
    </CoachMessage>
  );
}
