"use client";

import { useEffect, useState } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { api } from "@/lib/api/client";
import { P, adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";
import type { SpeechConfig, SpeechConfigPatch, SpeechOverview, SpeechProviderReadiness } from "@/lib/admin/types";
import { ActionDialog } from "./ActionDialog";
import { KeyValue, Panel, PermissionGate, ResourceState, StatusLabel, btn, field, useAdminResource } from "./ui";

// Governed speech (W12.4E backend, W12.4F Admin surface). This page records SELECTION and POLICY only: saving a setting never starts a provider, downloads a model or contacts a service.
// There is no path, command, endpoint, secret or model-loading control here by design.

const yn = (v: boolean) => (v ? "Yes" : "No");

export function SpeechView() {
  return (
    <PermissionGate anyOf={[P.flagsRead]}>
      <Body />
    </PermissionGate>
  );
}

function ProviderPanel({ title, r }: { title: string; r: SpeechProviderReadiness }) {
  return (
    <Panel title={title}>
      <p className="text-sm">
        <StatusLabel tone={r.operational ? "ok" : "warn"}>{r.operational ? "Operational" : "Not operational"}</StatusLabel>{" "}
        Configured is not operational: each state below is separate and none implies the next.
      </p>
      <KeyValue rows={[
        ["Provider", r.provider], ["Selected and enabled", yn(r.configured)], ["Runtime dependency available", yn(r.dependency_available)], ["Model weights placed by an operator", yn(r.model_available)],
        ["Ready for offline execution", yn(r.ready_for_offline_execution)], ["Adapter validated with a fixture", yn(r.validated_with_fixture)],
        ["Genuine model execution", r.validated_with_genuine_model], ["Code authorization (live)", r.live_authorized ? "Authorized" : "Not authorized"], ["Deployment", r.deployment],
      ]} />
      {r.blockers.length ? (
        <div>
          <p className="text-xs text-muted">Blockers</p>
          <ul className="list-disc pl-5 text-sm">{r.blockers.map((b) => <li key={b}>{b}</li>)}</ul>
        </div>
      ) : null}
    </Panel>
  );
}

function Body() {
  const auth = useAuthOptional();
  const canManage = hasAnyPermission(adminPermissions(auth?.account), [P.configManage]);
  const data = useAdminResource(() => api.admin.speech(), []);
  const [draft, setDraft] = useState<SpeechConfig | null>(null);
  const [confirm, setConfirm] = useState<SpeechConfigPatch | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const serverConfig = data.state === "ready" ? data.data.config : null;
  useEffect(() => { if (serverConfig) setDraft(serverConfig); }, [serverConfig]);

  const diff = (o: SpeechOverview, d: SpeechConfig): SpeechConfigPatch => {
    const c = o.config;
    const patch: SpeechConfigPatch = {};
    (["stt_enabled", "tts_enabled", "browser_stt_allowed", "browser_tts_allowed", "stt_timeout_seconds", "tts_timeout_seconds"] as const).forEach((k) => {
      if (d[k] !== c[k]) (patch as Record<string, unknown>)[k] = d[k];
    });
    if ([...d.languages].sort().join() !== [...c.languages].sort().join()) patch.languages = d.languages;
    return patch;
  };

  return (
    <div className="grid gap-4">
      <ResourceState loaded={data}>
        {data.state === "ready" && draft ? (() => {
          const o = data.data;
          const patch = diff(o, draft);
          const changed = Object.keys(patch);
          const productLangs = Object.entries(o.language_matrix).filter(([, v]) => v.product_authorized).map(([k]) => k);
          return (
            <>
              <section aria-labelledby="speech-status" className="rounded border-2 border-border p-4">
                <h2 id="speech-status" className="text-lg font-semibold">Server speech: not active</h2>
                <p className="text-sm">Environment: <strong>{o.environment}</strong> (decided by this server). {o.note}</p>
                <p className="text-sm">Browser speech is the active path today. Server providers are implemented and fixture-tested; genuine model execution is NOT VERIFIED and activation is deferred until after capstone submission.</p>
              </section>
              {notice ? <p role="status" className="text-sm">{notice}</p> : null}
              <ProviderPanel title="Speech to text: OpenAI Whisper" r={o.stt} />
              <ProviderPanel title="Text to speech: Kyutai Pocket TTS" r={o.tts} />
              <Panel title="Language matrix">
                <p className="text-xs text-muted">Effective = product-authorized AND verified provider capability AND selected below. Russian is an interface language only and is excluded from speech. Dutch server TTS is unverified.</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <caption className="sr-only">Speech language matrix</caption>
                    <thead><tr className="text-xs text-muted">{["Language", "Product-authorized", "STT provider", "TTS provider", "Selected", "Effective STT", "Effective TTS"].map((c) => <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>)}</tr></thead>
                    <tbody>
                      {Object.entries(o.language_matrix).map(([code, v]) => (
                        <tr key={code} className="border-t border-default">
                          <th scope="row" className="py-1 pr-4 text-left font-medium">{code}</th>
                          <td className="py-1 pr-4">{yn(v.product_authorized)}</td>
                          <td className="py-1 pr-4">{yn(v.stt_provider_supports)}</td>
                          <td className="py-1 pr-4">{v.tts_provider_unverified ? "Unverified" : yn(v.tts_provider_supports)}</td>
                          <td className="py-1 pr-4">{yn(v.admin_selected)}</td>
                          <td className="py-1 pr-4">{yn(v.effective_stt)}</td>
                          <td className="py-1 pr-4">{yn(v.effective_tts)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
              <Panel title="Policy (selection only)">
                <p className="text-xs text-muted">Revision {o.config.revision}{o.config.persisted ? "" : " (defaults, never saved)"}. Enabling a provider records a decision; it does not start anything.</p>
                <fieldset disabled={!canManage} className="grid gap-2 text-sm">
                  <legend className="sr-only">Speech policy</legend>
                  {([["stt_enabled", "Server speech to text selected"], ["tts_enabled", "Server text to speech selected"], ["browser_stt_allowed", "Allow browser dictation (fallback)"], ["browser_tts_allowed", "Allow browser speech output (fallback)"]] as const).map(([k, label]) => (
                    <label key={k} className="flex min-h-[40px] items-center gap-2">
                      <input type="checkbox" checked={draft[k]} onChange={(e) => setDraft({ ...draft, [k]: e.target.checked })} />
                      {label}
                    </label>
                  ))}
                  <div role="group" aria-label="Eligible speech languages" className="flex flex-wrap gap-3">
                    {productLangs.map((code) => (
                      <label key={code} className="flex min-h-[40px] items-center gap-1">
                        <input type="checkbox" checked={draft.languages.includes(code)}
                          onChange={(e) => setDraft({ ...draft, languages: e.target.checked ? [...draft.languages, code] : draft.languages.filter((l) => l !== code) })} />
                        {code}
                      </label>
                    ))}
                  </div>
                  <label className="grid gap-1 text-xs text-muted">Speech to text timeout (seconds, 5 to 120)
                    <input type="number" className={field} min={5} max={120} value={draft.stt_timeout_seconds} onChange={(e) => setDraft({ ...draft, stt_timeout_seconds: Number(e.target.value) })} />
                  </label>
                  <label className="grid gap-1 text-xs text-muted">Text to speech timeout (seconds, 5 to 60)
                    <input type="number" className={field} min={5} max={60} value={draft.tts_timeout_seconds} onChange={(e) => setDraft({ ...draft, tts_timeout_seconds: Number(e.target.value) })} />
                  </label>
                </fieldset>
                {canManage ? (
                  <div className="flex flex-wrap gap-2">
                    <button type="button" className={btn} disabled={!changed.length} onClick={() => setConfirm(patch)}>Save changes</button>
                    <button type="button" className={btn} disabled={!changed.length} onClick={() => setDraft(o.config)}>Discard</button>
                  </div>
                ) : <p className="text-xs text-muted">Your role can view speech governance but cannot change it.</p>}
              </Panel>
              <Panel title="Authorization (code constants, not editable here)">
                <KeyValue rows={Object.entries(o.authorization).map(([k, v]) => [k.replace(/_/g, " "), v ? "Authorized" : "Not authorized"] as [string, string])} />
                <p className="text-xs text-muted">Changing an authorization needs a reviewed code change after the owner approves it. Hosting, licensing, model weights, genuine validation and the server-side recording client are post-submission work.</p>
              </Panel>
            </>
          );
        })() : null}
      </ResourceState>
      <ActionDialog open={confirm !== null} title="Save speech policy?" confirmLabel="Save" reasonRequired onClose={() => setConfirm(null)}
        onConfirm={async (reason) => {
          if (!confirm || data.state !== "ready") return;
          await api.admin.setSpeech(confirm, data.data.config.revision, reason);
          setNotice("Speech policy saved. No provider was started or contacted.");
          data.reload();
        }}>
        <p className="text-sm">Changes: {confirm ? Object.keys(confirm).join(", ") : ""}. Candidate browser speech behaviour follows these settings immediately; server speech stays inactive.</p>
      </ActionDialog>
    </div>
  );
}
