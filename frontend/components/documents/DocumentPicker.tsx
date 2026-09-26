"use client";

/**
 * Owner-scoped document picker (P10B Wave 4).
 *
 * Lets a candidate SELECT one of their existing private documents (of a given category) or
 * upload a new one, from inside Prepare/Practice — reusing the ONE governed document system
 * (`api.documents.*` + the shared `DocumentUpload`). It emits only a document ID; the server
 * resolves that id to text/evidence, so no raw document text is held in the browser, in the URL,
 * or in localStorage. Selecting a document never submits anything on its own.
 */

import { useCallback, useEffect, useId, useState } from "react";
import { api } from "@/lib/api/client";
import type { DocumentSummary } from "@/lib/api/types";
import { useI18n } from "@/components/i18n/I18nProvider";
import { DocumentUpload } from "@/components/documents/DocumentUpload";

export function DocumentPicker({
  category,
  value,
  onChange,
  label,
  disabled = false,
}: {
  /** Restrict the list + the upload to a single category (e.g. "job_description"). */
  category: string;
  value: number | null;
  onChange: (id: number | null) => void;
  label: string;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const [docs, setDocs] = useState<DocumentSummary[] | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const selectId = useId();

  const refresh = useCallback(async () => {
    try {
      const res = await api.documents.list();
      setDocs(res.documents.filter((d) => d.category === category));
    } catch {
      setDocs([]);
    }
  }, [category]);

  useEffect(() => { void refresh(); }, [refresh]);

  // Only documents that actually have usable content are selectable (never a failed upload).
  const selectable = (docs ?? []).filter((d) => d.status === "ready" || d.status === "review_required");

  return (
    <div className="grid gap-2">
      <label htmlFor={selectId} className="text-sm font-medium text-foreground">{label}</label>
      {docs === null ? (
        <p className="text-sm text-muted">{t("common.loading")}</p>
      ) : (
        <select
          id={selectId}
          value={value ?? ""}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
          className="min-h-[44px] rounded-lg border border-border bg-surface px-2 text-sm"
        >
          <option value="">{t("prepctx.noneSelected")}</option>
          {selectable.map((d) => (
            <option key={d.id} value={d.id}>{d.title}</option>
          ))}
        </select>
      )}
      {docs !== null && selectable.length === 0 ? (
        <p className="text-xs text-muted">{t("prepctx.pickerEmpty")}</p>
      ) : null}

      <button
        type="button"
        onClick={() => setShowUpload((s) => !s)}
        aria-expanded={showUpload}
        disabled={disabled}
        className="justify-self-start text-sm font-medium text-accent hover:underline disabled:opacity-50"
      >
        {showUpload ? t("prepctx.hideUpload") : t("prepctx.uploadNew")}
      </button>

      {showUpload ? (
        <div className="rounded-lg border border-border bg-surface-2 p-3">
          <DocumentUpload
            compact
            lockedCategory={category}
            onUploaded={(detail) => {
              // Refresh the list and auto-select the newly uploaded document.
              void refresh();
              onChange(detail.id);
              setShowUpload(false);
            }}
          />
        </div>
      ) : null}
    </div>
  );
}
