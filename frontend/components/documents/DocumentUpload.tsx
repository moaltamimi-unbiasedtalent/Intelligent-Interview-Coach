"use client";

/**
 * Reusable private-document upload control (Capstone P4 · P10B Wave 3).
 *
 * This is the ONE governed upload seam. The Documents page uses it today; Wave 4 will reuse
 * the SAME component inside Prepare/Practice (via the documented props) so there is never a
 * second upload pipeline. It performs immediate, localized client-side pre-validation
 * (type + size) for a fast, understandable failure, then delegates to `api.documents.upload`
 * — the backend remains the authority (validation, private storage, scanning, extraction).
 *
 * It never claims OCR/scanning/extraction succeeded; it reports only what the API returned.
 * Uploaded documents are private DATA — never public, never analysed for identity/emotion.
 */

import { useId, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import type { DocumentDetail } from "@/lib/api/types";
import { useI18n } from "@/components/i18n/I18nProvider";
import { Alert } from "@/components/ui/Alert";

/** The single accepted-format allow-list, mirrored from the backend validation contract. */
export const ACCEPTED_EXTENSIONS = ["pdf", "docx", "txt", "png", "jpg", "jpeg"] as const;
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10 MB — matches src/documents/validation.py
export const DOCUMENT_CATEGORIES = ["cv", "job_description", "portfolio", "company_brief", "other"] as const;

export function categoryLabelKey(c: string): string {
  switch (c) {
    case "cv": return "documents.catCv";
    case "job_description": return "documents.catJob";
    case "portfolio": return "documents.catPortfolio";
    case "company_brief": return "documents.catBrief";
    default: return "documents.catOther";
  }
}

export interface DocumentUploadProps {
  /** Called after a successful upload with the created document detail (Wave 4 can chain off it). */
  onUploaded?: (detail: DocumentDetail) => void;
  /** Initial category selection (default "cv"). */
  defaultCategory?: string;
  /**
   * When set, the category is FIXED to this value and the picker is hidden — e.g. a future
   * "Upload your CV" affordance in Prepare. Overrides `showCategory`.
   */
  lockedCategory?: string;
  /** Show the category picker (default true). Ignored when `lockedCategory` is set. */
  showCategory?: boolean;
  /** A compact variant for embedding in a side panel (Wave 4). */
  compact?: boolean;
  className?: string;
}

export function DocumentUpload({
  onUploaded,
  defaultCategory = "cv",
  lockedCategory,
  showCategory = true,
  compact = false,
  className,
}: DocumentUploadProps) {
  const { t } = useI18n();
  const [category, setCategory] = useState(lockedCategory ?? defaultCategory);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const statusId = useId();
  const catId = useId();

  const preValidate = (file: File): string | null => {
    const ext = file.name.includes(".") ? file.name.split(".").pop()!.toLowerCase() : "";
    if (!(ACCEPTED_EXTENSIONS as readonly string[]).includes(ext)) return t("documents.badType");
    if (file.size > MAX_UPLOAD_BYTES) return t("documents.badSize");
    return null;
  };

  const onFile = async (file: File) => {
    setError(null);
    setSuccess(null);
    const problem = preValidate(file);
    if (problem) {
      setError(problem);
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    setBusy(true);
    try {
      const detail = await api.documents.upload(file, lockedCategory ?? category);
      setSuccess(t("documents.uploadSuccess"));
      onUploaded?.(detail);
    } catch (e) {
      // Surface the backend's specific, safe message when present; otherwise a bounded fallback.
      setError(e instanceof ApiError ? e.message : t("documents.uploadFailed"));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const showPicker = !lockedCategory && showCategory;

  return (
    <div className={className}>
      {error ? <Alert tone="danger" className="mb-3">{error}</Alert> : null}
      {success ? <Alert tone="success" className="mb-3">{success}</Alert> : null}

      {!compact ? (
        <p className="text-sm text-muted">{t("documents.uploadWhat")}</p>
      ) : null}

      <div className="mt-3 flex flex-wrap items-end gap-3">
        {showPicker ? (
          <label className="text-sm" htmlFor={catId}>
            <span className="mb-1 block font-medium text-foreground">{t("documents.category")}</span>
            <select
              id={catId}
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              disabled={busy}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm"
            >
              {DOCUMENT_CATEGORIES.map((c) => (
                <option key={c} value={c}>{t(categoryLabelKey(c))}</option>
              ))}
            </select>
          </label>
        ) : null}
        <div>
          <span className="mb-1 block text-sm font-medium text-foreground">{t("documents.chooseFile")}</span>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.txt,.png,.jpg,.jpeg"
            aria-label={t("documents.upload")}
            aria-describedby={statusId}
            disabled={busy}
            onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
            className="block text-sm"
          />
        </div>
      </div>

      {/* Guidance visible BEFORE choosing a file: formats, size, privacy, OCR. */}
      <ul className="mt-2 space-y-0.5 text-xs text-muted">
        <li>{t("documents.uploadFormats")} {t("documents.uploadSize")}</li>
        <li>{t("documents.uploadPrivacy")}</li>
        <li>{t("documents.uploadOcrNote")}</li>
      </ul>

      {/* Live region so assistive tech announces progress/success/failure. */}
      <p id={statusId} role="status" aria-live="polite" className="mt-1 min-h-[1rem] text-xs text-muted">
        {busy ? t("documents.processingHint") : ""}
      </p>
    </div>
  );
}
