"use client";

/**
 * Story editor (04A, REQ-OWN-06 S1): create or edit a STAR story by hand. Every field is the candidate's own words;
 * nothing is pre-filled with invented facts, and the STAR hints only say what each part is for. Saving a story that
 * came from a document marks it as the candidate's own corrected account (the server decides that, not this form).
 */

import { useEffect, useId, useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { Opportunity, StoryOut } from "@/lib/api/types";
import { useI18n } from "@/components/i18n/I18nProvider";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Field";
import { Alert } from "@/components/ui/Alert";

type StarField = "situation" | "task" | "action" | "result";
const STAR: StarField[] = ["situation", "task", "action", "result"];
const HINT_KEY: Record<StarField, string> = {
  situation: "storyBank.hintSituation", task: "storyBank.hintTask", action: "storyBank.hintAction", result: "storyBank.hintResult",
};
const LABEL_KEY: Record<StarField, string> = {
  situation: "storyBank.fieldSituation", task: "storyBank.fieldTask", action: "storyBank.fieldAction", result: "storyBank.fieldResult",
};

export function StoryEditor({
  story, opportunities, onSaved, onCancel,
}: {
  story?: StoryOut | null;
  opportunities: Opportunity[];
  onSaved: (story: StoryOut) => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const uid = useId();
  const [title, setTitle] = useState(story?.title ?? "");
  const [star, setStar] = useState<Record<StarField, string>>({
    situation: story?.situation ?? "", task: story?.task ?? "", action: story?.action ?? "", result: story?.result ?? "",
  });
  const [tags, setTags] = useState((story?.competencies ?? []).join(", "));
  const [opportunityId, setOpportunityId] = useState<string>(story?.opportunity_id != null ? String(story.opportunity_id) : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [titleError, setTitleError] = useState(false);

  const focusTitle = () => document.getElementById(`${uid}-title`)?.focus();
  useEffect(() => { focusTitle(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) {
      setTitleError(true);
      focusTitle();
      return;
    }
    setBusy(true);
    setError(null);
    const competencies = tags.split(",").map((x) => x.trim()).filter(Boolean);
    try {
      const saved = story
        ? await api.stories.update(story.id, {
            title: title.trim(), ...star, competencies,
            opportunity_id: opportunityId ? Number(opportunityId) : null,
          })
        : await api.stories.create({
            title: title.trim(), status: "user_created", ...star, competencies,
            ...(opportunityId ? { opportunity_id: Number(opportunityId) } : {}),
          });
      onSaved(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : t("storyBank.saveError"));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} onKeyDown={(e) => { if (e.key === "Escape") onCancel(); }} className="mt-4 rounded-lg border border-border p-4" aria-labelledby={`${uid}-h`} noValidate>
      <h3 id={`${uid}-h`} className="text-base font-semibold text-foreground">
        {story ? t("storyBank.editorEditTitle") : t("storyBank.editorNewTitle")}
      </h3>
      <p className="mt-1 text-xs text-muted">{t("storyBank.noInvent")}</p>
      {error ? <Alert tone="danger" className="mt-3">{error}</Alert> : null}

      <div className="mt-3 grid gap-3">
        <div className="grid gap-1">
          <label htmlFor={`${uid}-title`} className="text-sm font-medium">{t("storyBank.fieldTitle")}</label>
          <Input
            id={`${uid}-title`} value={title} maxLength={255} disabled={busy}
            aria-invalid={titleError || undefined} aria-describedby={titleError ? `${uid}-title-err` : undefined}
            onChange={(e) => { setTitle(e.target.value); if (e.target.value.trim()) setTitleError(false); }}
          />
          {titleError ? <p id={`${uid}-title-err`} role="alert" className="text-xs text-danger">{t("storyBank.titleRequired")}</p> : null}
        </div>

        {STAR.map((f) => (
          <div key={f} className="grid gap-1">
            <label htmlFor={`${uid}-${f}`} className="text-sm font-medium">{t(LABEL_KEY[f])}</label>
            <Textarea
              id={`${uid}-${f}`} value={star[f]} maxLength={4000} disabled={busy} className="min-h-[88px]"
              aria-describedby={`${uid}-${f}-hint`}
              onChange={(e) => setStar((s) => ({ ...s, [f]: e.target.value }))}
            />
            <p id={`${uid}-${f}-hint`} className="text-xs text-muted">{t(HINT_KEY[f])}</p>
          </div>
        ))}

        <div className="grid gap-1">
          <label htmlFor={`${uid}-tags`} className="text-sm font-medium">{t("storyBank.fieldTags")}</label>
          <Input id={`${uid}-tags`} value={tags} disabled={busy} aria-describedby={`${uid}-tags-hint`} onChange={(e) => setTags(e.target.value)} />
          <p id={`${uid}-tags-hint`} className="text-xs text-muted">{t("storyBank.tagsHint")}</p>
        </div>

        <div className="grid gap-1">
          <label htmlFor={`${uid}-opp`} className="text-sm font-medium">{t("storyBank.fieldOpportunity")}</label>
          <select
            id={`${uid}-opp`} value={opportunityId} disabled={busy} onChange={(e) => setOpportunityId(e.target.value)}
            className="min-h-[44px] rounded border border-border bg-surface px-2 text-sm"
          >
            <option value="">{t("storyBank.noOpportunity")}</option>
            {opportunities.map((o) => <option key={o.id} value={o.id}>{o.title}</option>)}
          </select>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button type="submit" size="sm" disabled={busy}>{busy ? t("storyBank.saving") : t("common.save")}</Button>
        <Button type="button" size="sm" variant="ghost" onClick={onCancel} disabled={busy}>{t("common.cancel")}</Button>
      </div>
    </form>
  );
}
