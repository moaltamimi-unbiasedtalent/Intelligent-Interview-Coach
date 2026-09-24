"use client";

/**
 * Private documents & evidence surface (Capstone P4/E2/E3).
 *
 * Candidate-oriented (not a technical console): upload a CV/JD privately, watch its
 * status, review/correct/reject the evidence Ask4Mo extracted (with provenance), build
 * reusable stories from approved evidence, and delete/replace. Fully localized via i18n.
 * Documents are private DATA — never public, never analysed for identity/emotion.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import type { ClaimOut, DocumentDetail, DocumentSummary, StoryOut } from "@/lib/api/types";
import { useI18n } from "@/components/i18n/I18nProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { LoadingState } from "@/components/ui/States";

const CATEGORIES = ["cv", "job_description", "portfolio", "company_brief", "other"] as const;

function statusKey(status: string): string {
  const map: Record<string, string> = {
    uploaded: "documents.statusUploaded", processing: "documents.statusProcessing",
    review_required: "documents.statusReview", ready: "documents.statusReady",
    failed: "documents.statusFailed",
  };
  return map[status] ?? "documents.statusUploaded";
}

export function DocumentsClient() {
  const { t } = useI18n();
  const [docs, setDocs] = useState<DocumentSummary[] | null>(null);
  const [stories, setStories] = useState<StoryOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [d, s] = await Promise.all([api.documents.list(), api.stories.list()]);
      setDocs(d.documents);
      setStories(s.stories);
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : "Could not load your documents.");
      setDocs([]);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <section className="max-w-reading">
      <PageHeader eyebrow="Evidence" title={t("documents.title")} description={t("documents.subtitle")} />
      {error ? <Alert tone="danger" className="mb-4">{error}</Alert> : null}

      <UploadCard onUploaded={refresh} />

      {docs === null ? (
        <LoadingState label={t("common.loading")} />
      ) : docs.length === 0 ? (
        <p className="mt-4 text-sm text-muted">{t("documents.empty")}</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {docs.map((d) => (
            <li key={d.id}>
              <DocumentRow summary={d} onChanged={refresh} />
            </li>
          ))}
        </ul>
      )}

      <StoryBank stories={stories} onChanged={refresh} />

      <p className="mt-6 text-xs text-muted">{t("documents.privacyNote")}</p>
    </section>
  );
}

function UploadCard({ onUploaded }: { onUploaded: () => void }) {
  const { t } = useI18n();
  const [category, setCategory] = useState("cv");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const onFile = async (file: File) => {
    setErr(null);
    setBusy(true);
    try {
      await api.documents.upload(file, category);
      onUploaded();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("documents.uploadFailed"));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <Card>
      <CardBody className="space-y-3">
        {err ? <Alert tone="danger">{err}</Alert> : null}
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="mb-1 block font-medium text-foreground">{t("documents.category")}</span>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              disabled={busy}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm"
              aria-label={t("documents.category")}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {t(`documents.cat${c === "cv" ? "Cv" : c === "job_description" ? "Job" : c === "portfolio" ? "Portfolio" : c === "company_brief" ? "Brief" : "Other"}`)}
                </option>
              ))}
            </select>
          </label>
          <div>
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.docx,.txt,.png,.jpg,.jpeg"
              aria-label={t("documents.upload")}
              disabled={busy}
              onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
              className="block text-sm"
            />
          </div>
          {busy ? <span className="text-sm text-muted">{t("documents.uploading")}</span> : null}
        </div>
        <p className="text-xs text-muted">{t("documents.dropHint")}</p>
      </CardBody>
    </Card>
  );
}

function DocumentRow({ summary, onChanged }: { summary: DocumentSummary; onChanged: () => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const load = useCallback(async () => {
    setDetail(await api.documents.get(summary.id));
  }, [summary.id]);

  useEffect(() => {
    if (open && !detail) void load();
  }, [open, detail, load]);

  const remove = async () => {
    await api.documents.remove(summary.id);
    onChanged();
  };

  return (
    <Card>
      <CardBody>
        <div className="flex items-center justify-between gap-3">
          <button type="button" onClick={() => setOpen((v) => !v)} className="text-left">
            <span className="font-medium text-foreground">{summary.title}</span>{" "}
            <Badge>{t(statusKey(summary.status))}</Badge>
          </button>
          <div className="flex items-center gap-3 text-sm">
            <a href={api.documents.downloadUrl(summary.id)} className="text-accent hover:underline">{t("documents.download")}</a>
            {!confirmDelete ? (
              <button onClick={() => setConfirmDelete(true)} className="text-muted hover:text-danger">{t("documents.delete")}</button>
            ) : (
              <span className="flex items-center gap-2">
                <span className="text-xs text-danger">{t("documents.deleteConfirm")}</span>
                <button onClick={remove} className="font-semibold text-danger">{t("documents.delete")}</button>
                <button onClick={() => setConfirmDelete(false)} className="text-muted">{t("common.cancel")}</button>
              </span>
            )}
          </div>
        </div>
        {confirmDelete ? <p className="mt-1 text-xs text-muted">{t("documents.deleteExplain")}</p> : null}

        {open && detail ? <ClaimReview detail={detail} onReviewed={load} onDrafted={onChanged} /> : null}
      </CardBody>
    </Card>
  );
}

function ClaimReview({ detail, onReviewed, onDrafted }: { detail: DocumentDetail; onReviewed: () => void; onDrafted: () => void }) {
  const { t } = useI18n();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [editing, setEditing] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  const act = async (claim: ClaimOut, action: string, text?: string) => {
    await api.documents.reviewClaim(detail.id, claim.id, action, text);
    setEditing(null);
    onReviewed();
  };

  const draft = async () => {
    if (selected.size === 0) return;
    await api.stories.draft(detail.title, [...selected]);
    setSelected(new Set());
    onDrafted();
  };

  if (detail.status === "failed") {
    const reason = detail.versions[detail.versions.length - 1]?.failure_reason;
    return <Alert tone="warning" className="mt-3">{reason || t("documents.statusFailed")}</Alert>;
  }

  return (
    <div className="mt-3 border-t border-border pt-3">
      <h3 className="text-sm font-semibold text-foreground">{t("documents.reviewTitle")}</h3>
      <p className="text-xs text-muted">{t("documents.reviewHint")}</p>
      <ul className="mt-2 space-y-2">
        {detail.claims.map((c) => (
          <li key={c.id} className="rounded-lg border border-border p-2 text-sm">
            <div className="flex items-start gap-2">
              <input
                type="checkbox"
                className="mt-1"
                aria-label={c.display_text}
                checked={selected.has(c.id)}
                disabled={c.review_state === "rejected"}
                onChange={(e) => setSelected((s) => { const n = new Set(s); e.target.checked ? n.add(c.id) : n.delete(c.id); return n; })}
              />
              <div className="min-w-0 flex-1">
                <Badge>{t(`documents.type${c.claim_type[0].toUpperCase()}${c.claim_type.slice(1)}` as never)}</Badge>{" "}
                <Badge>{t(`documents.${c.review_state}` as never)}</Badge>
                {editing === c.id ? (
                  <div className="mt-1 flex gap-2">
                    <input value={editText} onChange={(e) => setEditText(e.target.value)} placeholder={t("documents.editPlaceholder")} className="flex-1 rounded border border-border px-2 py-1 text-sm" />
                    <Button size="sm" onClick={() => act(c, "edit", editText)}>{t("documents.save")}</Button>
                  </div>
                ) : (
                  <p className="mt-0.5 break-words text-foreground">{c.display_text}</p>
                )}
                <p className="text-xs text-muted">
                  {t("documents.source")}: {c.source_page ? t("documents.page", { n: c.source_page }) : c.source_section}
                </p>
                <div className="mt-1 flex gap-3 text-xs">
                  <button onClick={() => act(c, "accept")} className="text-accent hover:underline">{t("documents.accept")}</button>
                  <button onClick={() => { setEditing(c.id); setEditText(c.display_text); }} className="text-accent hover:underline">{t("documents.edit")}</button>
                  <button onClick={() => act(c, "reject")} className="text-muted hover:text-danger">{t("documents.reject")}</button>
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
      <Button size="sm" className="mt-3" disabled={selected.size === 0} onClick={draft}>
        {t("documents.draftStory")}
      </Button>
    </div>
  );
}

function StoryBank({ stories, onChanged }: { stories: StoryOut[]; onChanged: () => void }) {
  const { t } = useI18n();
  const remove = async (id: number) => {
    await api.stories.remove(id);
    onChanged();
  };
  const statusLabel: Record<string, string> = {
    source_backed: "documents.stSourceBacked", user_created: "documents.stUserCreated",
    user_corrected: "documents.stUserCorrected", model_suggested: "documents.stModelSuggested",
  };
  const evLabel: Record<string, string> = {
    verified: "documents.evVerified", source_revoked: "documents.evRevoked", none: "documents.evNone",
  };
  return (
    <div className="mt-8">
      <h2 className="text-lg font-bold text-foreground">{t("documents.storiesTitle")}</h2>
      <p className="text-sm text-muted">{t("documents.storiesSubtitle")}</p>
      {stories.length === 0 ? (
        <p className="mt-3 text-sm text-muted">{t("documents.storyEmpty")}</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {stories.map((s) => (
            <li key={s.id} className="rounded-lg border border-border p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-foreground">{s.title}</span>
                <button onClick={() => remove(s.id)} className="text-xs text-muted hover:text-danger">{t("documents.deleteStory")}</button>
              </div>
              <div className="mt-1 flex flex-wrap gap-2">
                <Badge>{t(statusLabel[s.status] ?? "documents.stUserCreated")}</Badge>
                <Badge>{t(evLabel[s.evidence_state] ?? "documents.evNone")}</Badge>
              </div>
              {s.result ? <p className="mt-1 text-muted">{s.result}</p> : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
