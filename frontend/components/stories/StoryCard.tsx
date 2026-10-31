"use client";

/**
 * One story in the Story Bank (04A). Shows how it is verified in plain words (evidence, the candidate's own practice
 * answer, the candidate's own confirmation, or nothing), the STAR text, quality prompts that only ask the candidate to
 * add what is missing, usage, evidence links and the actions: edit, archive/restore, confirm, link evidence, delete.
 * Nothing is labelled verified without live evidence; a confirmation is labelled as the candidate's own attestation.
 */

import { useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { Opportunity, StoryOut } from "@/lib/api/types";
import { useI18n } from "@/components/i18n/I18nProvider";
import { Badge } from "@/components/ui/Badge";
import { Alert } from "@/components/ui/Alert";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EvidenceLinker } from "@/components/stories/EvidenceLinker";
import { StoryShare } from "@/components/stories/StoryShare";
import { QUALITY_KEY, STATUS_KEY, VERIFICATION_HELP_KEY, VERIFICATION_KEY, VERIFICATION_TONE, verificationOf } from "@/components/stories/storyVocab";

const STAR = [
  ["situation", "storyBank.fieldSituation"], ["task", "storyBank.fieldTask"], ["action", "storyBank.fieldAction"], ["result", "storyBank.fieldResult"],
] as const;

export function StoryCard({
  story, opportunities, onChanged, onEdit, onDeleted,
}: {
  story: StoryOut;
  opportunities: Opportunity[];
  onChanged: (s: StoryOut) => void;
  onEdit: (s: StoryOut) => void;
  onDeleted: (id: number) => void;
}) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [showLink, setShowLink] = useState(false);
  const [showShare, setShowShare] = useState(false);
  const v = verificationOf(story);
  const archived = Boolean(story.archived_at);
  const opportunity = opportunities.find((o) => o.id === story.opportunity_id);
  const claimIds = story.evidence_claim_ids;
  const answerIds = story.evidence_answer_ids ?? [];

  async function run(action: () => Promise<StoryOut>) {
    setBusy(true);
    setError(null);
    try { onChanged(await action()); } catch (e) { setError(e instanceof ApiError ? e.userMessage : t("storyBank.actionError")); } finally { setBusy(false); }
  }

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await api.stories.remove(story.id);
      onDeleted(story.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.userMessage : t("storyBank.actionError"));
      setConfirmDelete(false);
      setBusy(false);
    }
  }

  const link = "text-sm text-accent hover:underline disabled:opacity-50";
  return (
    <li className="rounded-lg border border-border p-3 text-sm" data-testid={`story-${story.id}`} aria-label={story.title}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-base font-semibold text-foreground">{story.title}</h3>
        <div className="flex flex-wrap gap-2">
          <Badge>{t(STATUS_KEY[story.status] ?? "documents.stUserCreated")}</Badge>
          <Badge tone={VERIFICATION_TONE[v]}>{t(VERIFICATION_KEY[v])}</Badge>
          {archived ? <Badge>{t("storyBank.archivedBadge")}</Badge> : null}
        </div>
      </div>
      <p className="mt-1 text-xs text-muted" data-testid="verification-help">{t(VERIFICATION_HELP_KEY[v])}</p>
      {archived ? <p className="mt-1 text-xs text-muted">{t("storyBank.archivedNote")}</p> : null}
      {error ? <Alert tone="danger" className="mt-2">{error}</Alert> : null}

      {story.competencies.length > 0 ? (
        <ul className="mt-2 flex flex-wrap gap-1.5" aria-label={t("storyBank.fieldTags")}>
          {story.competencies.map((c) => <li key={c} className="rounded-full border border-border px-2 py-0.5 text-xs text-muted">{c}</li>)}
        </ul>
      ) : null}
      {opportunity ? <p className="mt-2 text-xs text-muted">{t("storyBank.linkedOpportunity", { title: opportunity.title })}</p> : null}

      <dl className="mt-2 grid gap-1.5">
        {STAR.map(([f, key]) => (story[f] ? (
          <div key={f}><dt className="text-xs font-semibold uppercase tracking-wide text-muted">{t(key)}</dt><dd className="break-words text-foreground">{story[f]}</dd></div>
        ) : null))}
      </dl>

      {!archived && (story.quality_prompts ?? []).length > 0 ? (
        <div className="mt-2 rounded border border-border bg-surface-2 p-2" data-testid="quality-prompts">
          <p className="text-xs font-semibold text-foreground">{t("storyBank.qualityTitle")}</p>
          <ul className="mt-1 list-disc pl-5 text-xs text-muted">
            {(story.quality_prompts ?? []).map((q) => <li key={q}>{t(QUALITY_KEY[q] ?? "storyBank.q_no_tags")}</li>)}
          </ul>
        </div>
      ) : null}

      <p className="mt-2 text-xs text-muted">
        {(story.use_count ?? 0) > 0 ? t("storyBank.usedN", { n: story.use_count ?? 0 }) : t("storyBank.neverUsed")}
      </p>

      {claimIds.length + answerIds.length > 0 ? (
        <ul className="mt-2 grid gap-1" aria-label={t("storyBank.evidenceTitle")}>
          {claimIds.map((id) => (
            <li key={`c${id}`} className="flex flex-wrap items-center gap-2 text-xs">
              <span>{t("storyBank.evidenceClaimN", { n: id })}</span>
              <button type="button" className={link} disabled={busy} onClick={() => void run(() => api.stories.detachEvidence(story.id, "claim", id))}>{t("storyBank.removeLink")}</button>
            </li>
          ))}
          {answerIds.map((id) => (
            <li key={`a${id}`} className="flex flex-wrap items-center gap-2 text-xs">
              <span>{t("storyBank.evidenceAnswerN", { n: id })}</span>
              <button type="button" className={link} disabled={busy} onClick={() => void run(() => api.stories.detachEvidence(story.id, "answer", id))}>{t("storyBank.removeLink")}</button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
        {!archived ? <button type="button" className={link} disabled={busy} onClick={() => onEdit(story)}>{t("storyBank.edit")}</button> : null}
        {!archived ? (
          story.confirmed_at
            ? <button type="button" className={link} disabled={busy} onClick={() => void run(() => api.stories.unconfirm(story.id))}>{t("storyBank.unconfirm")}</button>
            : <button type="button" className={link} disabled={busy} onClick={() => void run(() => api.stories.confirm(story.id))}>{t("storyBank.confirm")}</button>
        ) : null}
        {!archived ? <button type="button" className={link} aria-expanded={showLink} disabled={busy} onClick={() => setShowLink((x) => !x)}>{t("storyBank.linkToggle")}</button> : null}
        {!archived ? <button type="button" className={link} aria-expanded={showShare} disabled={busy} onClick={() => setShowShare((x) => !x)}>{t("storyBank.shareToggle")}</button> : null}
        {archived
          ? <button type="button" className={link} disabled={busy} onClick={() => void run(() => api.stories.restore(story.id))}>{t("storyBank.restore")}</button>
          : <button type="button" className={link} disabled={busy} onClick={() => void run(() => api.stories.archive(story.id))}>{t("storyBank.archive")}</button>}
        <button type="button" className="text-sm text-muted hover:text-danger disabled:opacity-50" disabled={busy} onClick={() => setConfirmDelete(true)}>{t("storyBank.delete")}</button>
      </div>
      {!archived && !story.confirmed_at ? <p className="mt-1 text-xs text-muted">{t("storyBank.confirmHelp")}</p> : null}

      {showLink && !archived ? <EvidenceLinker story={story} onChanged={onChanged} /> : null}
      {showShare && !archived ? <StoryShare storyId={story.id} /> : null}

      <ConfirmDialog
        open={confirmDelete} title={`${t("storyBank.deleteTitle")} ${story.title}`} confirmLabel={t("storyBank.delete")} busy={busy}
        onConfirm={() => void remove()} onCancel={() => setConfirmDelete(false)} testId={`delete-story-${story.id}`}
      >
        <p>{t("storyBank.deleteBody")}</p>
      </ConfirmDialog>
    </li>
  );
}
