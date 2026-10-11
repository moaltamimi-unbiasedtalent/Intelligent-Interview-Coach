"use client";

// Interactive workflow (v4.4). One ordered rail replaces the earlier orbit diagram, whose hand-positioned
// arrows could drift away from the nodes. The same sequence works on desktop and as a horizontal scroller on
// small screens. Keyboard behaviour follows the tabs pattern and the detail panel explains the selected stage.

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
    [`workflow.${active}Do`, "gettingStarted.factYouDo"],
    [`workflow.${active}Ask4mo`, "gettingStarted.factAsk4mo"],
    [`workflow.${active}Private`, "gettingStarted.factPrivate"],
    [`workflow.${active}Next`, "gettingStarted.factNext"],
  ];

  return (
    <div data-testid="workflow-map">
      <div className="overflow-hidden rounded-[2rem] bg-[#183f42] p-5 text-white shadow-soft md:p-8">
        <div className="mb-7 flex flex-wrap items-end justify-between gap-3">
          <p className="max-w-xl text-sm leading-relaxed text-white/70">{t("gettingStarted.workflowLead")}</p>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/55">{t("gettingStarted.workflowStep", { n: idx + 1, total: JOURNEY_STAGES.length })}</p>
        </div>
        <div className="-mx-2 overflow-x-auto px-2 pb-3">
        <div
          role="tablist"
          aria-label={t("gettingStarted.workflowListLabel")}
          aria-orientation="horizontal"
          onKeyDown={onKeyDown}
          data-testid="workflow-sequence"
          className="grid min-w-[64rem] grid-cols-7 gap-3"
        >
          {JOURNEY_STAGES.map((stage, index) => {
            const selected = stage === active;
            return (
              <div key={stage} className="relative">
                {index < JOURNEY_STAGES.length - 1 ? (
                  <span aria-hidden="true" className="pointer-events-none absolute left-[calc(50%+1.75rem)] right-[-1.45rem] top-7 z-0 flex items-center">
                    <span className="h-px flex-1 bg-white/30" />
                    <span className="-ml-px h-2 w-2 rotate-45 border-r border-t border-white/50" />
                  </span>
                ) : null}
                <button
                  ref={(el) => { refs.current[stage] = el; }}
                  type="button"
                  role="tab"
                  id={`wf-tab-${stage}`}
                  aria-label={t(`workflow.${stage}Title`)}
                  aria-selected={selected}
                  aria-controls="wf-panel"
                  tabIndex={selected ? 0 : -1}
                  onClick={() => select(stage)}
                  className="group relative z-10 flex w-full flex-col items-center gap-3 rounded-xl px-1 py-1 text-center text-sm font-semibold text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white"
                >
                  <span aria-hidden="true" className={cn(
                    "grid h-14 w-14 place-items-center rounded-full border text-base font-bold transition motion-reduce:transition-none",
                    selected ? "scale-110 border-white bg-white text-[#183f42] shadow-lg" : "border-white/30 bg-white/10 text-white group-hover:border-white/70 group-hover:bg-white/15",
                  )}>{index + 1}</span>
                  <span className={cn("max-w-[8rem] leading-tight", selected ? "text-white" : "text-white/75 group-hover:text-white")}>{t(`workflow.${stage}Title`)}</span>
                </button>
              </div>
            );
          })}
        </div>
        </div>
      </div>

      <div
        id="wf-panel"
        role="tabpanel"
        aria-labelledby={`wf-tab-${active}`}
        tabIndex={0}
        className="mt-4 overflow-hidden rounded-[1.5rem] border border-border bg-surface shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        <div className="border-b border-border bg-surface-2 px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">
            {t("gettingStarted.workflowStep", { n: idx + 1, total: JOURNEY_STAGES.length })}
          </p>
          <h3 className="mt-1 text-xl font-semibold">{t(`workflow.${active}Title`)}</h3>
        </div>
        <dl className="grid gap-px bg-border sm:grid-cols-2">
          {facts.map(([valueKey, labelKey]) => (
            <div key={labelKey} className="bg-surface p-5">
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{t(labelKey)}</dt>
              <dd className="mt-2 text-sm leading-relaxed text-foreground">{t(valueKey)}</dd>
            </div>
          ))}
        </dl>
      </div>

      <noscript>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/images/ask4mo/ask4mo-v4-workflow-map.svg" alt={t("gettingStarted.workflowFallbackAlt")} className="mt-4 h-auto w-full rounded-lg border border-border" />
      </noscript>
    </div>
  );
}
