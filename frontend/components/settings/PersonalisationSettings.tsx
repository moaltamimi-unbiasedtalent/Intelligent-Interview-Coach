"use client";

/**
 * Personalisation settings (P10B Wave 2) — edit everything onboarding configured, later.
 *
 * Extends the EXISTING Settings + preference architecture (no second settings system): preferred
 * name, career focus (target role + geography) and Mo coaching style, all persisted via
 * `api.auth.updatePreferences` and reconciled through the auth provider. It also links back to the
 * full setup. Coaching style is tone only (the note says so); geography is independent of language.
 */

import { useEffect, useState } from "react";
import Link from "next/link";

import { api } from "@/lib/api/client";
import { useAuth } from "@/components/auth/AuthProvider";
import { useI18n } from "@/components/i18n/I18nProvider";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { CoachingStyleField, type CoachingStyle } from "@/components/settings/CoachingStyleField";
import { CareerGeographyField, type CareerGeography } from "@/components/settings/CareerGeographyField";

export function PersonalisationSettings() {
  const { account, refresh, status } = useAuth();
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [geography, setGeography] = useState<CareerGeography>("");
  const [coaching, setCoaching] = useState<CoachingStyle>("balanced");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (hydrated || !account) return;
    setName(account.display_name ?? "");
    setTargetRole(account.target_role ?? "");
    setGeography((account.career_geography ?? "") as CareerGeography);
    setCoaching(((account.coaching_style as CoachingStyle) || "balanced"));
    setHydrated(true);
  }, [account, hydrated]);

  const save = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await api.auth.updatePreferences({
        display_name: name.trim(), target_role: targetRole.trim(),
        career_geography: geography, coaching_style: coaching,
      });
      await refresh();
      setSaved(true);
    } finally {
      setSaving(false);
    }
  };

  const disabled = status !== "authenticated" || saving;

  return (
    <div className="grid gap-4">
      <h2 className="text-base font-semibold">{t("trustUx.settingsProfileTitle")}</h2>
      <label className="grid gap-1">
        <span className="text-sm font-medium text-foreground">{t("onboarding.nameLabel")}</span>
        <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={255} disabled={disabled} />
      </label>
      <label className="grid gap-1">
        <span className="text-sm font-medium text-foreground">{t("onboarding.targetRoleLabel")}</span>
        <Input value={targetRole} onChange={(e) => setTargetRole(e.target.value)} maxLength={200} disabled={disabled} />
      </label>
      <CareerGeographyField value={geography} onChange={setGeography} disabled={disabled} />
      <CoachingStyleField value={coaching} onChange={setCoaching} disabled={disabled} />
      <div className="flex items-center gap-3">
        <Button onClick={save} disabled={disabled} aria-busy={saving}>
          {saving ? t("onboarding.saving") : t("settings.savePersonalisation")}
        </Button>
        <span role="status" aria-live="polite" className="text-sm text-muted">
          {saved ? t("settings.saved") : ""}
        </span>
      </div>
      <p className="text-sm text-muted">
        <Link href="/onboarding" className="font-medium text-accent hover:underline">
          {t("settings.revisitSetup")}
        </Link>
      </p>
    </div>
  );
}
