"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { MemoryCategory, MemoryPreviewItem, MemoryResponse } from "@/lib/api/types";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Field";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { useT } from "@/components/i18n/I18nProvider";

/** Candidate-friendly category labels - technical categories are never shown raw. Mapped to i18n
 *  keys (resolved via t() at render) so names localise with the interface language. */
export const CATEGORY_KEY: Record<MemoryCategory, string> = {
  target_role: "memory.catTargetRole",
  recurring_gap: "memory.catPriority",
  strength: "memory.catStrength",
  completed_topic: "memory.catCompleted",
  interview_preference: "memory.catPreference",
  preparation_goal: "memory.catGoal",
};

/** English category labels retained for an out-of-scope consumer (agent/PendingHumanActionCard).
 *  Candidate-facing rendering in THIS file uses CATEGORY_KEY + t(); do not add new callers. */
export const CATEGORY_LABEL: Record<MemoryCategory, string> = {
  target_role: "Target role",
  recurring_gap: "Priority",
  strength: "Strength",
  completed_topic: "Completed",
  interview_preference: "Preference",
  preparation_goal: "Goal",
};

export const CATEGORIES: MemoryCategory[] = [
  "recurring_gap", "strength", "completed_topic",
  "interview_preference", "preparation_goal", "target_role",
];

/**
 * Primary preparation-memory management surface (P2): list, edit, pin/unpin, delete,
 * and a "what may load next time" preview. Candidate-controlled; nothing is saved
 * without the user. Memory is preparation details the user chose to save — never a
 * hidden chat history.
 */
export function MemoryManager() {
  const t = useT();
  const [items, setItems] = useState<MemoryResponse[] | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<{ message: string; requestId?: string | null } | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const ctrlRef = useRef<AbortController | null>(null);

  // Safe re-runnable GET (P10B-W9.2): aborts any in-flight load so a stale response cannot
  // overwrite a newer success; a manual retry starts a fresh bounded request cycle.
  const load = useCallback((isRetry = false) => {
    ctrlRef.current?.abort();
    const ctrl = new AbortController();
    ctrlRef.current = ctrl;
    if (isRetry) setRetrying(true);
    else setStatus("loading");
    api.memory
      .list(undefined, { signal: ctrl.signal })
      .then((r) => {
        if (ctrl.signal.aborted) return;
        setItems(r.memories);
        setError(null);
        setStatus("ready");
        setRetrying(false);
      })
      .catch((e) => {
        if (ctrl.signal.aborted || (e instanceof DOMException && e.name === "AbortError")) return;
        const err = e as ApiError;
        setError({ message: err.userMessage ?? t("memory.loadError"), requestId: err.requestId });
        setStatus("error");
        setRetrying(false);
      });
  }, [t]);

  useEffect(() => {
    load();
    return () => ctrlRef.current?.abort();
  }, [load]);

  const onSaved = useCallback((updated: MemoryResponse, msg: string) => {
    setItems((prev) => (prev ? prev.map((m) => (m.id === updated.id ? updated : m)) : prev));
    setNotice(msg);
  }, []);

  const onRemoved = useCallback((id: number) => {
    setItems((prev) => (prev ? prev.filter((m) => m.id !== id) : prev));
    setNotice(t("memory.removedNotice"));
  }, [t]);

  return (
    <div className="grid gap-6">
      <div>
        <h2 className="text-base font-semibold">{t("memory.title")}</h2>
        <p className="mt-1 text-sm text-muted">
          {t("memory.intro")}
        </p>
      </div>

      {notice ? <p role="status" aria-live="polite" className="text-xs text-success">{notice}</p> : null}
      {status === "loading" ? <LoadingState label={t("memory.loadingLabel")} /> : null}
      {status === "error" && error ? (
        <ErrorState message={error.message} requestId={error.requestId} retrying={retrying} onRetry={() => load(true)} />
      ) : null}

      {status === "ready" && items ? (
        items.length === 0 ? (
          <EmptyState
            title={t("memory.emptyTitle")}
            description={t("memory.emptyDescription")}
            action={<ButtonLink href="/prepare">{t("common.prepareWithMo")}</ButtonLink>}
          />
        ) : (
          <ul className="grid gap-3">
            {items.map((m) => (
              <li key={m.id}>
                <MemoryRow memory={m} onSaved={onSaved} onRemoved={onRemoved} />
              </li>
            ))}
          </ul>
        )
      ) : null}

      <NextRunPreview />
    </div>
  );
}

function MemoryRow({
  memory,
  onSaved,
  onRemoved,
}: {
  memory: MemoryResponse;
  onSaved: (m: MemoryResponse, msg: string) => void;
  onRemoved: (id: number) => void;
}) {
  const t = useT();
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pinToggle = async () => {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.memory.update(memory.id, { pinned: !memory.pinned });
      onSaved(updated, updated.pinned ? t("memory.pinnedNotice") : t("memory.unpinnedNotice"));
    } catch (e) {
      setError((e as ApiError).userMessage ?? t("memory.updateError"));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.memory.remove(memory.id);
      onRemoved(memory.id);
    } catch (e) {
      setError((e as ApiError).userMessage ?? t("memory.removeError"));
      setBusy(false);
    }
  };

  if (editing) {
    return (
      <MemoryEditForm
        memory={memory}
        onCancel={() => setEditing(false)}
        onSaved={(m) => { setEditing(false); onSaved(m, t("common.saved")); }}
      />
    );
  }

  return (
    <Card>
      <CardBody className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="font-medium break-words">{memory.summary}</p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <Badge>{t(CATEGORY_KEY[memory.category])}</Badge>
            {memory.target_role ? <Badge tone="neutral">{memory.target_role}</Badge> : null}
            {memory.pinned ? <Badge tone="low">📌 {t("memory.pinned")}</Badge> : null}
          </div>
          {error ? <p role="alert" className="mt-1 text-sm text-danger">{error}</p> : null}
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {confirming ? (
            <div className="flex items-center gap-2" role="group" aria-label={t("memory.removeItemAria", { summary: memory.summary })}>
              <span className="text-xs text-muted">{t("memory.removeConfirm")}</span>
              <Button size="sm" variant="ghost" onClick={() => setConfirming(false)} disabled={busy}>{t("common.cancel")}</Button>
              <Button size="sm" onClick={remove} disabled={busy}>{t("common.remove")}</Button>
            </div>
          ) : (
            <>
              <Button size="sm" variant="ghost" onClick={() => setEditing(true)}
                aria-label={t("memory.editAria", { summary: memory.summary })}>{t("common.edit")}</Button>
              <Button size="sm" variant="ghost" onClick={pinToggle} disabled={busy}
                aria-pressed={memory.pinned}
                aria-label={t(memory.pinned ? "memory.unpinAria" : "memory.pinAria", { summary: memory.summary })}>
                {memory.pinned ? t("memory.unpin") : t("memory.pin")}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setConfirming(true)}
                aria-label={t("memory.removeAria", { summary: memory.summary })}>{t("common.remove")}</Button>
            </>
          )}
        </div>
      </CardBody>
    </Card>
  );
}

function MemoryEditForm({
  memory,
  onCancel,
  onSaved,
}: {
  memory: MemoryResponse;
  onCancel: () => void;
  onSaved: (m: MemoryResponse) => void;
}) {
  const t = useT();
  const [category, setCategory] = useState<MemoryCategory>(memory.category);
  const [summary, setSummary] = useState(memory.summary);
  const [role, setRole] = useState(memory.target_role ?? "");
  const [pinned, setPinned] = useState(memory.pinned);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.memory.update(memory.id, {
        category,
        summary: summary.trim(),
        target_role: role.trim() || null,
        pinned,
      });
      onSaved(updated);
    } catch (e) {
      // Preserve the entered text so the user can correct and retry.
      setError((e as ApiError).userMessage ?? t("memory.saveError"));
      setBusy(false);
    }
  };

  return (
    <Card className="border-accent">
      <CardBody className="grid gap-3">
        <div>
          <label htmlFor={`cat-${memory.id}`} className="block text-sm text-muted">{t("memory.categoryLabel")}</label>
          <select
            id={`cat-${memory.id}`}
            value={category}
            onChange={(e) => setCategory(e.target.value as MemoryCategory)}
            className="w-full rounded-lg border border-border bg-surface px-3.5 py-3"
          >
            {CATEGORIES.map((c) => <option key={c} value={c}>{t(CATEGORY_KEY[c])}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor={`sum-${memory.id}`} className="block text-sm text-muted">{t("memory.memoryLabel")}</label>
          <Textarea id={`sum-${memory.id}`} value={summary} maxLength={500}
            onChange={(e) => setSummary(e.target.value)} />
        </div>
        <div>
          <label htmlFor={`role-${memory.id}`} className="block text-sm text-muted">{t("memory.targetRoleOptional")}</label>
          <Input id={`role-${memory.id}`} value={role} maxLength={200}
            onChange={(e) => setRole(e.target.value)} />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={pinned} onChange={(e) => setPinned(e.target.checked)} />
          {t("memory.pinHelp")}
        </label>
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={save} disabled={busy || summary.trim().length === 0}>{t("common.save")}</Button>
          <Button size="sm" variant="ghost" onClick={onCancel} disabled={busy}>{t("common.cancel")}</Button>
        </div>
      </CardBody>
    </Card>
  );
}

function NextRunPreview() {
  const t = useT();
  const [role, setRole] = useState("");
  const [items, setItems] = useState<MemoryPreviewItem[] | null>(null);
  const [limit, setLimit] = useState(10);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.memory.preview(role.trim() || null);
      setItems(r.items);
      setLimit(r.load_limit);
    } catch (e) {
      setError((e as ApiError).userMessage ?? t("memory.previewError"));
    } finally {
      setBusy(false);
    }
  }, [role, t]);

  return (
    <Card>
      <CardBody className="grid gap-3">
        <div>
          <h3 className="text-sm font-semibold">{t("memory.previewTitle")}</h3>
          <p className="mt-1 text-xs text-muted">
            {t("memory.previewIntro", { limit })}
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="grow">
            <label htmlFor="preview-role" className="block text-sm text-muted">{t("memory.targetRoleOptional")}</label>
            <Input id="preview-role" value={role} maxLength={200}
              placeholder={t("memory.rolePlaceholder")}
              onChange={(e) => setRole(e.target.value)} />
          </div>
          <Button size="sm" onClick={run} disabled={busy}>{t("memory.previewButton")}</Button>
        </div>
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        {items !== null ? (
          items.length === 0 ? (
            <p className="text-sm text-muted">
              {t("memory.previewEmpty")}
            </p>
          ) : (
            <ol className="grid gap-2">
              {items.map((it) => (
                <li key={it.id} className="rounded-lg border border-border px-3 py-2">
                  <p className="text-sm break-words">{it.summary}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
                    <Badge>{t(CATEGORY_KEY[it.category])}</Badge>
                    {it.pinned ? <Badge tone="low">📌 {t("memory.pinned")}</Badge> : null}
                    <span>{it.reason}</span>
                  </div>
                </li>
              ))}
            </ol>
          )
        ) : null}
      </CardBody>
    </Card>
  );
}
