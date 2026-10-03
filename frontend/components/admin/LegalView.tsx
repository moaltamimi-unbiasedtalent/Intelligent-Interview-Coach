"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import { ActionDialog } from "./ActionDialog";
import { Panel, PermissionGate, ResourceState, Stat, StatusLabel, apiMessage, btn, field, useAdminResource } from "./ui";

export function LegalView() {
  return (
    <PermissionGate anyOf={[P.privacyRead]}>
      <Body />
    </PermissionGate>
  );
}

const STATE_LABEL: Record<string, string> = { draft: "Draft", published: "Current (published)", retired: "Retired" };

function Body() {
  const granted = adminPermissions(useAuthOptional()?.account);
  const canManage = hasAnyPermission(granted, [P.legalManage]);
  const loaded = useAdminResource(() => api.admin.legalOverview(), []);
  const [publishing, setPublishing] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const publish = async () => {
    if (publishing === null) return;
    await api.admin.legalPublish(publishing);
    setNotice("Version published. It is now the current version and can no longer be edited.");
    loaded.reload();
  };
  return (
    <div className="grid gap-4">
      <p className="text-sm text-muted">
        These are the versions of the Terms, Privacy notice and AI transparency pages that Ask4Mo has registered. The text itself stays in the
        product pages; a version records its reference, effective date and content hash. Published versions cannot be changed: new text is a new
        version. Counts show recorded acceptances only. This is not a compliance measure.
      </p>
      {notice ? <p role="status" className="text-sm">{notice}</p> : null}
      <ResourceState loaded={loaded}>
        {loaded.state === "ready" ? (
          <>
            {loaded.data.documents.map((doc) => (
              <Panel key={doc.code} title={doc.title}>
                <div className="grid gap-3 sm:grid-cols-3">
                  <Stat label="Current version" value={doc.current?.version ?? "None"} />
                  <Stat label="Accepted the current version" value={doc.current_accepted} />
                  <Stat label="No acceptance recorded" value={doc.current_not_recorded} />
                </div>
                {doc.current?.is_baseline ? <p className="text-xs text-muted">The current version is a baseline created when versioning was introduced. Its effective date was not recorded.</p> : null}
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <caption className="sr-only">{doc.title} versions</caption>
                    <thead><tr className="text-xs text-muted">{["Version", "State", "Effective", "Published", "Reference", "Content hash", "Acceptances", ""].map((c, i) => <th key={i} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
                    <tbody>
                      {doc.versions.map((v) => (
                        <tr key={v.id} className="border-t border-default">
                          <th scope="row" className="py-1 pr-4 text-left font-medium">{v.version}{v.is_baseline ? " (baseline)" : ""}</th>
                          <td className="py-1 pr-4"><StatusLabel tone={v.state === "published" ? "ok" : "neutral"}>{STATE_LABEL[v.state] ?? v.state}</StatusLabel></td>
                          <td className="py-1 pr-4">{v.effective_at ?? "Not recorded"}</td>
                          <td className="py-1 pr-4">{v.published_at ?? "Not published"}</td>
                          <td className="py-1 pr-4">{v.content_ref}</td>
                          <td className="py-1 pr-4 [overflow-wrap:anywhere]">{v.content_hash ? `${v.content_hash.slice(0, 12)}…` : "None"}</td>
                          <td className="py-1 pr-4">{v.acceptances ?? 0}</td>
                          <td className="py-1 pr-4">
                            {canManage && v.state === "draft" ? (
                              <button type="button" className={btn} onClick={() => setPublishing(v.id)} aria-label={`Publish ${doc.title} version ${v.version}`}>Publish</button>
                            ) : null}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {canManage ? <DraftForm code={doc.code} title={doc.title} onDone={loaded.reload} /> : null}
              </Panel>
            ))}
            <p className="text-xs text-muted">{loaded.data.note} Active accounts: {loaded.data.active_accounts}.</p>
          </>
        ) : null}
      </ResourceState>
      <ActionDialog open={publishing !== null} title="Publish this version?" confirmLabel="Publish" askReason={false} onConfirm={publish} onClose={() => setPublishing(null)}>
        <p className="text-sm">Publishing makes this the current version and retires the previous one. A published version can never be edited. Candidates are not forced to re-accept.</p>
      </ActionDialog>
    </div>
  );
}

function DraftForm({ code, title, onDone }: { code: string; title: string; onDone: () => void }) {
  const [v, setV] = useState({ version: "", content_ref: "", content_hash: "", effective_at: "" });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value });
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    try {
      await api.admin.legalCreateDraft(code, v);
      setNotice("Draft registered. Publish it when the text and hash are final.");
      setV({ version: "", content_ref: "", content_hash: "", effective_at: "" });
      onDone();
    } catch (err) {
      setError(apiMessage(err));
    }
  };
  const id = `legal-${code}`;
  return (
    <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2" aria-label={`Register a draft ${title} version`}>
      <label className="grid gap-1 text-xs text-muted">New version label
        <input className={field} value={v.version} onChange={set("version")} maxLength={32} required aria-describedby={error ? `${id}-error` : undefined} />
      </label>
      <label className="grid gap-1 text-xs text-muted">Page path or https reference
        <input className={field} value={v.content_ref} onChange={set("content_ref")} maxLength={300} required />
      </label>
      <label className="grid gap-1 text-xs text-muted">Content hash (SHA-256, 64 hex characters)
        <input className={field} value={v.content_hash} onChange={set("content_hash")} maxLength={64} />
      </label>
      <label className="grid gap-1 text-xs text-muted">Effective date (ISO date)
        <input className={field} value={v.effective_at} onChange={set("effective_at")} maxLength={40} placeholder="2026-12-01" />
      </label>
      <div className="sm:col-span-2 grid gap-2">
        {error ? <p id={`${id}-error`} role="alert" className="text-sm">{error}</p> : null}
        {notice ? <p role="status" className="text-sm">{notice}</p> : null}
        <div><button type="submit" className={btn}>Register draft version</button></div>
      </div>
    </form>
  );
}
