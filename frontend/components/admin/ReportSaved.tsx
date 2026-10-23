"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError } from "@/lib/api/errors";
import { api } from "@/lib/api/client";
import type { BuilderDefinition, ReportFamily, SavedList, SavedReport } from "@/lib/admin/reportBuilder";
import { problemsFromMessage } from "@/lib/admin/reportBuilder";
import { Panel, StatusLabel, btn, field } from "./ui";

// Saved report configuration management (03E2): create, load, rename, update with the expected revision, share flag and delete. A saved report holds the
// DEFINITION only (never results). Every write names the revision it was based on; a 409 is shown as "changed elsewhere" and never overwritten silently.

export function reportErrorText(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 409) return "This saved report was changed elsewhere (or the name is already in use). Reload the list and try again; nothing was overwritten.";
    if (err.status === 403) return "You may not do that with this report.";
    if (err.status === 404) return "That saved report no longer exists.";
    if (err.status === 503) return err.message;
    if (err.status === 422) {
      const p = problemsFromMessage(err.message);
      if (p.length) return p.map((x) => x.message).join(" ");
    }
    if (err.code === "malformed_response") return "The server answered in an unexpected form, so nothing was changed on screen.";
  }
  return "That request could not be processed.";
}

interface Props {
  family: ReportFamily;
  list: SavedList;
  definition: BuilderDefinition | null;       // the current builder definition, null when it is not valid
  loaded: SavedReport | null;                 // the saved report the builder was loaded from
  onLoad: (s: SavedReport) => void;
  onChanged: (selectId?: number | null) => void;
}

export function SavedReports({ family, list, definition, loaded, onLoad, onChanged }: Props) {
  const client = api.admin.reportBuilder[family];
  const [name, setName] = useState("");
  const [shared, setShared] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<{ id: number; value: string } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  const run = async (what: string, fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await fn();
      setNotice(what);
    } catch (err) {
      setError(reportErrorText(err));
    } finally {
      setBusy(false);
    }
  };

  const atLimit = list.items.filter((i) => i.editable).length >= list.max_saved;

  const create = (e: FormEvent) => {
    e.preventDefault();
    if (!definition) return;
    void run("Saved.", async () => {
      const created = await client.create({ name: name.trim(), definition, shared });
      setName("");
      onChanged(created.id);
    });
  };
  const update = () => {
    if (!definition || !loaded) return;
    void run("Updated.", async () => {
      const u = await client.update(loaded.id, { name: loaded.name, definition, shared: loaded.shared, expected_revision: loaded.revision });
      onChanged(u.id);
    });
  };
  const rename = (s: SavedReport, value: string) => {
    if (!s.definition) return;
    const def = s.definition;
    void run("Renamed.", async () => {
      await client.update(s.id, { name: value.trim(), definition: def, shared: s.shared, expected_revision: s.revision });
      setRenaming(null);
      onChanged(loaded?.id === s.id ? s.id : null);
    });
  };
  const toggleShare = (s: SavedReport) => {
    if (!s.definition) return;
    const def = s.definition;
    void run(s.shared ? "Sharing turned off." : "Shared with other administrators who may read this report type.", async () => {
      await client.update(s.id, { name: s.name, definition: def, shared: !s.shared, expected_revision: s.revision });
      onChanged(loaded?.id === s.id ? s.id : null);
    });
  };
  const remove = (s: SavedReport) => {
    void run("Deleted.", async () => {
      await client.remove(s.id, s.revision);
      setConfirmDelete(null);
      onChanged(loaded?.id === s.id ? null : undefined);
    });
  };

  return (
    <Panel title="Saved reports">
      <p className="text-xs text-muted">A saved report stores the definition only, never results or candidate data. {list.items.filter((i) => i.editable).length} of {list.max_saved} used.</p>
      {error ? <p role="alert" className="rounded border border-border p-2 text-sm">{error}</p> : null}
      {notice ? <p role="status" className="text-sm">{notice}</p> : null}
      {list.items.length === 0 ? <p className="text-sm text-muted">No saved reports yet.</p> : (
        <ul className="grid gap-2">
          {list.items.map((s) => (
            <li key={s.id} className="grid gap-1 rounded border border-default p-2">
              <div className="flex flex-wrap items-center gap-2">
                {renaming?.id === s.id ? (
                  <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); rename(s, renaming.value); }}>
                    <label className="grid gap-1 text-sm">New name
                      <input className={field} value={renaming.value} maxLength={60} onChange={(e) => setRenaming({ id: s.id, value: e.target.value })} />
                    </label>
                    <button type="submit" className={btn} disabled={busy}>Save name</button>
                    <button type="button" className={btn} onClick={() => setRenaming(null)}>Cancel</button>
                  </form>
                ) : <strong className="text-sm [overflow-wrap:anywhere]">{s.name}</strong>}
                <StatusLabel tone="neutral">{s.report_id.replace(/_/g, " ")}</StatusLabel>
                {s.shared ? <StatusLabel tone="neutral">Shared</StatusLabel> : null}
                {!s.editable ? <StatusLabel tone="neutral">Shared with you (read only)</StatusLabel> : null}
                {!s.valid ? <StatusLabel tone="warn">No longer valid</StatusLabel> : null}
                {loaded?.id === s.id ? <StatusLabel tone="ok">Loaded in the builder</StatusLabel> : null}
              </div>
              <div className="flex flex-wrap gap-2">
                <button type="button" className={btn} disabled={!s.valid || busy} onClick={() => onLoad(s)} aria-label={`Load ${s.name} into the builder`}>Load</button>
                {s.editable ? (
                  <>
                    <button type="button" className={btn} disabled={!s.valid || busy} onClick={() => setRenaming({ id: s.id, value: s.name })} aria-label={`Rename ${s.name}`}>Rename</button>
                    <button type="button" className={btn} disabled={!s.valid || busy} aria-pressed={s.shared} onClick={() => toggleShare(s)}
                      aria-label={`${s.shared ? "Stop sharing" : "Share"} ${s.name}`}>{s.shared ? "Stop sharing" : "Share"}</button>
                    {confirmDelete === s.id ? (
                      <>
                        <button type="button" className={btn} disabled={busy} onClick={() => remove(s)} aria-label={`Confirm delete ${s.name}`}>Confirm delete</button>
                        <button type="button" className={btn} onClick={() => setConfirmDelete(null)}>Keep</button>
                      </>
                    ) : <button type="button" className={btn} disabled={busy} onClick={() => setConfirmDelete(s.id)} aria-label={`Delete ${s.name}`}>Delete</button>}
                  </>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={create} className="grid gap-2 border-t border-default pt-2">
        <h3 className="text-sm font-semibold">Save the current definition</h3>
        <div className="flex flex-wrap items-end gap-3">
          <label className="grid gap-1 text-sm">Name (3 to 60 characters)
            <input className={field} value={name} minLength={3} maxLength={60} onChange={(e) => setName(e.target.value)} autoComplete="off" />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={shared} onChange={(e) => setShared(e.target.checked)} /> Share with other administrators
          </label>
          <button type="submit" className={btn} disabled={busy || !definition || name.trim().length < 3 || atLimit}>Save as new</button>
          {loaded && loaded.editable ? <button type="button" className={btn} disabled={busy || !definition} onClick={update}>Update &quot;{loaded.name}&quot;</button> : null}
        </div>
        {!definition ? <p className="text-xs text-muted">Fix the definition problems above before saving.</p> : null}
        {atLimit ? <p className="text-xs text-muted">You have reached the limit of {list.max_saved} saved reports. Delete one to save another.</p> : null}
      </form>
    </Panel>
  );
}
