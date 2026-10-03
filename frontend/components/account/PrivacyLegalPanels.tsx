"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { PrivacyRequestList } from "@/lib/api/types";
import { useT } from "@/components/i18n/I18nProvider";
import { Button } from "@/components/ui/Button";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { useResource } from "@/lib/hooks/useResource";

// P10B-W10.10 candidate-facing privacy-request form and legal-version truth. Copy is localized (8 locales) and makes no guarantee,
// no response-time promise and no compliance claim. Legal acceptance is separate from privacy choices and is never required.

const TYPES: Array<[string, string]> = [
  ["data_access", "prTypeDataAccess"], ["deletion", "prTypeDeletion"], ["correction", "prTypeCorrection"],
  ["consent_question", "prTypeConsentQuestion"], ["other_privacy", "prTypeOther"],
];
const STATUS_KEY: Record<string, string> = {
  submitted: "prStatusSubmitted", acknowledged: "prStatusAcknowledged", in_progress: "prStatusInProgress", waiting_for_user: "prStatusWaiting",
  completed: "prStatusCompleted", closed: "prStatusClosed", rejected: "prStatusRejected",
};
const RESULT_KEY: Record<string, string> = {
  export_provided: "prResultExport", deletion_performed: "prResultDeletion", correction_made: "prResultCorrection",
  information_provided: "prResultInformation", no_action_required: "prResultNoAction", unable_to_verify: "prResultUnverified",
};
const field = "min-h-[44px] w-full rounded border border-border bg-surface px-2 text-sm text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent";

export function PrivacyRequestsPanel() {
  const t = useT();
  const list = useResource<PrivacyRequestList>((signal) => api.privacy.requests({ signal }));
  const [type, setType] = useState("correction");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setCreated(null);
    if (note.trim().length > 1000) return setError(t("dataPrivacy.prErrorNote"));
    setBusy(true);
    try {
      const r = await api.privacy.createRequest({ request_type: type, note: note.trim() || undefined });
      setCreated(t("dataPrivacy.prCreated", { ref: r.public_id }));
      setNote("");
      list.reload();
    } catch (err) {
      setError(err instanceof ApiError && err.status === 409 ? t("dataPrivacy.prErrorTooMany") : t("dataPrivacy.prError"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-4" data-testid="dp-privacy-requests">
      <p className="text-sm text-muted">{t("dataPrivacy.prNoPromise")}</p>
      <form onSubmit={submit} className="grid gap-3" aria-label={t("dataPrivacy.prTitle")}>
        <label className="grid gap-1 text-sm text-foreground">
          {t("dataPrivacy.prTypeLabel")}
          <select className={field} value={type} onChange={(e) => setType(e.target.value)}>
            {TYPES.map(([v, k]) => <option key={v} value={v}>{t(`dataPrivacy.${k}`)}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-foreground">
          {t("dataPrivacy.prNoteLabel")}
          <textarea className={`${field} min-h-[96px] py-2`} value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000}
            aria-describedby="pr-hint" />
          <span id="pr-hint" className="text-xs text-muted">{t("dataPrivacy.prNoteHint")}</span>
        </label>
        {error ? <p role="alert" className="text-sm text-foreground">{error}</p> : null}
        {created ? <p role="status" className="text-sm text-foreground">{created}</p> : null}
        <div><Button type="submit" disabled={busy}>{busy ? t("dataPrivacy.prSending") : t("dataPrivacy.prSubmit")}</Button></div>
      </form>
      <h3 className="text-base font-semibold text-foreground">{t("dataPrivacy.prListTitle")}</h3>
      {list.state.status === "loading" ? <LoadingState /> : list.state.status === "error" ? (
        <ErrorState variant="section" message={t("dataPrivacy.prError")} requestId={list.state.error?.requestId} retrying={list.state.retrying} onRetry={list.reload} />
      ) : (list.state.data?.items ?? []).length === 0 ? <p className="text-sm text-muted">{t("dataPrivacy.prListEmpty")}</p> : (
        <ul className="space-y-2">
          {(list.state.data?.items ?? []).map((r) => (
            <li key={r.public_id} className="rounded border border-border p-3 text-sm text-foreground">
              <p className="font-medium">{t(`dataPrivacy.${TYPES.find(([v]) => v === r.request_type)?.[1] ?? "prTypeOther"}`)}</p>
              <p>{t(`dataPrivacy.${STATUS_KEY[r.status] ?? "prStatusSubmitted"}`)}{r.result_category ? `: ${t(`dataPrivacy.${RESULT_KEY[r.result_category] ?? "prResultInformation"}`)}` : ""}</p>
              <p className="text-xs text-muted">{r.public_id}{r.created_at ? ` · ${new Date(r.created_at).toLocaleDateString()}` : ""}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function LegalVersionsPanel() {
  const t = useT();
  const legal = useResource((signal) => api.privacy.legal({ signal }));
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const accept = async (code: string) => {
    setBusy(code);
    setError(null);
    try {
      await api.privacy.acceptLegal(code);
      legal.reload();
    } catch {
      setError(t("dataPrivacy.legalError"));
    } finally {
      setBusy(null);
    }
  };
  if (legal.state.status === "loading") return <LoadingState />;
  if (legal.state.status === "error")
    return <ErrorState variant="section" message={t("dataPrivacy.legalLoadError")} requestId={legal.state.error?.requestId} retrying={legal.state.retrying} onRetry={legal.reload} />;
  return (
    <div className="space-y-3" data-testid="dp-legal-versions">
      {(legal.state.data?.documents ?? []).map((d) => (
        <div key={d.code} className="rounded border border-border p-3 text-sm text-foreground">
          <p className="font-medium">{d.title}</p>
          <p>{t("dataPrivacy.legalCurrentVersion", { version: d.current_version ?? "-" })}</p>
          <p className="text-muted">{d.effective_at ? t("dataPrivacy.legalEffective", { date: new Date(d.effective_at).toLocaleDateString() }) : t("dataPrivacy.legalEffectiveUnknown")}</p>
          {d.version_is_baseline ? <p className="text-xs text-muted">{t("dataPrivacy.legalBaseline")}</p> : null}
          {d.accepted_current ? (
            <p>{t("dataPrivacy.legalAcceptedOn", { date: d.last_acceptance?.accepted_at ? new Date(d.last_acceptance.accepted_at).toLocaleDateString() : "" })}</p>
          ) : (
            <>
              <p>{t("dataPrivacy.legalNotAcceptedCurrent")}</p>
              {d.last_acceptance ? <p className="text-xs text-muted">{t("dataPrivacy.legalLastRecorded", { version: d.last_acceptance.version })}</p> : null}
              <Button variant="ghost" size="sm" onClick={() => accept(d.code)} disabled={busy === d.code}
                aria-label={`${t("dataPrivacy.legalAcceptButton")}: ${d.title}`}>
                {busy === d.code ? t("dataPrivacy.legalAccepting") : t("dataPrivacy.legalAcceptButton")}
              </Button>
            </>
          )}
        </div>
      ))}
      {error ? <p role="alert" className="text-sm text-foreground">{error}</p> : null}
      <p className="text-xs text-muted">{t("dataPrivacy.legalNote")}</p>
    </div>
  );
}
