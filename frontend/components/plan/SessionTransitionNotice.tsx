"use client";

import { useT } from "@/components/i18n/I18nProvider";
import { ButtonLink } from "@/components/ui/Button";

/**
 * Shown when an existing Practice session needs an AI model profile the candidate's account can no longer use to continue it (W12.4D-P3 transition addendum).
 * It explains why continuation is unavailable, confirms that saved work is preserved and that the session was NOT switched to another model, and offers a NEW
 * authorized session as the next step. Nothing is regenerated, there is no upgrade or checkout action, and it does not claim anything about outcomes.
 */
export function SessionTransitionNotice() {
  const t = useT();
  return (
    <section role="region" aria-labelledby="session-transition-title" className="mb-4 rounded-lg border border-border bg-surface p-4" data-testid="session-transition-notice">
      <h2 id="session-transition-title" className="text-base font-semibold text-foreground">{t("planUx.transition_title")}</h2>
      <p className="mt-2 text-sm text-foreground">{t("planUx.transition_why")}</p>
      <p className="mt-2 text-sm text-foreground">{t("planUx.transition_preserved")}</p>
      <p className="mt-2 text-sm text-muted">{t("planUx.transition_history")}</p>
      <div className="mt-3">
        <ButtonLink href="/practice">{t("planUx.transition_newSession")}</ButtonLink>
      </div>
    </section>
  );
}
