"use client";

import { useState } from "react";
import Link from "@/components/ui/VerifiedLink";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { KnowledgeVersionDetail } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { UploadForm } from "./KnowledgeView";
import { KeyValue, Panel, PermissionGate, ResourceState, StatusLabel, btn, field, useAdminResource } from "./ui";
import { FAILURE_LABEL, REASON_LABEL, SCAN_LABEL, label, stateText } from "./knowledgeLabels";

export function KnowledgeDetailView({ id }: { id: string }) {
  return (
    <PermissionGate anyOf={[P.knowledge]}>
      <Body id={id} />
    </PermissionGate>
  );
}

type Action = "approve" | "reject" | "index" | "activate" | "retire" | "reprocess" | "delete";
const COPY: Record<Action, { title: string; button: string; body: string }> = {
  approve: { title: "Approve this version?", button: "Approve", body: "Approval records you as the reviewer. It does not index or activate the version; nothing becomes available to candidates yet." },
  reject: { title: "Reject this version?", button: "Reject", body: "A rejected version is never indexed or activated." },
  index: { title: "Index this approved version?", button: "Queue indexing", body: "A worker will embed and index it. It still will not be used in answers until you activate it." },
  activate: { title: "Activate this version?", button: "Activate", body: "From now on this version can be used to ground candidate answers. Any previously active version of this source is retired." },
  retire: { title: "Retire this version?", button: "Retire", body: "It stops being used in candidate answers immediately. Its history is kept; its index entries are removed by a worker." },
  reprocess: { title: "Reprocess this version?", button: "Reprocess", body: "The failed step is queued again." },
  delete: { title: "Delete this version?", button: "Delete", body: "This permanently deletes the uploaded file and record. It is only possible for versions that were never approved." },
};

function Body({ id }: { id: string }) {
  const src = useAdminResource(() => api.admin.knowledgeSource(id), [id]);
  const meta = useAdminResource(() => api.admin.knowledgeMeta(), []);
  const [selected, setSelected] = useState<string | null>(null);
  return (
    <ResourceState loaded={src}>
      {src.state === "ready" ? (
        <div className="grid gap-4">
          <Panel title="Source">
            <KeyValue rows={[["Title", src.data.title], ["Reference", src.data.source_public_id], ["Created", src.data.created_at ?? ""]]} />
          </Panel>
          <Panel title="Versions">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Versions of this source</caption>
                <thead><tr className="text-xs text-muted">{["Version", "State", "Authority", "Updated", ""].map((c, i) => <th key={i} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
                <tbody>
                  {src.data.versions.map((v) => (
                    <tr key={v.version_public_id} className="border-t border-default">
                      <th scope="row" className="py-1 pr-4 text-left font-medium">Version {v.version}</th>
                      <td className="py-1 pr-4"><StatusLabel tone={v.active ? "ok" : "neutral"}>{stateText(v.state)}</StatusLabel></td>
                      <td className="py-1 pr-4">{v.authority_meaning}</td>
                      <td className="py-1 pr-4">{v.updated_at ?? ""}</td>
                      <td className="py-1 pr-4">
                        <button type="button" className={btn} onClick={() => setSelected(v.version_public_id)} aria-label={`Review version ${v.version}`}>Review</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          <VersionPanel key={selected ?? src.data.versions[0].version_public_id} versionId={selected ?? src.data.versions[0].version_public_id} reloadSource={src.reload} />
          {meta.state === "ready" ? <WriteGate><UploadForm meta={meta.data} sourceId={id} onDone={src.reload} /></WriteGate> : null}
        </div>
      ) : null}
    </ResourceState>
  );
}

function WriteGate({ children }: { children: React.ReactNode }) {
  const granted = adminPermissions(useAuthOptional()?.account);
  return hasAnyPermission(granted, [P.knowledgeManage]) ? <>{children}</> : null;
}

function VersionPanel({ versionId, reloadSource }: { versionId: string; reloadSource: () => void }) {
  const loaded = useAdminResource(() => api.admin.knowledgeVersion(versionId), [versionId]);
  return (
    <ResourceState loaded={loaded}>
      {loaded.state === "ready" ? <VersionDetail d={loaded.data} reload={() => { loaded.reload(); reloadSource(); }} /> : null}
    </ResourceState>
  );
}

function VersionDetail({ d, reload }: { d: KnowledgeVersionDetail; reload: () => void }) {
  const granted = adminPermissions(useAuthOptional()?.account);
  const canManage = hasAnyPermission(granted, [P.knowledgeManage]);
  const canApprove = hasAnyPermission(granted, [P.knowledgeApprove]);
  const [pending, setPending] = useState<Action | null>(null);
  const [reason, setReason] = useState("out_of_scope");
  const [notice, setNotice] = useState<string | null>(null);
  const run = async () => {
    if (pending === "reject") await api.admin.knowledgeReject(d.version_public_id, reason);
    else if (pending === "delete") await api.admin.knowledgeDelete(d.version_public_id);
    else if (pending) await api.admin.knowledgeAction(d.version_public_id, pending);
    setNotice(`${COPY[pending as Action].button}: done.`);
    reload();
  };
  const btnFor = (a: Action, show: boolean, allowed: boolean, text: string) =>
    show && allowed ? <button key={a} type="button" className={btn} onClick={() => setPending(a)}>{text}</button> : null;
  const actions = [
    btnFor("approve", d.can.approve, canApprove, "Approve version"),
    btnFor("reject", d.can.reject, canApprove, "Reject version"),
    btnFor("index", d.can.index, canManage, "Queue indexing"),
    btnFor("activate", d.can.activate, canApprove, "Activate version"),
    btnFor("retire", d.can.retire, canManage, "Retire version"),
    btnFor("reprocess", d.can.reprocess, canManage, "Reprocess version"),
    btnFor("delete", d.can.delete, canManage, "Delete version"),
  ].filter(Boolean);
  return (
    <div className="grid gap-4">
      {notice ? <p role="status" className="text-sm">{notice}</p> : null}
      <Panel title={`Version ${d.version}`}>
        <KeyValue rows={[
          ["State", <StatusLabel key="s" tone={d.active ? "ok" : d.state === "failed" || d.state === "rejected" ? "warn" : "neutral"}>{stateText(d.state)}</StatusLabel>],
          ["Language", d.language],
          ["Authority", d.authority_meaning],
          ["Publisher", d.publisher || "Not recorded"],
          ["File", `${d.original_filename} (${d.media_type}, ${d.byte_size} bytes)`],
          ["Checksum (SHA-256)", d.checksum_sha256],
        ]} />
      </Panel>
      <Panel title="Provenance and use rights">
        <KeyValue rows={[
          ["Source reference", d.source_reference ?? "None recorded"],
          ["Provenance note", d.provenance_note || "Not recorded"],
          ["Licence classification", d.licence_label],
          ["Metadata", d.metadata_frozen ? "Frozen after approval; upload a new version to change it" : "Editable until approval"],
        ]} />
        <p className="text-xs text-muted">The classification is an engineering control, not legal advice or a compliance certification.</p>
      </Panel>
      <Panel title="Safety and parsing">
        <KeyValue rows={[
          ["Malware scan", `${SCAN_LABEL[d.scan_status] ?? label(d.scan_status)}${d.scanner ? ` (${d.scanner})` : ""}`],
          ["Extracted characters", d.extracted_chars ?? "Not parsed yet"],
          ["Failure", d.failure_category ? `${FAILURE_LABEL[d.failure_category] ?? label(d.failure_category)} (during ${d.failed_stage ?? "processing"})` : "None"],
          ["Rejection", d.rejection_reason ? REASON_LABEL[d.rejection_reason] ?? label(d.rejection_reason) : "None"],
        ]} />
      </Panel>
      <Panel title="Preview">
        {d.preview ? (
          <>
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded border border-default p-3 text-sm [overflow-wrap:anywhere]" data-testid="knowledge-preview">{d.preview}</pre>
            <p className="text-xs text-muted">{d.preview_is_truncated ? "Showing the first part of the extracted text only." : "Showing the full extracted text."} Shown as plain text; nothing in it is executed.</p>
          </>
        ) : <p className="text-sm text-muted">No preview yet. A worker scans and parses new uploads.</p>}
      </Panel>
      <Panel title="Approval, index and activity">
        <KeyValue rows={[
          ["Approved", d.approved_at ? `${d.approved_at} (reviewer account ${d.approved_by_user_id ?? "unknown"})` : "Not approved"],
          ["Index", d.index ? `${label(d.index.state)}: ${d.index.chunk_count} chunks (${d.index.embedder})` : "Not indexed"],
          ["Active", d.active ? `Active since ${d.activated_at ?? ""}` : "Not active; not used in candidate answers"],
          ["Retired", d.retired_at ?? "No"],
        ]} />
        {d.blockers.length > 0 ? (
          <div role="status" className="text-sm">
            <p className="font-medium">Blocked until these are resolved:</p>
            <ul className="list-disc pl-5">{d.blockers.map((b) => <li key={b}>{b}</li>)}</ul>
          </div>
        ) : null}
        <p className="text-sm">
          Related jobs:{" "}
          {d.parse_job_id ? <Link href={`/admin/jobs/${d.parse_job_id}`} className="underline underline-offset-2">Scan and parse job</Link> : "none"}
          {d.index_job_id ? <>{" · "}<Link href={`/admin/jobs/${d.index_job_id}`} className="underline underline-offset-2">Indexing job</Link></> : null}
        </p>
      </Panel>
      {actions.length > 0 ? (
        <Panel title="Actions">
          <div className="flex flex-wrap gap-3">{actions}</div>
          <p className="text-xs text-muted">Approval, indexing and activation are separate steps. Retiring keeps history; deletion is only for versions that were never approved.</p>
        </Panel>
      ) : null}
      <ActionDialog open={pending !== null} title={pending ? COPY[pending].title : ""} confirmLabel={pending ? COPY[pending].button : ""}
        askReason={false} onConfirm={run} onClose={() => setPending(null)}>
        <p className="text-sm">{pending ? COPY[pending].body : ""}</p>
        {pending === "reject" ? (
          <label className="grid gap-1 text-xs text-muted">
            Reason
            <select className={field} value={reason} onChange={(e) => setReason(e.target.value)}>
              {Object.entries(REASON_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
        ) : null}
      </ActionDialog>
      <Panel title="Recent management actions">
        {d.audit.length === 0 ? <p className="text-sm text-muted">None recorded.</p> : (
          <ul className="grid gap-1 text-sm">{d.audit.map((e, i) => <li key={i}>{label(e.event_type.replace("admin.", ""))} ({e.created_at ?? ""})</li>)}</ul>
        )}
      </Panel>
    </div>
  );
}
