"use client";

/**
 * Share one story with a Workspace (04A, REQ-OWN-06 S6). Sharing is an explicit, view-only grant the candidate makes
 * here and can end at any time. The text spells out exactly what a member can and cannot see. Archiving or deleting
 * the story ends the sharing on the server; restoring never shares it again.
 */

import { useCallback, useEffect, useId, useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { ShareGrantOut, WorkspaceSummary } from "@/lib/api/types";
import { useI18n } from "@/components/i18n/I18nProvider";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";

export function StoryShare({ storyId }: { storyId: number }) {
  const { t } = useI18n();
  const uid = useId();
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[] | null>(null);
  const [grants, setGrants] = useState<ShareGrantOut[]>([]);
  const [choice, setChoice] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [w, s] = await Promise.all([api.workspaces.list(), api.shares.mine()]);
      setWorkspaces(w.workspaces ?? []);
      setGrants((s.shares ?? []).filter((g) => g.resource_type === "story" && g.resource_id === String(storyId)));
      setError(null);
    } catch {
      setWorkspaces((w) => w ?? []);
      setError(t("storyBank.shareLoadError"));
    }
  }, [storyId, t]);
  useEffect(() => { void load(); }, [load]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try { await action(); await load(); } catch (e) { setError(e instanceof ApiError ? e.userMessage : t("storyBank.shareError")); } finally { setBusy(false); }
  }

  const nameOf = (id: number) => workspaces?.find((w) => w.id === id)?.name ?? t("storyBank.shareWorkspaceUnknown");
  const open = (workspaces ?? []).filter((w) => !grants.some((g) => g.workspace_id === w.id));

  return (
    <div className="mt-2 rounded-lg border border-border p-3" role="group" aria-labelledby={`${uid}-h`}>
      <h4 id={`${uid}-h`} className="text-sm font-semibold text-foreground">{t("storyBank.shareTitle")}</h4>
      <p className="mt-1 text-xs text-muted">{t("storyBank.shareExplain")}</p>
      {error ? <Alert tone="danger" className="mt-2">{error}</Alert> : null}

      {grants.length === 0 ? (
        <p className="mt-2 text-xs text-muted">{t("storyBank.shareNone")}</p>
      ) : (
        <ul className="mt-2 grid gap-1" aria-label={t("storyBank.shareActive")}>
          {grants.map((g) => (
            <li key={g.id} className="flex flex-wrap items-center gap-2 text-sm">
              <span>{t("storyBank.shareSharedWith", { name: nameOf(g.workspace_id) })}</span>
              <button type="button" className="text-sm text-accent hover:underline disabled:opacity-50" disabled={busy} onClick={() => void run(() => api.shares.revoke(g.id))}>
                {t("storyBank.shareStop")}
              </button>
            </li>
          ))}
        </ul>
      )}

      {workspaces === null ? (
        <p className="mt-2 text-sm text-muted">{t("common.loading")}</p>
      ) : workspaces.length === 0 ? (
        <p className="mt-2 text-xs text-muted">{t("storyBank.shareNoWorkspace")}</p>
      ) : open.length > 0 ? (
        <div className="mt-2 grid gap-2">
          <label htmlFor={`${uid}-ws`} className="text-sm font-medium">{t("storyBank.shareWorkspace")}</label>
          <select id={`${uid}-ws`} value={choice} disabled={busy} onChange={(e) => setChoice(e.target.value)} className="min-h-[44px] w-full rounded border border-border bg-surface px-2 text-sm">
            <option value="">{t("storyBank.linkChoose")}</option>
            {open.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </select>
          <Button type="button" size="sm" disabled={busy || !choice} onClick={() => void run(async () => { await api.shares.create(Number(choice), "story", String(storyId)); setChoice(""); })}>
            {t("storyBank.shareAction")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
