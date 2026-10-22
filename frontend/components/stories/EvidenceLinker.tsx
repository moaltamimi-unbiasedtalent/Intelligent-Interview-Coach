"use client";

/**
 * Link evidence to a story (04A, REQ-OWN-06 S2). Two kinds, both the candidate's OWN and both references only:
 * a document item (an extracted claim that has not been rejected) or one of their practice answers (question text
 * shown, never the answer). A document item makes the story "evidence verified"; a practice answer only marks it as
 * linked to the candidate's own words. Nothing here can attach another account's item (the server answers 404).
 */

import { useCallback, useEffect, useId, useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { ClaimOut, DocumentSummary, StoryAnswerSource, StoryOut } from "@/lib/api/types";
import { useI18n } from "@/components/i18n/I18nProvider";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";

type Kind = "claim" | "answer";

export function EvidenceLinker({ story, onChanged }: { story: StoryOut; onChanged: (s: StoryOut) => void }) {
  const { t } = useI18n();
  const uid = useId();
  const [kind, setKind] = useState<Kind>("claim");
  const [docs, setDocs] = useState<DocumentSummary[] | null>(null);
  const [docId, setDocId] = useState("");
  const [claims, setClaims] = useState<ClaimOut[]>([]);
  const [claimId, setClaimId] = useState("");
  const [sources, setSources] = useState<StoryAnswerSource[] | null>(null);
  const [answerId, setAnswerId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDocs = useCallback(async () => {
    try {
      const r = await api.documents.list();
      setDocs(r.documents.filter((d) => d.status === "ready" || d.status === "review_required"));
    } catch { setDocs([]); }
  }, []);
  const loadSources = useCallback(async () => {
    try { setSources((await api.stories.answerSources()).sources); } catch { setSources([]); }
  }, []);

  useEffect(() => { if (kind === "claim" && docs === null) void loadDocs(); }, [kind, docs, loadDocs]);
  useEffect(() => { if (kind === "answer" && sources === null) void loadSources(); }, [kind, sources, loadSources]);
  useEffect(() => {
    if (!docId) { setClaims([]); setClaimId(""); return; }
    let live = true;
    api.documents.get(Number(docId)).then((d) => { if (live) setClaims(d.claims.filter((c) => c.review_state !== "rejected")); }).catch(() => { if (live) setClaims([]); });
    return () => { live = false; };
  }, [docId]);

  const linked = new Set(kind === "claim" ? story.evidence_claim_ids : story.evidence_answer_ids ?? []);
  const refId = kind === "claim" ? claimId : answerId;

  async function link() {
    if (!refId) return;
    setBusy(true);
    setError(null);
    try {
      onChanged(await api.stories.attachEvidence(story.id, kind, Number(refId)));
      setClaimId(""); setAnswerId("");
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : t("storyBank.attachError"));
    } finally { setBusy(false); }
  }

  const selectCls = "min-h-[44px] w-full rounded border border-border bg-surface px-2 text-sm";
  return (
    <div className="mt-2 rounded-lg border border-border p-3" role="group" aria-labelledby={`${uid}-h`}>
      <h4 id={`${uid}-h`} className="text-sm font-semibold text-foreground">{t("storyBank.linkTitle")}</h4>
      <p className="mt-1 text-xs text-muted">{t(kind === "claim" ? "storyBank.linkClaimHelp" : "storyBank.linkAnswerHelp")}</p>
      {error ? <Alert tone="danger" className="mt-2">{error}</Alert> : null}
      <fieldset className="mt-2 flex flex-wrap gap-4 text-sm">
        <legend className="sr-only">{t("storyBank.linkKind")}</legend>
        <label className="flex items-center gap-2"><input type="radio" name={`${uid}-kind`} checked={kind === "claim"} onChange={() => setKind("claim")} />{t("storyBank.linkKindClaim")}</label>
        <label className="flex items-center gap-2"><input type="radio" name={`${uid}-kind`} checked={kind === "answer"} onChange={() => setKind("answer")} />{t("storyBank.linkKindAnswer")}</label>
      </fieldset>

      {kind === "claim" ? (
        <div className="mt-2 grid gap-2">
          <label htmlFor={`${uid}-doc`} className="text-sm font-medium">{t("storyBank.linkDocument")}</label>
          <select id={`${uid}-doc`} className={selectCls} value={docId} onChange={(e) => setDocId(e.target.value)} disabled={busy}>
            <option value="">{docs === null ? t("common.loading") : docs.length === 0 ? t("storyBank.linkNoDocuments") : t("storyBank.linkChoose")}</option>
            {(docs ?? []).map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
          </select>
          {docId ? (
            <>
              <label htmlFor={`${uid}-claim`} className="text-sm font-medium">{t("storyBank.linkClaim")}</label>
              <select id={`${uid}-claim`} className={selectCls} value={claimId} onChange={(e) => setClaimId(e.target.value)} disabled={busy}>
                <option value="">{t("storyBank.linkChoose")}</option>
                {claims.filter((c) => !linked.has(c.id)).map((c) => <option key={c.id} value={c.id}>{c.display_text.slice(0, 90)}</option>)}
              </select>
            </>
          ) : null}
        </div>
      ) : (
        <div className="mt-2 grid gap-2">
          <label htmlFor={`${uid}-ans`} className="text-sm font-medium">{t("storyBank.linkAnswer")}</label>
          <select id={`${uid}-ans`} className={selectCls} value={answerId} onChange={(e) => setAnswerId(e.target.value)} disabled={busy}>
            <option value="">{sources === null ? t("common.loading") : sources.length === 0 ? t("storyBank.linkNoAnswers") : t("storyBank.linkChoose")}</option>
            {(sources ?? []).filter((s) => !linked.has(s.answer_id)).map((s) => (
              <option key={s.answer_id} value={s.answer_id}>{t("storyBank.linkAnswerOption", { n: s.position + 1, q: s.question.slice(0, 80) })}</option>
            ))}
          </select>
        </div>
      )}
      <Button type="button" size="sm" className="mt-3" disabled={busy || !refId} onClick={() => void link()}>
        {t("storyBank.linkAction")}
      </Button>
    </div>
  );
}
