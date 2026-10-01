"use client";

import { useState } from "react";
import type { HumanDecisionRequest, MemoryCategory, PendingHumanAction, PracticeHandoffSummary } from "@/lib/api/types";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input, Textarea } from "@/components/ui/Field";
import { CATEGORIES, CATEGORY_LABEL } from "@/components/memory/MemoryManager";
import { memoryCategoryLabel } from "./labels";
import { useT } from "@/components/i18n/I18nProvider";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

interface CardProps {
  action: PendingHumanAction;
  busy: boolean;
  onDecision: (decision: HumanDecisionRequest) => void;
}

/** Candidate-facing source labels for handoff provenance (never technical tool names). */
export function handoffSourceLabel(source: string, t: Translate): string {
  switch (source) {
    case "confirmed_role": return t("prepare.sourceConfirmedRole");
    case "job_analysis": return t("prepare.sourceJobAnalysis");
    case "gap_analysis": return t("prepare.sourceGapAnalysis");
    case "preparation_plan": return t("prepare.sourcePreparationPlan");
    case "question_generator": return t("prepare.sourceQuestionGenerator");
    default: return t("prepare.sourceDefault");
  }
}

/** Dispatches a pending HITL action to the right first-class approval card. */
export function PendingHumanActionCard({
  action, busy, onDecision, handoffSummary,
}: CardProps & { handoffSummary?: PracticeHandoffSummary | null }) {
  if (action.type === "confirm_role") return <RoleConfirmationCard action={action} busy={busy} onDecision={onDecision} />;
  if (action.type === "approve_memory") return <MemoryApprovalCard action={action} busy={busy} onDecision={onDecision} />;
  if (action.type === "approve_practice_handoff") return <PracticeHandoffCard action={action} busy={busy} onDecision={onDecision} summary={handoffSummary} />;
  return null;
}

function Shell({ children }: { children: React.ReactNode }) {
  const t = useT();
  return (
    <Card className="border-accent">
      <CardBody>
        <div role="group" aria-label={t("prepare.inputNeededAria")} tabIndex={-1}>
          {children}
        </div>
      </CardBody>
    </Card>
  );
}

export function RoleConfirmationCard({ action, busy, onDecision }: CardProps) {
  const t = useT();
  const [selected, setSelected] = useState<string>("");
  return (
    <Shell>
      <p className="font-medium">{action.message}</p>
      <fieldset className="mt-3 grid gap-2" disabled={busy}>
        <legend className="sr-only">{t("prepare.chooseRole")}</legend>
        {action.options.map((role) => (
          <label key={role} className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm hover:bg-surface-2">
            <input
              type="radio"
              name="role-option"
              value={role}
              checked={selected === role}
              onChange={() => setSelected(role)}
            />
            <span>{role}</span>
          </label>
        ))}
      </fieldset>
      <div className="mt-3">
        <Button
          size="sm"
          disabled={busy || !selected}
          onClick={() => onDecision({ action_id: action.action_id, decision: "select", selected_role: selected })}
        >
          {t("prepare.confirmRole")}
        </Button>
      </div>
    </Shell>
  );
}

export function MemoryApprovalCard({ action, busy, onDecision }: CardProps) {
  const t = useT();
  const origCategory = (String(action.data.category ?? "recurring_gap")) as MemoryCategory;
  const origSummary = String(action.data.summary ?? "");
  const origRole = action.data.target_role ? String(action.data.target_role) : "";

  const [editing, setEditing] = useState(false);
  const [category, setCategory] = useState<MemoryCategory>(origCategory);
  const [summary, setSummary] = useState(origSummary);
  const [role, setRole] = useState(origRole);

  const approveEdited = () =>
    onDecision({
      action_id: action.action_id,
      decision: "approve",
      memory: { category, summary: summary.trim(), target_role: role.trim() || null },
    });

  return (
    <Shell>
      <p className="font-medium">{t("prepare.whatRemembered")}</p>
      {editing ? (
        <div className="mt-3 grid gap-3">
          <div>
            <label htmlFor="approve-cat" className="block text-sm text-muted">{t("prepare.category")}</label>
            <select id="approve-cat" value={category} disabled={busy}
              onChange={(e) => setCategory(e.target.value as MemoryCategory)}
              className="w-full rounded-lg border border-border bg-surface px-3.5 py-3">
              {CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="approve-sum" className="block text-sm text-muted">{t("prepare.memory")}</label>
            <Textarea id="approve-sum" value={summary} maxLength={500} disabled={busy}
              onChange={(e) => setSummary(e.target.value)} />
          </div>
          <div>
            <label htmlFor="approve-role" className="block text-sm text-muted">{t("prepare.forRoleOptional")}</label>
            <Input id="approve-role" value={role} maxLength={200} disabled={busy}
              onChange={(e) => setRole(e.target.value)} />
          </div>
          <p className="text-xs text-muted">{t("prepare.whyUseful")}</p>
          <div className="flex gap-2">
            <Button size="sm" disabled={busy || summary.trim().length === 0} onClick={approveEdited}>
              {t("prepare.save")}
            </Button>
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => setEditing(false)}>
              {t("prepare.cancel")}
            </Button>
          </div>
        </div>
      ) : (
        <>
          <dl className="mt-3 rounded-lg border border-border bg-surface-2 p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <dt className="sr-only">{t("prepare.category")}</dt>
              <dd><Badge>{memoryCategoryLabel(category)}</Badge></dd>
              {role ? <dd><Badge tone="neutral">{role}</Badge></dd> : null}
            </div>
            <dt className="mt-2 text-xs text-muted">{t("prepare.memory")}</dt>
            <dd className="break-words">{summary}</dd>
            <dt className="mt-2 text-xs text-muted">{t("prepare.why")}</dt>
            <dd className="text-xs text-muted">{t("prepare.usefulFuture")}</dd>
          </dl>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" disabled={busy}
              onClick={() => onDecision({ action_id: action.action_id, decision: "approve" })}>
              {t("prepare.approve")}
            </Button>
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => setEditing(true)}>
              {t("prepare.editBeforeSaving")}
            </Button>
            <Button size="sm" variant="ghost" disabled={busy}
              onClick={() => onDecision({ action_id: action.action_id, decision: "reject" })}>
              {t("prepare.reject")}
            </Button>
          </div>
        </>
      )}
    </Shell>
  );
}

export function PracticeHandoffCard({ action, busy, onDecision, summary }: CardProps & { summary?: PracticeHandoffSummary | null }) {
  const t = useT();
  // Prefer the safe provenance summary (what/where each item came from); fall back to
  // the pending action's coarse counts. Only actually-present fields are shown.
  const role = summary?.target_role?.value ?? (action.data.target_role ? String(action.data.target_role) : null);
  const roleSource = summary?.target_role?.source;
  const focus = summary?.focus_areas ?? [];
  const focusSource = focus[0]?.source;
  const questionCount = summary?.question_count
    ?? (typeof action.data.question_count === "number" ? action.data.question_count : null);

  return (
    <Shell>
      <h3 className="font-medium">{t("prepare.readyToPractise")}</h3>
      {role ? <p className="mt-1 text-lg font-semibold">{role}</p> : null}
      <p className="mt-3 text-sm text-muted">{t("prepare.moPreparedFocus")}</p>
      <ul className="mt-2 grid gap-1.5 text-sm">
        {role ? (
          <li className="flex items-start gap-2">
            <span aria-hidden>✓</span>
            <span>{t("prepare.roleLabel")} <span className="text-muted">{roleSource ? handoffSourceLabel(roleSource, t) : t("prepare.sourceDefault")}</span></span>
          </li>
        ) : null}
        {focus.length ? (
          <li className="flex items-start gap-2">
            <span aria-hidden>✓</span>
            <span>
              {focusSource === "preparation_plan" ? t("prepare.preparationFocus") : t("prepare.priorityAreas")}{" "}
              <span className="text-muted">{handoffSourceLabel(focusSource ?? "gap_analysis", t)}</span>
              <span className="mt-1 flex flex-wrap gap-1.5">
                {focus.map((f, i) => <Badge key={i} tone="neutral">{f.value}</Badge>)}
              </span>
            </span>
          </li>
        ) : null}
        {questionCount ? (
          <li className="flex items-start gap-2">
            <span aria-hidden>✓</span>
            <span>{t("prepare.practiceQuestionsCount", { count: questionCount })} <span className="text-muted">{t("prepare.sourceQuestionGenerator")}</span></span>
          </li>
        ) : null}
      </ul>
      <div className="mt-3 flex gap-2">
        <Button size="sm" disabled={busy} onClick={() => onDecision({ action_id: action.action_id, decision: "approve" })}>
          {t("prepare.startPractice")}
        </Button>
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => onDecision({ action_id: action.action_id, decision: "reject" })}>
          {t("prepare.notYet")}
        </Button>
      </div>
    </Shell>
  );
}
