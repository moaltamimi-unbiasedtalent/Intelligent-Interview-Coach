"use client";

import type { ResponsePresentation } from "@/lib/api/types";
import { Markdown } from "@/components/coach/Markdown";
import { Disclosure } from "@/components/ui/Disclosure";

/**
 * Renders Mo's latest answer with progressive disclosure (Capstone P2/E2).
 *
 * ANSWER is always shown. When the presentation contract has DETAILS, Brief mode
 * collapses them behind "Show more" while Detailed mode shows them inline — the FULL
 * content is present in both modes (never truncated). A single, real NEXT STEP is
 * shown when the backend derived one. Sources/citations are rendered separately by
 * the conversation and remain discoverable in both modes.
 *
 * If no presentation contract is available (older turns, or a run without the field),
 * the caller renders the raw content instead — this component is only used for the
 * current answer.
 */
export function AgentAnswer({
  presentation,
  detailed,
}: {
  presentation: ResponsePresentation;
  detailed: boolean;
}) {
  const { answer, details, has_details, next_step } = presentation;

  return (
    <div className="space-y-3">
      <Markdown text={answer} />

      {next_step ? (
        <p className="text-sm">
          <span className="font-semibold text-foreground">Next step: </span>
          <span className="text-muted">{next_step.label}</span>
        </p>
      ) : null}

      {has_details ? (
        detailed ? (
          <div className="border-t border-border pt-3">
            <Markdown text={details} />
          </div>
        ) : (
          <Disclosure showLabel="Show more" hideLabel="Show less">
            <Markdown text={details} />
          </Disclosure>
        )
      ) : null}
    </div>
  );
}
