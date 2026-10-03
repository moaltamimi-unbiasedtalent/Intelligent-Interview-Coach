"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "@/components/ui/VerifiedLink";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { KnowledgeMeta, KnowledgeQuery } from "@/lib/admin/types";
import { Pager, Panel, PermissionGate, ResourceState, StatusLabel, apiMessage, btn, field, useAdminResource } from "./ui";
import { SCAN_LABEL, label, stateText } from "./knowledgeLabels";

export function KnowledgeView() {
  return (
    <PermissionGate anyOf={[P.knowledge]}>
      <Body />
    </PermissionGate>
  );
}

function Body() {
  const granted = adminPermissions(useAuthOptional()?.account);
  const canManage = hasAnyPermission(granted, [P.knowledgeManage]);
  const [draft, setDraft] = useState<KnowledgeQuery>({});
  const [query, setQuery] = useState<KnowledgeQuery>({ page: 1 });
  const meta = useAdminResource(() => api.admin.knowledgeMeta(), []);
  const loaded = useAdminResource(() => api.admin.knowledgeSources({ ...query, page_size: 25 }), [JSON.stringify(query)]);
  const set = (k: keyof KnowledgeQuery) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setQuery({ ...draft, page: 1 });
  };
  return (
    <div className="grid gap-4">
      <p className="text-sm text-muted">
        This is the platform knowledge base, not candidate data. A source is never used in answers until it has been scanned, parsed,
        reviewed, approved, indexed and explicitly activated.
      </p>
      <ResourceState loaded={meta}>
        {meta.state === "ready" ? (
          <>
            {canManage ? <UploadForm meta={meta.data} onDone={loaded.reload} /> : null}
            <Panel title="Filter sources">
              <form onSubmit={submit} className="flex flex-wrap items-end gap-3" role="search" aria-label="Filter knowledge sources">
                <label className="grid gap-1 text-xs text-muted">
                  Search by name, publisher or reference
                  <input className={field} value={draft.q ?? ""} onChange={set("q")} maxLength={80} />
                </label>
                <Select name="State" value={draft.state} options={meta.data.states.map((s) => [s, stateText(s)])} onChange={set("state")} />
                <Select name="Language" value={draft.language} options={meta.data.languages.map((l) => [l, l])} onChange={set("language")} />
                <Select name="Authority" value={draft.authority} options={meta.data.authority_levels.map((a) => [String(a.level), a.meaning])} onChange={set("authority")} />
                <Select name="Licence" value={draft.licence} options={meta.data.licence_classes.map((c) => [c.code, c.label])} onChange={set("licence")} />
                <Select name="Active" value={draft.active} options={[["true", "Active only"], ["false", "Not active"]]} onChange={set("active")} />
                <button type="submit" className={btn}>Apply</button>
              </form>
              <p className="text-xs text-muted">Search covers titles, publishers and references only, not document text.</p>
            </Panel>
          </>
        ) : null}
      </ResourceState>
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          <Panel title="Sources">
            {loaded.data.items.length === 0 ? <p className="text-sm text-muted">No sources match.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Knowledge sources</caption>
                  <thead>
                    <tr className="text-xs text-muted">
                      {["Source", "Version", "State", "Language", "Authority", "Licence", "Scan", "Chunks", "Updated"].map((c) => (
                        <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {loaded.data.items.map((r) => (
                      <tr key={r.source_public_id} className="border-t border-default">
                        <th scope="row" className="py-1 pr-4 text-left font-medium [overflow-wrap:anywhere]">
                          <Link href={`/admin/knowledge/${r.source_public_id}`} className="underline underline-offset-2">{r.title}</Link>
                          <span className="block text-xs font-normal text-muted">{r.publisher || "Publisher not recorded"}</span>
                        </th>
                        <td className="py-1 pr-4">{r.version}</td>
                        <td className="py-1 pr-4">
                          <StatusLabel tone={r.active ? "ok" : r.state === "failed" || r.state === "rejected" ? "warn" : "neutral"}>{stateText(r.state)}</StatusLabel>
                        </td>
                        <td className="py-1 pr-4">{r.language}</td>
                        <td className="py-1 pr-4">{r.authority_meaning}</td>
                        <td className="py-1 pr-4">{r.licence_label}</td>
                        <td className="py-1 pr-4">{SCAN_LABEL[r.scan_status] ?? label(r.scan_status)}</td>
                        <td className="py-1 pr-4">{r.chunk_count ?? "None"}</td>
                        <td className="py-1 pr-4">{r.updated_at ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <Pager page={loaded.data.page} pageSize={loaded.data.page_size} total={loaded.data.total}
              onPage={(p) => setQuery({ ...query, page: p })} />
          </Panel>
        ) : null}
      </ResourceState>
    </div>
  );
}

export function UploadForm({ meta, onDone, sourceId }: { meta: KnowledgeMeta; onDone: () => void; sourceId?: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    const file = data.get("file");
    setError(null);
    setNotice(null);
    if (!(file instanceof File) || file.size === 0) return setError("Choose a file to upload.");
    if (file.size > meta.upload.max_bytes) return setError(`The file is too large (maximum ${Math.round(meta.upload.max_bytes / 1048576)} MB).`);
    setBusy(true);
    try {
      if (sourceId) await api.admin.addKnowledgeVersion(sourceId, data);
      else await api.admin.createKnowledgeSource(data);
      form.reset();
      setNotice("Uploaded. It is queued for scanning and parsing by a worker.");
      onDone();
    } catch (err) {
      setError(apiMessage(err));
    } finally {
      setBusy(false);
    }
  };
  const exts = meta.upload.extensions.map((x) => `.${x}`).join(", ");
  return (
    <Panel title={sourceId ? "Upload a new version" : "Add a source"}>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2" aria-label={sourceId ? "Upload a new version" : "Add a knowledge source"}>
        {sourceId ? null : (
          <label className="grid gap-1 text-xs text-muted">Title
            <input name="title" className={field} required maxLength={200} />
          </label>
        )}
        <label className="grid gap-1 text-xs text-muted">Publisher
          <input name="publisher" className={field} maxLength={200} />
        </label>
        <label className="grid gap-1 text-xs text-muted">Source reference (https, never fetched)
          <input name="source_url" className={field} maxLength={500} inputMode="url" />
        </label>
        <label className="grid gap-1 text-xs text-muted">Provenance note
          <input name="provenance_note" className={field} maxLength={500} />
        </label>
        <label className="grid gap-1 text-xs text-muted">Source language
          <select name="language" className={field} defaultValue="en">{meta.languages.map((l) => <option key={l} value={l}>{l}</option>)}</select>
        </label>
        <label className="grid gap-1 text-xs text-muted">Authority level
          <select name="authority_level" className={field} defaultValue="3">
            {meta.authority_levels.map((a) => <option key={a.level} value={a.level}>{a.meaning}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-xs text-muted">Licence classification
          <select name="licence_class" className={field} defaultValue="unclear">
            {meta.licence_classes.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-xs text-muted">File ({exts}, up to {Math.round(meta.upload.max_bytes / 1048576)} MB)
          <input name="file" type="file" className={field} accept={meta.upload.extensions.map((x) => `.${x}`).join(",")}
            aria-invalid={error ? true : undefined} aria-describedby={error ? "knowledge-upload-error" : undefined} />
        </label>
        <div className="sm:col-span-2 grid gap-2">
          <p className="text-xs text-muted">The licence classification records how Ask4Mo may use the source. It is an engineering control, not legal advice.</p>
          {error ? <p id="knowledge-upload-error" role="alert" className="text-sm">{error}</p> : null}
          {notice ? <p role="status" className="text-sm">{notice}</p> : null}
          <div><button type="submit" className={btn} disabled={busy}>{busy ? "Uploading..." : "Upload"}</button></div>
        </div>
      </form>
    </Panel>
  );
}

function Select({ name, value, options, onChange }: { name: string; value?: string; options: string[][]; onChange: (e: { target: { value: string } }) => void }) {
  return (
    <label className="grid gap-1 text-xs text-muted">
      {name}
      <select className={field} value={value ?? ""} onChange={(e) => onChange(e)}>
        <option value="">Any</option>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
}

