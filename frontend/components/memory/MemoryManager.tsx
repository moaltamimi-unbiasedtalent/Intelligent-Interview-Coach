"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { MemoryCategory, MemoryPreviewItem, MemoryResponse } from "@/lib/api/types";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Field";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";

/** Candidate-friendly labels — technical categories are never shown raw. */
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
  const [items, setItems] = useState<MemoryResponse[] | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<{ message: string; requestId?: string | null } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback((signal?: AbortSignal) => {
    setStatus("loading");
    api.memory
      .list(undefined, { signal })
      .then((r) => { setItems(r.memories); setStatus("ready"); })
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        const err = e as ApiError;
        setError({ message: err.userMessage ?? "Couldn't load your preparation memory.", requestId: err.requestId });
        setStatus("error");
      });
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  const onSaved = useCallback((updated: MemoryResponse, msg: string) => {
    setItems((prev) => (prev ? prev.map((m) => (m.id === updated.id ? updated : m)) : prev));
    setNotice(msg);
  }, []);

  const onRemoved = useCallback((id: number) => {
    setItems((prev) => (prev ? prev.filter((m) => m.id !== id) : prev));
    setNotice("Preparation memory removed.");
  }, []);

  return (
    <div className="grid gap-6">
      <div>
        <h2 className="text-base font-semibold">What Mo remembers</h2>
        <p className="mt-1 text-sm text-muted">
          These are preparation details you chose to save for future Coach sessions. You
          can edit, prioritise or remove them at any time.
        </p>
      </div>

      {notice ? <p role="status" aria-live="polite" className="text-xs text-success">{notice}</p> : null}
      {status === "loading" ? <LoadingState label="Loading your preparation memory" /> : null}
      {status === "error" && error ? <ErrorState message={error.message} requestId={error.requestId} /> : null}

      {status === "ready" && items ? (
        items.length === 0 ? (
          <EmptyState
            title="Nothing saved yet."
            description="Mo can remember selected preparation preferences that you explicitly approve. Mo never saves anything without you asking."
            action={<ButtonLink href="/prepare">Prepare with Mo</ButtonLink>}
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
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pinToggle = async () => {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.memory.update(memory.id, { pinned: !memory.pinned });
      onSaved(updated, updated.pinned ? "Pinned." : "Unpinned.");
    } catch (e) {
      setError((e as ApiError).userMessage ?? "Couldn't update that memory.");
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
      setError((e as ApiError).userMessage ?? "Couldn't remove that memory.");
      setBusy(false);
    }
  };

  if (editing) {
    return (
      <MemoryEditForm
        memory={memory}
        onCancel={() => setEditing(false)}
        onSaved={(m) => { setEditing(false); onSaved(m, "Saved."); }}
      />
    );
  }

  return (
    <Card>
      <CardBody className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="font-medium break-words">{memory.summary}</p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <Badge>{CATEGORY_LABEL[memory.category]}</Badge>
            {memory.target_role ? <Badge tone="neutral">{memory.target_role}</Badge> : null}
            {memory.pinned ? <Badge tone="low">📌 Pinned</Badge> : null}
          </div>
          {error ? <p role="alert" className="mt-1 text-sm text-danger">{error}</p> : null}
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {confirming ? (
            <div className="flex items-center gap-2" role="group" aria-label={`Remove “${memory.summary}”?`}>
              <span className="text-xs text-muted">Remove this saved preparation memory?</span>
              <Button size="sm" variant="ghost" onClick={() => setConfirming(false)} disabled={busy}>Cancel</Button>
              <Button size="sm" onClick={remove} disabled={busy}>Remove</Button>
            </div>
          ) : (
            <>
              <Button size="sm" variant="ghost" onClick={() => setEditing(true)}
                aria-label={`Edit saved memory: ${memory.summary}`}>Edit</Button>
              <Button size="sm" variant="ghost" onClick={pinToggle} disabled={busy}
                aria-pressed={memory.pinned}
                aria-label={`${memory.pinned ? "Unpin" : "Pin"} saved memory: ${memory.summary}`}>
                {memory.pinned ? "Unpin" : "Pin"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setConfirming(true)}
                aria-label={`Remove saved memory: ${memory.summary}`}>Remove</Button>
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
      setError((e as ApiError).userMessage ?? "Couldn't save that change.");
      setBusy(false);
    }
  };

  return (
    <Card className="border-accent">
      <CardBody className="grid gap-3">
        <div>
          <label htmlFor={`cat-${memory.id}`} className="block text-sm text-muted">Category</label>
          <select
            id={`cat-${memory.id}`}
            value={category}
            onChange={(e) => setCategory(e.target.value as MemoryCategory)}
            className="w-full rounded-lg border border-border bg-surface px-3.5 py-3"
          >
            {CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor={`sum-${memory.id}`} className="block text-sm text-muted">Memory</label>
          <Textarea id={`sum-${memory.id}`} value={summary} maxLength={500}
            onChange={(e) => setSummary(e.target.value)} />
        </div>
        <div>
          <label htmlFor={`role-${memory.id}`} className="block text-sm text-muted">Target role (optional)</label>
          <Input id={`role-${memory.id}`} value={role} maxLength={200}
            onChange={(e) => setRole(e.target.value)} />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={pinned} onChange={(e) => setPinned(e.target.checked)} />
          Pin (prioritised when relevant to the role you&apos;re preparing for)
        </label>
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={save} disabled={busy || summary.trim().length === 0}>Save</Button>
          <Button size="sm" variant="ghost" onClick={onCancel} disabled={busy}>Cancel</Button>
        </div>
      </CardBody>
    </Card>
  );
}

function NextRunPreview() {
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
      setError((e as ApiError).userMessage ?? "Couldn't build the preview.");
    } finally {
      setBusy(false);
    }
  }, [role]);

  return (
    <Card>
      <CardBody className="grid gap-3">
        <div>
          <h3 className="text-sm font-semibold">What may be used next time</h3>
          <p className="mt-1 text-xs text-muted">
            Up to {limit} memories may be loaded for a session, most relevant first.
            Pinned memories are preferred when they match the role.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="grow">
            <label htmlFor="preview-role" className="block text-sm text-muted">Target role (optional)</label>
            <Input id="preview-role" value={role} maxLength={200}
              placeholder="e.g. Senior Product Manager"
              onChange={(e) => setRole(e.target.value)} />
          </div>
          <Button size="sm" onClick={run} disabled={busy}>Preview</Button>
        </div>
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        {items !== null ? (
          items.length === 0 ? (
            <p className="text-sm text-muted">
              No saved preparation memories would be loaded for this role.
            </p>
          ) : (
            <ol className="grid gap-2">
              {items.map((it) => (
                <li key={it.id} className="rounded-lg border border-border px-3 py-2">
                  <p className="text-sm break-words">{it.summary}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
                    <Badge>{CATEGORY_LABEL[it.category]}</Badge>
                    {it.pinned ? <Badge tone="low">📌 Pinned</Badge> : null}
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
