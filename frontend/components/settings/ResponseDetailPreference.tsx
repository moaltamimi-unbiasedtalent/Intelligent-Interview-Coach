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

const OPTIONS: { value: ResponseDetail; label: string; help: string }[] = [
  { value: "brief", label: "Brief", help: "Short answers with the key action first." },
  { value: "detailed", label: "Detailed", help: "More explanation and supporting context." },
];

export function ResponseDetailPreference() {
  const { responseDetail, setResponseDetail, status } = useAuth();
  const [saving, setSaving] = useState<ResponseDetail | null>(null);

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
      <h2 className="text-base font-semibold">Response detail</h2>
      <p className="mt-1 text-sm text-muted">
        How much of Mo&rsquo;s answer to show first. Supporting detail and sources stay
        available behind &ldquo;Show more&rdquo; either way — nothing is removed.
      </p>
      <fieldset className="mt-3 space-y-2" aria-label="Response detail">
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
