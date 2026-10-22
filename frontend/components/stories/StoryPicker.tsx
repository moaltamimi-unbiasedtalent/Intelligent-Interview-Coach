"use client";

/**
 * Practice story picker (04A, REQ-OWN-06 S4). The candidate chooses which of their OWN stories Mo may use in this
 * practice session, one by one. A suggestion is only a proposal: nothing is used until the candidate ticks it AND
 * gives the explicit consent below. Each row shows how the story is verified, so an unverified story is never
 * presented as evidence. The server re-checks ownership and usability; this component only emits ids and consent.
 */

import { useEffect, useId, useMemo, useState } from "react";
import { api } from "@/lib/api/client";
import type { StoryOut, StorySuggestion } from "@/lib/api/types";
import { useI18n } from "@/components/i18n/I18nProvider";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { MAX_PRACTICE_STORIES, VERIFICATION_KEY, VERIFICATION_TONE, verificationOf } from "@/components/stories/storyVocab";

/** Mirrors the server rule in `StoryRepository.is_usable`; the server stays the authority. */
export function isUsableStory(s: StoryOut): boolean {
  if (s.archived_at) return false;
  if (s.status === "model_suggested" && !s.confirmed_at) return false;
  if (s.status === "source_backed" && s.evidence_state !== "verified") return false;
  return true;
}

export function StoryPicker({
  roleText, opportunityId = null, value, onChange, consent, onConsent, disabled = false,
}: {
  roleText: string;
  opportunityId?: number | null;
  value: number[];
  onChange: (ids: number[]) => void;
  consent: boolean;
  onConsent: (v: boolean) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const uid = useId();
  const [stories, setStories] = useState<StoryOut[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [suggestions, setSuggestions] = useState<StorySuggestion[] | null>(null);
  const [suggesting, setSuggesting] = useState(false);

  useEffect(() => {
    let live = true;
    Promise.resolve().then(() => api.stories.list()).then((r) => { if (live) setStories(r.stories); }).catch(() => { if (live) { setStories([]); setFailed(true); } });
    return () => { live = false; };
  }, []);

  const suggested = useMemo(() => new Map((suggestions ?? []).map((s) => [s.id, s])), [suggestions]);
  const atLimit = value.length >= MAX_PRACTICE_STORIES;

  async function suggest() {
    setSuggesting(true);
    try {
      const terms = Array.from(new Set(roleText.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter((w) => w.length >= 3))).slice(0, 20);
      const r = await api.stories.suggest({ terms, ...(opportunityId != null ? { opportunity_id: opportunityId } : {}) });
      setSuggestions(r.suggestions);
    } catch { setSuggestions([]); } finally { setSuggesting(false); }
  }

  function toggle(id: number, on: boolean) {
    const next = on ? [...value, id] : value.filter((x) => x !== id);
    onChange(next);
    if (next.length === 0) onConsent(false);
  }

  return (
    <div className="grid gap-2" role="group" aria-labelledby={`${uid}-h`}>
      <h3 id={`${uid}-h`} className="text-sm font-medium text-foreground">{t("storyBank.pickerTitle")}</h3>
      <p className="text-xs text-muted">{t("storyBank.pickerHelp")}</p>

      {stories === null ? (
        <p className="text-sm text-muted">{t("common.loading")}</p>
      ) : failed ? (
        <p className="text-sm text-muted">{t("storyBank.loadError")}</p>
      ) : stories.length === 0 ? (
        <p className="text-sm text-muted">{t("storyBank.pickerEmpty")}</p>
      ) : (
        <>
          <div>
            <Button type="button" size="sm" variant="ghost" onClick={() => void suggest()} disabled={disabled || suggesting}>
              {suggesting ? t("storyBank.pickerSuggesting") : t("storyBank.pickerSuggest")}
            </Button>
            {suggestions !== null && suggestions.length === 0 ? <span className="ml-3 text-xs text-muted">{t("storyBank.pickerNoSuggestions")}</span> : null}
          </div>
          <ul className="grid gap-1.5">
            {stories.map((s) => {
              const usable = isUsableStory(s);
              const v = verificationOf(s);
              const sug = suggested.get(s.id);
              const checked = value.includes(s.id);
              const id = `${uid}-s${s.id}`;
              return (
                <li key={s.id} className="flex items-start gap-2 rounded border border-border p-2 text-sm">
                  <input
                    id={id} type="checkbox" className="mt-1 h-4 w-4" checked={checked}
                    disabled={disabled || !usable || (!checked && atLimit)} onChange={(e) => toggle(s.id, e.target.checked)}
                  />
                  <label htmlFor={id} className="min-w-0 flex-1">
                    <span className="font-medium text-foreground">{s.title}</span>{" "}
                    <Badge tone={VERIFICATION_TONE[v]}>{t(VERIFICATION_KEY[v])}</Badge>
                    {sug ? <Badge className="ml-1">{t("storyBank.pickerSuggestedBadge")}</Badge> : null}
                    {sug && sug.matched.length > 0 ? <span className="mt-0.5 block text-xs text-muted">{t("storyBank.pickerMatched", { terms: sug.matched.join(", ") })}</span> : null}
                    {!usable ? <span className="mt-0.5 block text-xs text-muted">{t("storyBank.pickerNotUsable")}</span> : null}
                  </label>
                </li>
              );
            })}
          </ul>
          <p className="text-xs text-muted" aria-live="polite">
            {t("storyBank.pickerSelected", { n: value.length, max: MAX_PRACTICE_STORIES })}
            {atLimit ? ` ${t("storyBank.pickerLimit", { max: MAX_PRACTICE_STORIES })}` : ""}
          </p>
          {value.length > 0 ? (
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-1 h-4 w-4" checked={consent} disabled={disabled} onChange={(e) => onConsent(e.target.checked)} />
              <span>{t("storyBank.pickerConsent")}</span>
            </label>
          ) : null}
        </>
      )}
    </div>
  );
}
