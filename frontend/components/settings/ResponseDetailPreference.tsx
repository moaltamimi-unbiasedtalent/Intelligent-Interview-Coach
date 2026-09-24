"use client";

/**
 * Response-detail preference control (Capstone P2/E2).
 *
 * Brief vs Detailed is the PRESENTATION depth of Mo's answers — distinct from the
 * model/capability profile (Fast/Balanced/Advanced) and from any future
 * personality/tone setting. It is stored server-side against the account (persists
 * across devices and sign-outs), available to every tier (never paywalled), and is
 * low-sensitivity metadata (never candidate content).
 */

import { useState } from "react";
import type { ResponseDetail } from "@/lib/api/types";
import { useAuth } from "@/components/auth/AuthProvider";
import { useT } from "@/components/i18n/I18nProvider";

export function ResponseDetailPreference() {
  const { responseDetail, setResponseDetail, status } = useAuth();
  const t = useT();
  const [saving, setSaving] = useState<ResponseDetail | null>(null);

  const OPTIONS: { value: ResponseDetail; label: string; help: string }[] = [
    { value: "brief", label: t("settings.brief"), help: t("settings.briefHelp") },
    { value: "detailed", label: t("settings.detailed"), help: t("settings.detailedHelp") },
  ];

  const choose = async (value: ResponseDetail) => {
    if (value === responseDetail) return;
    setSaving(value);
    try {
      await setResponseDetail(value);
    } finally {
      setSaving(null);
    }
  };

  return (
    <div>
      <h2 className="text-base font-semibold">{t("settings.responseDetail")}</h2>
      <p className="mt-1 text-sm text-muted">{t("settings.responseDetailHelp")}</p>
      <fieldset className="mt-3 space-y-2" aria-label={t("settings.responseDetail")}>
        {OPTIONS.map((opt) => {
          const checked = responseDetail === opt.value;
          return (
            <label
              key={opt.value}
              className={`flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2.5 ${
                checked ? "border-accent bg-surface-2" : "border-border"
              }`}
            >
              <input
                type="radio"
                name="response-detail"
                value={opt.value}
                checked={checked}
                disabled={status !== "authenticated" || saving !== null}
                onChange={() => choose(opt.value)}
                className="mt-1"
              />
              <span>
                <span className="block text-sm font-medium text-foreground">
                  {opt.label}
                  {saving === opt.value ? " …" : ""}
                </span>
                <span className="block text-sm text-muted">{opt.help}</span>
              </span>
            </label>
          );
        })}
      </fieldset>
    </div>
  );
}
