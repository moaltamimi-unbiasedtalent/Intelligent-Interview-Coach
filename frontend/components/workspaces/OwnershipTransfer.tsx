"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { useI18n } from "@/components/i18n/I18nProvider";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input } from "@/components/ui/Field";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { OwnershipTransfer } from "@/lib/api/types";
import { workspaceErrorKey } from "./workspaceUi";

type FormerRole = "workspace_admin" | "workspace_member";

/** The role words used inside sentences ("you become an admin"). */
export function formerRoleKey(role: string): string {
  return role === "workspace_admin" ? "wsTransfer.keepAdmin" : "wsTransfer.keepMember";
}

/** Why proposing failed, as a localized key. Step-up refusals carry stable codes; everything else follows the shared workspace taxonomy. */
export function proposeErrorKey(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.code === "step_up_failed") return "wsTransfer.errStepUpFailed";
    if (e.code === "step_up_unavailable") return "wsTransfer.errStepUpUnavailable";
    if (e.status === 422) return "wsTransfer.errRecipient";
  }
  return workspaceErrorKey(e);
}

/**
 * The pending transfer, for BOTH parties, with what each choice means. The proposer can cancel; the recipient can decline. Accepting is deliberately NOT a button
 * here: it needs the one-time link from the email sent to the recipient's verified address (the accept page), so a pending banner alone can never move ownership.
 */
export function TransferBanner({ transfer, showWorkspace = false, busy, onCancel, onDecline }: {
  transfer: OwnershipTransfer;
  showWorkspace?: boolean;
  busy: boolean;
  onCancel: () => void;
  onDecline: () => void;
}) {
  const { t, formatDate } = useI18n();
  const date = transfer.expires_at ? formatDate(transfer.expires_at, { dateStyle: "medium" }) : "";
  const proposer = transfer.viewer_role === "proposer";
  const name = transfer.counterpart_label;
  return (
    <Card>
      <CardBody className="grid gap-2" data-testid={`transfer-banner-${proposer ? "proposer" : "recipient"}`}>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold">{t(proposer ? "wsTransfer.proposerTitle" : "wsTransfer.recipientTitle")}</h3>
          <Badge tone="medium">{t("wsTransfer.pendingBadge")}</Badge>
          {showWorkspace && transfer.workspace_name && <span className="text-sm text-muted">{transfer.workspace_name}</span>}
        </div>
        {proposer ? (
          <>
            <p className="text-sm">{t("wsTransfer.proposerBody", { name, date })}</p>
            <p className="text-sm">{t("wsTransfer.proposerKeeps", { name, role: t(formerRoleKey(transfer.former_owner_role)) })}</p>
            <p className="text-xs text-muted">{t("wsTransfer.cancelNote")}</p>
          </>
        ) : (
          <>
            <p className="text-sm">{t("wsTransfer.recipientBody", { name, date })}</p>
            <p className="text-sm">{t("wsTransfer.acceptFormerRole", { role: t(formerRoleKey(transfer.former_owner_role)) })}</p>
            <p className="text-xs text-muted">{t("wsTransfer.recipientHow")}</p>
          </>
        )}
        <div className="flex flex-wrap gap-2">
          {proposer
            ? <Button size="sm" variant="ghost" disabled={busy} onClick={onCancel}>{t("wsTransfer.cancelAction")}</Button>
            : <Button size="sm" variant="ghost" disabled={busy} onClick={onDecline}>{t("wsTransfer.declineAction")}</Button>}
          {showWorkspace && (
            <Link href={`/workspaces/${transfer.workspace_id}`}
              className="inline-flex min-h-[36px] items-center rounded border border-border px-3 text-sm font-semibold hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2">
              {t("wsTransfer.openWorkspace")}
            </Link>
          )}
        </div>
      </CardBody>
    </Card>
  );
}

/**
 * Propose a transfer to ONE member. Consequences are stated before anything is sent. Authorisation: the exact workspace name AND a fresh password confirmation
 * (the existing step-up; five minutes, this session only, not multi-factor). The password is held only in this component state and cleared on close.
 */
export function ProposeTransferDialog({ open, workspace, member, onClose, onProposed }: {
  open: boolean;
  workspace: { id: number; name: string };
  member: { user_id: number; label: string } | null;
  onClose: () => void;
  onProposed: (transfer: OwnershipTransfer) => void;
}) {
  const { t } = useI18n();
  const ids = useId();
  const [typed, setTyped] = useState("");
  const [password, setPassword] = useState("");
  const [keep, setKeep] = useState<FormerRole>("workspace_member");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => { setTyped(""); setPassword(""); setKeep("workspace_member"); setError(null); };
  const close = () => { if (busy) return; reset(); onClose(); };

  const submit = async () => {
    if (!member) return;
    if (typed.trim() !== workspace.name) { setError(t("wsMgmt.errValidation")); return; }
    if (!password) { setError(t("wsTransfer.errStepUpFailed")); return; }
    setBusy(true);
    setError(null);
    try {
      await api.workspaces.transferStepUp(password);
      const transfer = await api.workspaces.proposeTransfer(workspace.id, member.user_id, typed.trim(), keep);
      reset();
      onProposed(transfer);
    } catch (e) {
      setError(t(proposeErrorKey(e)));
    } finally {
      setPassword("");
      setBusy(false);
    }
  };

  const name = member?.label ?? "";
  const keepWord = t(formerRoleKey(keep));
  return (
    <ConfirmDialog
      open={open && member !== null}
      title={t("wsTransfer.proposeTitle", { name })}
      confirmLabel={t("wsTransfer.sendProposal")}
      busy={busy}
      error={error}
      onConfirm={() => void submit()}
      onCancel={close}
      testId="transfer-propose"
    >
      <div className="grid gap-3 text-sm">
        <p>{t("wsTransfer.proposeIntro", { name })}</p>
        <fieldset className="grid gap-1">
          <legend className="text-xs font-semibold">{t("wsTransfer.keepRoleLabel")}</legend>
          <label className="flex items-center gap-2">
            <input type="radio" name={`${ids}-keep`} checked={keep === "workspace_member"} onChange={() => setKeep("workspace_member")} />
            <span>{t("wsTransfer.keepMember")}</span>
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" name={`${ids}-keep`} checked={keep === "workspace_admin"} onChange={() => setKeep("workspace_admin")} />
            <span>{t("wsTransfer.keepAdmin")}</span>
          </label>
        </fieldset>
        <div>
          <p className="text-xs font-semibold">{t("wsTransfer.consequencesTitle")}</p>
          <ul className="mt-1 list-disc pl-5 text-muted">
            <li>{t("wsTransfer.consequenceNewOwner", { name })}</li>
            <li>{t("wsTransfer.consequenceYou", { role: keepWord })}</li>
            <li>{t("wsTransfer.consequenceShares")}</li>
            <li>{t("wsTransfer.consequenceExpiry", { name })}</li>
          </ul>
        </div>
        <div className="grid gap-1">
          <label htmlFor={`${ids}-name`} className="text-xs font-semibold">{t("wsTransfer.confirmNameLabel")}</label>
          <Input id={`${ids}-name`} value={typed} autoComplete="off" onChange={(e) => setTyped(e.target.value)} />
        </div>
        <div className="grid gap-1">
          <label htmlFor={`${ids}-pw`} className="text-xs font-semibold">{t("wsTransfer.passwordLabel")}</label>
          <Input id={`${ids}-pw`} type="password" value={password} autoComplete="current-password" maxLength={256} onChange={(e) => setPassword(e.target.value)} />
          <span className="text-xs text-muted">{t("wsTransfer.passwordHint")}</span>
        </div>
      </div>
    </ConfirmDialog>
  );
}
