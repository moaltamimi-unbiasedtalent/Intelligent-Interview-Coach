"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { KnowledgeEnvironment, KnowledgeReadiness, KnowledgeReadinessStatus, KnowledgeRetrievalResult } from "@/lib/admin/types";
import { Panel, ResourceState, Stat, StatusLabel, apiMessage, btn, field, useAdminResource, ScrollRegion } from "./ui";

/**
 * W12.4A. Knowledge readiness, the active corpus and a retrieval-ONLY test, on /admin/knowledge (no new destination).
 * Wording is truthful: only `ready` is shown as ok; configuration alone, an existing source or a queued job is never presented as healthy.
 */
// Which knowledge layer a collection belongs to (a collection kind, not a user role).
const COLLECTION_LAYER_LABEL: Record<string, string> = { curated: "Curated", governed: "Governed" };

export const READINESS_TEXT: Record<KnowledgeReadinessStatus, string> = {
  ready: "Ready",
  no_active_sources: "No active sources",
  worker_unavailable: "Indexing worker unavailable",
  index_pending: "Indexing in progress",
  index_failed: "Index build failed",
  store_unavailable: "Retrieval store unavailable",
  collection_missing: "Governed collection missing",
  embedding_provider_unavailable: "Embedding provider unavailable",
  configuration_error: "Configuration problem",
  degraded: "Degraded",
};
const WORKER_TEXT: Record<string, string> = {
  available: "Worker reporting",
  stale: "Worker stale (no recent report)",
  none: "No worker has reported",
  unknown: "Worker state unknown",
};
const COLLECTION_TEXT: Record<string, string> = { ok: "Present", empty_or_missing: "Empty or missing", unavailable: "Unavailable" };
const CURATED_TEXT: Record<string, string> = { available: "Available", empty: "Empty", unavailable: "Unavailable" };
const FAILURE_TEXT: Record<string, string> = {
  unavailable: "A required service was unavailable", no_chunks: "Nothing could be indexed", internal_error: "Unexpected error",
  parse_failed: "The file could not be read", scan_failed: "The malware scan flagged the file", scan_unavailable: "No malware scanner is available",
  no_text: "No text could be extracted",
};

const WORKER_IDENTITY_TEXT: Record<string, string> = {
  match: "Matches the API (same data root, database and embedding settings)",
  mismatch: "Does NOT match the API",
  unrecorded: "A worker is running but has not recorded its environment",
  no_worker: "No worker has reported, so it cannot be compared",
  unknown: "Unknown",
};
const FIELD_TEXT: Record<string, string> = {
  "data_root.short_hash": "data root", "database.fingerprint": "database", embedding: "embedding settings",
};

export function KnowledgeReadinessPanels({ canTest }: { canTest: boolean }) {
  const readiness = useAdminResource(() => api.admin.knowledgeReadiness(), []);
  const active = useAdminResource(() => api.admin.knowledgeActive(), []);
  return (
    <>
      <Panel title="Knowledge readiness">
        <ResourceState loaded={readiness}>{readiness.state === "ready" ? <ReadinessBody r={readiness.data} /> : null}</ResourceState>
      </Panel>
      {readiness.state === "ready" && readiness.data.views ? <KnowledgeViews r={readiness.data} /> : null}
      {readiness.state === "ready" && readiness.data.environment ? <EnvironmentIdentity env={readiness.data.environment} /> : null}
      <Panel title="Active knowledge">
        <ResourceState loaded={active}>
          {active.state === "ready" ? (
            active.data.items.length === 0 ? (
              <p className="text-sm text-muted">No governed knowledge is active. Candidates are served only by the curated knowledge base until a source is activated.</p>
            ) : (
              <ScrollRegion label="Active governed knowledge (scrollable table)">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Active governed knowledge</caption>
                  <thead>
                    <tr className="text-xs text-muted">
                      {["Source", "Version", "Type", "Authority", "Language", "Chunks", "Embedder", "Index", "Activated"].map((c) => (
                        <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {active.data.items.map((i) => (
                      <tr key={i.version_public_id} className="border-t border-default">
                        <th scope="row" className="py-1 pr-4 text-left font-medium [overflow-wrap:anywhere]">{i.title}</th>
                        <td className="py-1 pr-4">{i.version}</td>
                        <td className="py-1 pr-4">{i.source_type}</td>
                        <td className="py-1 pr-4">{i.authority_meaning}</td>
                        <td className="py-1 pr-4">{i.language}</td>
                        <td className="py-1 pr-4">{i.chunk_count}</td>
                        <td className="py-1 pr-4">{i.embedder ?? "Not recorded"}</td>
                        <td className="py-1 pr-4">{i.index_state === "built" ? "Built" : i.index_state === "missing" ? "No index record" : i.index_state}</td>
                        <td className="py-1 pr-4">{i.activated_at ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </ScrollRegion>
            )
          ) : null}
        </ResourceState>
      </Panel>
      {canTest ? <RetrievalTest /> : null}
    </>
  );
}

/** 02A: CURATED and GOVERNED knowledge are different things with different owners; they are never merged into one count. */
function KnowledgeViews({ r }: { r: KnowledgeReadiness }) {
  const v = r.views;
  if (!v) return null;
  return (
    <div className="grid gap-3 md:grid-cols-2" data-testid="knowledge-views">
      <Panel title="Curated knowledge base (read-only)">
        <div className="grid gap-1 text-sm" data-testid="curated-view">
          <p className="text-muted">{v.curated.description}</p>
          <p>Status: <strong>{CURATED_TEXT[v.curated.status] ?? v.curated.status}</strong>{v.curated.chunk_count !== null ? `, ${v.curated.chunk_count} chunks` : ""}</p>
          <p className="text-xs text-muted">Not managed from this page. Counts here are never added to the governed counts.</p>
        </div>
      </Panel>
      <Panel title="Admin-governed knowledge">
        <div className="grid gap-1 text-sm" data-testid="governed-view">
          <p className="text-muted">{v.governed.description}</p>
          <p>Status: <strong>{READINESS_TEXT[v.governed.status as KnowledgeReadinessStatus] ?? v.governed.status}</strong>; {v.governed.active_source_count ?? 0} active source(s){v.governed.chunk_count !== null ? `; ${v.governed.chunk_count} chunks in the store` : ""}</p>
          <p className="text-xs text-muted">Managed on this page. Only active, indexed sources reach candidates.</p>
        </div>
      </Panel>
    </div>
  );
}

function EnvironmentIdentity({ env }: { env: KnowledgeEnvironment }) {
  const g = env.guard;
  const wi = env.worker_identity;
  return (
    <Panel title="Environment identity">
      <div className="grid gap-3" data-testid="env-identity">
        <p className="flex flex-wrap items-center gap-2 text-sm" data-testid="env-guard">
          <StatusLabel tone={g.serving_allowed && g.findings.every((f) => f.severity === "warn") ? "ok" : "warn"}>
            {g.mode === "enforced" ? (g.serving_allowed ? "Serving allowed" : "Serving refused") : "Development: warnings only"}
          </StatusLabel>
          <span>{g.serving_allowed ? "The environment guard allows governed retrieval and uploads." : "The environment guard is refusing governed retrieval and uploads in this environment."}</span>
        </p>
        {g.findings.length ? (
          <ul className="grid gap-1 text-sm" data-testid="env-findings">
            {g.findings.map((f) => (
              <li key={f.code} data-testid={`finding-${f.code}`}>
                <StatusLabel tone="warn">{f.severity === "block" ? (g.enforced ? "Blocking" : "Would block when hosted") : "Warning"}</StatusLabel>{" "}
                {f.message}{f.fields.length ? ` Differs: ${f.fields.map((x) => FIELD_TEXT[x] ?? x).join(", ")}.` : ""}
              </li>
            ))}
          </ul>
        ) : null}
        <dl className="grid gap-1 text-sm sm:grid-cols-[14rem_1fr]">
          <dt className="text-muted">Environment</dt>
          <dd data-testid="env-name">{env.environment}{env.hosted ? " (hosted: fails closed)" : " (development)"}</dd>
          <dt className="text-muted">Registry database</dt>
          <dd data-testid="env-db">{env.database.kind ?? "unknown"}, fingerprint {env.database.fingerprint ? env.database.fingerprint.slice(0, 12) : "unknown"}</dd>
          <dt className="text-muted">Data root</dt>
          <dd data-testid="env-root">{env.data_root.label}, id {env.data_root.short_hash ?? "unknown"}; private files {env.private_files.inside_data_root ? "inside the data root" : "outside the data root"}</dd>
          <dt className="text-muted">Worker identity</dt>
          <dd data-testid="env-worker">{WORKER_IDENTITY_TEXT[wi.status] ?? wi.status}{wi.mismatched_fields.length ? ` (${wi.mismatched_fields.map((x) => FIELD_TEXT[x] ?? x).join(", ")})` : ""}</dd>
          <dt className="text-muted">Embedder</dt>
          <dd data-testid="env-embedder">{env.embedder_identity.provider ?? "unknown"} / {env.embedder_identity.model ?? "unknown"}{env.embedder_identity.degraded ? " (degraded: fallback in use)" : ""}</dd>
          <dt className="text-muted">Index manifest</dt>
          <dd data-testid="env-manifest">{env.manifest.source_version_count} indexed version(s){env.manifest.checksum ? `, checksum ${env.manifest.checksum.slice(0, 12)}` : ""}{env.manifest.embedding_fields_known ? "" : "; embedding model fields not recorded"}</dd>
          <dt className="text-muted">Last indexing</dt>
          <dd data-testid="env-last-indexing">{env.last_indexing.result === "none" ? "No indexing job has run" : `${env.last_indexing.result}${env.last_indexing.at ? ` at ${env.last_indexing.at}` : ""}${env.last_indexing.failure_category ? ` (${env.last_indexing.failure_category.replace(/_/g, " ")})` : ""}`}</dd>
        </dl>
        <ScrollRegion label="Collections (scrollable table)">
          <table className="w-full text-left text-sm" data-testid="env-collections">
            <caption className="sr-only">Collections and chunk counts</caption>
            <thead>
              <tr className="text-xs text-muted">{["Collection", "View", "Chunks", "Persistent"].map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr>
            </thead>
            <tbody>
              {env.collections.map((c) => (
                <tr key={c.collection_id} className="border-t border-default">
                  <th scope="row" className="py-1 pr-4 text-left font-medium">{c.collection_id}</th>
                  <td className="py-1 pr-4">{COLLECTION_LAYER_LABEL[c.role] ?? "Governed"}</td>
                  <td className="py-1 pr-4">{c.chunk_count ?? "unreadable"}</td>
                  <td className="py-1 pr-4">{c.persistent ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
        <p className="text-xs text-muted">Identity shows kinds, short fingerprints and labels only. No connection string, credential or file path is ever shown.</p>
      </div>
    </Panel>
  );
}

function ReadinessBody({ r }: { r: KnowledgeReadiness }) {
  return (
    <div className="grid gap-3" data-testid="knowledge-readiness">
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <StatusLabel tone={r.status === "ready" ? "ok" : "warn"}>{READINESS_TEXT[r.status]}</StatusLabel>
        <span data-testid="readiness-message">{r.message}</span>
      </p>
      <p className="text-sm" data-testid="candidate-ready">
        Candidate retrieval ready: <strong>{r.candidate_retrieval_ready ? "Yes" : "No"}</strong>
        <span className="text-muted"> (curated knowledge base: {CURATED_TEXT[r.curated_corpus.status] ?? r.curated_corpus.status}; governed knowledge: {r.governed_retrieval_ready ? "ready" : "not ready"})</span>
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Active sources" value={r.active_source_count} />
        <Stat label="Indexed active versions" value={r.indexed_active_version_count} />
        <Stat label="Pending indexing jobs" value={r.pending_job_count} />
        <Stat label="Failed indexing jobs" value={r.failed_job_count} />
      </div>
      <dl className="grid gap-1 text-sm sm:grid-cols-[14rem_1fr]">
        <dt className="text-muted">Worker</dt>
        <dd data-testid="worker-state">{WORKER_TEXT[r.worker.status] ?? r.worker.status}{r.worker.last_seen_at ? `, last report ${r.worker.last_seen_at}` : ""}</dd>
        <dt className="text-muted">Embedding</dt>
        <dd data-testid="embedding-state">{r.embedder_state.provider === "local" ? "Offline local embedder" : "Remote provider"}: {r.embedder_state.status.replace(/_/g, " ")}</dd>
        <dt className="text-muted">Collection and store</dt>
        <dd data-testid="store-state">{r.collection} ({COLLECTION_TEXT[r.collection_status] ?? r.collection_status}); store {r.store.kind.replace(/_/g, " ")}{r.store.chunk_count !== null ? `, ${r.store.chunk_count} chunks` : ""}; location {r.store.location.replace(/_/g, " ")}</dd>
        <dt className="text-muted">Last indexed</dt>
        <dd>{r.last_indexed_at ?? "Never"}</dd>
        {r.last_failure_category ? (
          <>
            <dt className="text-muted">Last failure</dt>
            <dd data-testid="failure-state">{FAILURE_TEXT[r.last_failure_category] ?? r.last_failure_category.replace(/_/g, " ")}{r.last_failure_stage ? ` (${r.last_failure_stage})` : ""}</dd>
          </>
        ) : null}
      </dl>
      {r.status === "worker_unavailable" ? (
        <p className="text-xs text-muted">Indexing jobs are queued but cannot progress until a job worker is running (see Jobs).</p>
      ) : null}
    </div>
  );
}

function RetrievalTest() {
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<KnowledgeRetrievalResult | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.admin.testKnowledgeRetrieval(query.trim()));
    } catch (err) {
      // Only a classified API error message is shown; anything else (network text, provider text) becomes a fixed sentence.
      setError(err instanceof ApiError ? apiMessage(err) : "The retrieval test could not be completed.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Panel title="Test retrieval">
      <p className="text-xs text-muted">This tests the active Knowledge retrieval path. It does not call Mo or an LLM.</p>
      <form onSubmit={submit} className="flex flex-wrap items-end gap-3" aria-label="Test knowledge retrieval">
        <label className="grid gap-1 text-xs text-muted">Test query
          <input className={field} value={query} onChange={(e) => setQuery(e.target.value)} maxLength={300} required />
        </label>
        <button type="submit" className={btn} disabled={busy || !query.trim()}>{busy ? "Testing..." : "Test retrieval"}</button>
      </form>
      {error ? <p className="text-sm text-muted" role="alert">{error}</p> : null}
      {result ? (
        <div className="grid gap-2" data-testid="retrieval-result" role="status">
          <p className="text-sm">
            {result.status === "blocked"
              ? "The query was blocked by the retrieval safety screen."
              : result.insufficient_evidence
                ? "Insufficient evidence: nothing relevant was retrieved."
                : `${result.result_count} evidence item(s) from ${result.source_count} source(s).`}
            <span className="text-muted"> Mode {result.retrieval_mode || "none"}, {result.latency.replace(/_/g, " ")}.</span>
          </p>
          {result.sources.length ? (
            <ul className="list-disc pl-5 text-sm">
              {result.sources.map((s) => (
                <li key={`${s.origin}-${s.title}`}>
                  {s.title}{s.publisher ? `, ${s.publisher}` : ""} (authority {s.authority_level}; {s.origin === "admin_governed" ? "Admin-governed" : "curated knowledge base"})
                </li>
              ))}
            </ul>
          ) : null}
          {result.excerpts.length ? (
            <ul className="grid gap-1 text-xs text-muted">
              {result.excerpts.map((x, i) => <li key={i}>{x.text}</li>)}
            </ul>
          ) : null}
          <p className="text-xs text-muted">{result.note}</p>
        </div>
      ) : null}
    </Panel>
  );
}
