"use client";

import { useState } from "react";
import type { HumanDecisionRequest, PendingHumanAction } from "@/lib/api/types";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { memoryCategoryLabel } from "./labels";

interface CardProps {
  action: PendingHumanAction;
  busy: boolean;
  onDecision: (decision: HumanDecisionRequest) => void;
}

/** Dispatches a pending HITL action to the right first-class approval card. */
export function PendingHumanActionCard({ action, busy, onDecision }: CardProps) {
  if (action.type === "confirm_role") return <RoleConfirmationCard action={action} busy={busy} onDecision={onDecision} />;
  if (action.type === "approve_memory") return <MemoryApprovalCard action={action} busy={busy} onDecision={onDecision} />;
  if (action.type === "approve_practice_handoff") return <PracticeHandoffCard action={action} busy={busy} onDecision={onDecision} />;
  return null;
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <Card className="border-accent">
      <CardBody>
        <div role="group" aria-label="Your input is needed" tabIndex={-1}>
          {children}
        </div>
      </CardBody>
    </Card>
  );
}

export function RoleConfirmationCard({ action, busy, onDecision }: CardProps) {
  const [selected, setSelected] = useState<string>("");
  return (
    <Shell>
      <p className="font-medium">{action.message}</p>
      <fieldset className="mt-3 grid gap-2" disabled={busy}>
        <legend className="sr-only">Choose the role you are preparing for</legend>
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
          Confirm role
        </Button>
      </div>
    </Shell>
  );
}

export function MemoryApprovalCard({ action, busy, onDecision }: CardProps) {
  const category = String(action.data.category ?? "");
  const summary = String(action.data.summary ?? "");
  const targetRole = action.data.target_role ? String(action.data.target_role) : null;
  return (
    <Shell>
      <p className="font-medium">{action.message}</p>
      <div className="mt-3 rounded-lg border border-border bg-surface-2 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>{memoryCategoryLabel(category)}</Badge>
          {targetRole ? <Badge tone="neutral">{targetRole}</Badge> : null}
        </div>
        <p className="mt-2 break-words text-sm">{summary}</p>
      </div>
      <div className="mt-3 flex gap-2">
        <Button size="sm" disabled={busy} onClick={() => onDecision({ action_id: action.action_id, decision: "approve" })}>
          Save
        </Button>
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => onDecision({ action_id: action.action_id, decision: "reject" })}>
          Not now
        </Button>
      </div>
    </Shell>
  );
}

export function PracticeHandoffCard({ action, busy, onDecision }: CardProps) {
  const role = action.data.target_role ? String(action.data.target_role) : null;
  const priorities = typeof action.data.priority_count === "number" ? action.data.priority_count : null;
  const questions = typeof action.data.question_count === "number" ? action.data.question_count : null;
  return (
    <Shell>
      <p className="font-medium">{action.message}</p>
      <ul className="mt-2 flex flex-wrap gap-2 text-xs text-muted">
        {role ? <li><Badge tone="neutral">{role}</Badge></li> : null}
        {priorities !== null ? <li><Badge>{priorities} priorities</Badge></li> : null}
        {questions !== null ? <li><Badge>{questions} questions</Badge></li> : null}
      </ul>
      <div className="mt-3 flex gap-2">
        <Button size="sm" disabled={busy} onClick={() => onDecision({ action_id: action.action_id, decision: "approve" })}>
          Start practice
        </Button>
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => onDecision({ action_id: action.action_id, decision: "reject" })}>
          Not now
        </Button>
      </div>
    </Shell>
  );
}
