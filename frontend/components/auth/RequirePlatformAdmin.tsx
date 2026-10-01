"use client";

import type { ReactNode } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { useT } from "@/components/i18n/I18nProvider";
import { LoadingState } from "@/components/ui/States";

/**
 * Client guard for INTERNAL platform-admin-only pages (P10B-W9.3).
 *
 * Defense-in-depth ONLY — the security boundary is the server (each internal endpoint enforces
 * `require_platform_admin`). This just prevents an ordinary candidate who navigates directly to an
 * internal page from seeing its shell / triggering its client fetches: the gated children never
 * mount for a non-admin, and a safe, localized "access denied" is shown instead (403 semantics, not
 * a network/server error). Admin state comes from trusted server-provided account data, never a
 * client override. While the session is still resolving we render a neutral loading state so the
 * privileged content never flashes.
 */
export function RequirePlatformAdmin({ children }: { children: ReactNode }) {
  const auth = useAuthOptional();
  const t = useT();
  const status = auth?.status;
  const isAdmin = auth?.account?.platform_role === "platform_admin";

  if (!auth || status === "loading") {
    return <LoadingState label={t("states.loading")} />;
  }
  if (!isAdmin) {
    return (
      <div role="alert" className="rounded-lg border border-border bg-surface px-6 py-10 text-center">
        <h1 className="text-lg font-semibold">{t("states.accessDeniedTitle")}</h1>
        <p className="mx-auto mt-2 max-w-reading text-muted">{t("states.forbidden")}</p>
      </div>
    );
  }
  return <>{children}</>;
}
