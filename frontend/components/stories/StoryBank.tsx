"use client";

/**
 * Story Bank (04A, REQ-OWN-06): create, edit, search, filter, tag, link to an Opportunity, verify with evidence,
 * archive/restore and delete the candidate's own interview stories. All data is owner-scoped on the server; search words
 * travel in a POST body (never a URL). Honest empty, filtered-empty, loading and error states.
 */

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { Opportunity, StoryArchiveFilter, StoryOut, StoryVerification } from "@/lib/api/types";
import { useI18n } from "@/components/i18n/I18nProvider";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Alert } from "@/components/ui/Alert";
import { EmptyStateIllustration, LoadingState } from "@/components/ui/States";
import { StoryEditor } from "@/components/stories/StoryEditor";
import { StoryCard } from "@/components/stories/StoryCard";
import { VERIFICATIONS, VERIFICATION_FILTER_KEY } from "@/components/stories/storyVocab";

type Filters = { q: string; tag: string; verification: "" | StoryVerification; archived: StoryArchiveFilter; opportunity: string };
const NO_FILTERS: Filters = { q: "", tag: "", verification: "", archived: "active", opportunity: "" };

export function StoryBank({ refreshKey = 0 }: { refreshKey?: number }) {
  const { t } = useI18n();
  const uid = useId();
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [stories, setStories] = useState<StoryOut[] | null>(null);
  const [tags, setTags] = useState<string[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<StoryOut | "new" | null>(null);
  const seq = useRef(0);

  const filtered = filters.q.trim() !== "" || filters.tag !== "" || filters.verification !== "" || filters.archived !== "active" || filters.opportunity !== "";

  const load = useCallback(async (f: Filters) => {
    const mine = ++seq.current;
    try {
      const isFiltered = f.q.trim() !== "" || f.tag !== "" || f.verification !== "" || f.archived !== "active" || f.opportunity !== "";
      const res = isFiltered
        ? await api.stories.search({
            ...(f.q.trim() ? { q: f.q.trim() } : {}), ...(f.tag ? { tag: f.tag } : {}),
            ...(f.verification ? { verification: f.verification } : {}), ...(f.opportunity ? { opportunity_id: Number(f.opportunity) } : {}),
            archived: f.archived,
          })
        : await api.stories.list();
      if (mine !== seq.current) return;              // a newer search superseded this one
      setStories(res.stories);
      setError(null);
    } catch (err) {
      if (mine !== seq.current) return;
      setError(err instanceof ApiError ? err.userMessage : t("storyBank.loadError"));
      setStories((s) => s ?? []);
    }
  }, [t]);

  // Debounce typing; every other filter applies at once.
  useEffect(() => {
    const id = setTimeout(() => void load(filters), filters.q ? 250 : 0);
    return () => clearTimeout(id);
  }, [filters, load, refreshKey]);

  // Tags and Opportunities only feed the filter and editor controls; a failure leaves them empty and never blocks the list.
  const loadTags = useCallback(() => { void Promise.resolve().then(() => api.stories.tags()).then((r) => setTags(r.tags)).catch(() => setTags([])); }, []);
  useEffect(() => {
    loadTags();
    void Promise.resolve().then(() => api.opportunities.list()).then((r) => setOpportunities(r.opportunities)).catch(() => setOpportunities([]));
  }, [refreshKey, loadTags]);

  const reloadTags = loadTags;
  const patch = (s: StoryOut) => {
    // Keep the card in place when it still matches; an archive/restore that no longer matches the filter leaves the list.
    setStories((all) => (all ?? []).flatMap((x) => (x.id !== s.id ? [x] : (filters.archived === "all" || Boolean(s.archived_at) === (filters.archived === "archived") ? [s] : []))));
    reloadTags();
  };
  const set = <K extends keyof Filters>(k: K, v: Filters[K]) => setFilters((f) => ({ ...f, [k]: v }));
  const selectCls = "min-h-[44px] w-full rounded border border-border bg-surface px-2 text-sm";

  function closeEditor() {
    setEditing(null);
    requestAnimationFrame(() => document.getElementById(`${uid}-new`)?.focus());
  }

  return (
    <section className="mt-8" aria-labelledby={`${uid}-h`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id={`${uid}-h`} className="text-lg font-bold text-foreground">{t("documents.storiesTitle")}</h2>
          <p className="text-sm text-muted">{t("documents.storiesSubtitle")}</p>
        </div>
        <Button id={`${uid}-new`} size="sm" onClick={() => setEditing("new")} disabled={editing !== null}>{t("storyBank.newStory")}</Button>
      </div>

      {editing !== null ? (
        <StoryEditor
          key={editing === "new" ? "new" : editing.id}
          story={editing === "new" ? null : editing} opportunities={opportunities} onCancel={closeEditor}
          onSaved={() => { closeEditor(); void load(filters); reloadTags(); }}
        />
      ) : null}

      <div role="search" aria-label={t("storyBank.searchRegion")} className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div className="grid gap-1 sm:col-span-2">
          <label htmlFor={`${uid}-q`} className="text-sm font-medium">{t("storyBank.searchLabel")}</label>
          <Input id={`${uid}-q`} type="search" value={filters.q} onChange={(e) => set("q", e.target.value)} placeholder={t("storyBank.searchPlaceholder")} />
        </div>
        <div className="grid gap-1">
          <label htmlFor={`${uid}-tag`} className="text-sm font-medium">{t("storyBank.filterTag")}</label>
          <select id={`${uid}-tag`} className={selectCls} value={filters.tag} onChange={(e) => set("tag", e.target.value)}>
            <option value="">{t("storyBank.filterAll")}</option>
            {tags.map((x) => <option key={x} value={x}>{x}</option>)}
          </select>
        </div>
        <div className="grid gap-1">
          <label htmlFor={`${uid}-ver`} className="text-sm font-medium">{t("storyBank.filterVerification")}</label>
          <select id={`${uid}-ver`} className={selectCls} value={filters.verification} onChange={(e) => set("verification", e.target.value as Filters["verification"])}>
            <option value="">{t("storyBank.filterAll")}</option>
            {VERIFICATIONS.map((v) => <option key={v} value={v}>{t(VERIFICATION_FILTER_KEY[v])}</option>)}
          </select>
        </div>
        <div className="grid gap-1">
          <label htmlFor={`${uid}-arc`} className="text-sm font-medium">{t("storyBank.filterArchive")}</label>
          <select id={`${uid}-arc`} className={selectCls} value={filters.archived} onChange={(e) => set("archived", e.target.value as StoryArchiveFilter)}>
            <option value="active">{t("storyBank.archiveActive")}</option>
            <option value="archived">{t("storyBank.archiveArchived")}</option>
            <option value="all">{t("storyBank.archiveAll")}</option>
          </select>
        </div>
        {opportunities.length > 0 ? (
          <div className="grid gap-1">
            <label htmlFor={`${uid}-opp`} className="text-sm font-medium">{t("storyBank.fieldOpportunity")}</label>
            <select id={`${uid}-opp`} className={selectCls} value={filters.opportunity} onChange={(e) => set("opportunity", e.target.value)}>
              <option value="">{t("storyBank.filterAll")}</option>
              {opportunities.map((o) => <option key={o.id} value={o.id}>{o.title}</option>)}
            </select>
          </div>
        ) : null}
      </div>
      {filtered ? <button type="button" className="mt-2 text-sm text-accent hover:underline" onClick={() => setFilters(NO_FILTERS)}>{t("storyBank.clearFilters")}</button> : null}

      {error ? (
        <Alert tone="danger" className="mt-3">
          <span>{error}</span>{" "}
          <button type="button" className="font-semibold underline" onClick={() => void load(filters)}>{t("storyBank.retry")}</button>
        </Alert>
      ) : null}

      <p className="mt-3 text-xs text-muted" aria-live="polite" data-testid="story-count">
        {stories === null ? "" : t("storyBank.resultsCount", { n: stories.length })}
      </p>

      {stories === null ? (
        <LoadingState label={t("common.loading")} />
      ) : stories.length === 0 && !error ? (
        filtered ? (
          <p className="mt-3 text-sm text-muted">{t("storyBank.emptyFiltered")}</p>
        ) : (
          <>
            <div className="mt-3 flex justify-center">
              <EmptyStateIllustration src="/images/ask4mo/ask4mo-empty-documents-story-bank-ink.png" alt={t("documents.storyEmptyIllustrationAlt")} />
            </div>
            <p className="mt-3 text-sm text-muted">{t("storyBank.empty")}</p>
          </>
        )
      ) : (
        <ul className="mt-3 space-y-3">
          {stories.map((s) => (
            <StoryCard
              key={s.id} story={s} opportunities={opportunities}
              onChanged={patch} onEdit={(x) => setEditing(x)}
              onDeleted={(id) => { setStories((all) => (all ?? []).filter((x) => x.id !== id)); reloadTags(); }}
            />
          ))}
        </ul>
      )}
    </section>
  );
}
