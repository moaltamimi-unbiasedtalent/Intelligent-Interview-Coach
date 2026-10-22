"use client";

import { useT } from "@/components/i18n/I18nProvider";
import { useCapabilities } from "@/lib/useCapabilities";
import type { AiProviderMode } from "@/lib/api/types";

/**
 * The AI provider MODE of this environment, visible to every signed-in Candidate (04D, DEMO-02).
 *
 * A keyless review stack and the live stack used to look identical, and a candidate pressing Start Interview on the keyless one saw a generic "temporarily unavailable". The mode comes
 * from the server (`/capabilities.ai_provider_mode`), never from the client: live (a credential is configured; this is configuration, not a health check), offline (test fixtures only,
 * never real coaching), not configured (AI cannot run here) or unknown. Nothing is shown while the capability read is pending or when the server does not state a mode (an older server),
 * so the indicator can never claim live. It deliberately has no live-region role: it is a standing fact of the environment, not an announcement.
 */
const KEYS: Record<AiProviderMode, { label: string; hint: string }> = {
  live: { label: "providerMode.live", hint: "providerMode.liveHint" },
  offline: { label: "providerMode.offline", hint: "providerMode.offlineHint" },
  not_configured: { label: "providerMode.notConfigured", hint: "providerMode.notConfiguredHint" },
  unknown: { label: "providerMode.unknown", hint: "providerMode.unknownHint" },
};

export function ProviderModeIndicator() {
  const t = useT();
  const { capabilities, loading, offline } = useCapabilities();
  const mode = capabilities.ai_provider_mode;
  if (loading || offline || !mode || !(mode in KEYS)) return null;
  const keys = KEYS[mode];
  if (mode === "live") {
    return (
      <p className="mx-auto max-w-content px-5 pt-2 text-right text-xs text-muted" data-testid="ai-provider-mode" data-mode={mode} title={t(keys.hint)}>
        {t(keys.label)}
      </p>
    );
  }
  // Anything that is not a configured live provider is stated plainly, with what it means for the candidate.
  return (
    <div className="mx-auto mt-3 max-w-content px-3 sm:px-4" data-testid="ai-provider-mode" data-mode={mode}>
      <div className="rounded-xl border border-warning/40 bg-warning/10 px-4 py-2 text-sm text-foreground">
        <span className="font-semibold">{t(keys.label)}</span>
        <span className="text-muted"> {t(keys.hint)}</span>
      </div>
    </div>
  );
}
