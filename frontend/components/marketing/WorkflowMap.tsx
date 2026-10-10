"use client";

// Interactive workflow map (v4). Accessible HTML (tabs pattern: arrow keys, Home/End, roving tabindex), so every
// label is translated. The static SVG is only a no-script fallback. Each stage exposes what the candidate does,
// what Ask4Mo contributes, what stays private and the next action.

import { useRef, useState } from "react";

import { useT } from "@/components/i18n/I18nProvider";
import { JOURNEY_STAGES, type JourneyStage } from "@/lib/journey";
import { cn } from "@/lib/utils";

export function WorkflowMap() {
  const t = useT();
  const [active, setActive] = useState<JourneyStage>("opportunity");
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const idx = JOURNEY_STAGES.indexOf(active);

  const select = (stage: JourneyStage, focus = false) => {
    setActive(stage);
    if (focus) refs.current[stage]?.focus();
  };
  const onKeyDown = (e: React.KeyboardEvent) => {
    let next = idx;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") next = (idx + 1) % JOURNEY_STAGES.length;
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = (idx - 1 + JOURNEY_STAGES.length) % JOURNEY_STAGES.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = JOURNEY_STAGES.length - 1;
    else return;
    e.preventDefault();
    select(JOURNEY_STAGES[next], true);
  };

  const facts: [string, string][] = [
    ["workflow." + active + "Do", "gettingStarted.factYouDo"],
    ["workflow." + active + "Ask4mo", "gettingStarted.factAsk4mo"],
    ["workflow." + active + "Private", "gettingStarted.factPrivate"],
    ["workflow." + active + "Next", "gettingStarted.factNext"],
  ];

  return (
    <div data-testid="workflow-map">
      <div className="-mx-4 overflow-x-auto px-4 pb-2">
        <div role="tablist" aria-label={t("gettingStarted.workflowListLabel")} aria-orientation="horizontal" onKeyDown={onKeyDown}
             className="flex min-w-max items-stretch gap-2">
          {JOURNEY_STAGES.map((stage, i) => {
            const selected = stage === active;
            return (
              <button
                key={stage}
                ref={(el) => { refs.current[stage] = el; }}
                type="button"
                role="tab"
                id={`wf-tab-${stage}`}
                aria-selected={selected}
                aria-controls="wf-panel"
                tabIndex={selected ? 0 : -1}
                onClick={() => select(stage)}
                className={cn(
                  "flex min-w-[8.5rem] items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                  selected ? "border-accent bg-accent text-accent-foreground" : "border-border bg-surface text-foreground hover:bg-surface-2",
                )}
              >
                <span aria-hidden="true" className={cn("grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-bold", selected ? "bg-accent-foreground/20" : "bg-surface-2")}>{i + 1}</span>
                <span>{t(`workflow.${stage}Title`)}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div id="wf-panel" role="tabpanel" aria-labelledby={`wf-tab-${active}`} tabIndex={0}
           className="mt-3 rounded-lg border border-border bg-surface p-5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
        <p className="text-xs font-semibold uppercase tracking-wide text-accent">
          {t("gettingStarted.workflowStep", { n: idx + 1, total: JOURNEY_STAGES.length })}
        </p>
        <h3 className="mt-1 text-lg font-semibold">{t(`workflow.${active}Title`)}</h3>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2">
          {facts.map(([valueKey, labelKey]) => (
            <div key={labelKey}>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{t(labelKey)}</dt>
              <dd className="mt-1 text-sm text-foreground">{t(valueKey)}</dd>
            </div>
          ))}
        </dl>
      </div>

      {/* Static fallback only (no script): the translated, interactive version above is the real experience. */}
      <noscript>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/images/ask4mo/ask4mo-v4-workflow-map.svg" alt={t("gettingStarted.workflowFallbackAlt")} className="mt-4 h-auto w-full rounded-lg border border-border" />
      </noscript>
    </div>
  );
}
