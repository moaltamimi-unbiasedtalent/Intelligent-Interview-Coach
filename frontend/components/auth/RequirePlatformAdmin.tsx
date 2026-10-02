"use client";

import type { ReactNode } from "react";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { useT } from "@/components/i18n/I18nProvider";
import { LoadingState } from "@/components/ui/States";
import { adminPermissions, hasAnyPermission } from "@/lib/admin/capabilities";

/**
 * Client guard for INTERNAL platform-admin-only pages (P10B-W9.3).
 *
 * Defense-in-depth ONLY — the security boundary is the server (each internal endpoint enforces
 * `require_permission(...)`). This just prevents an ordinary candidate who navigates directly to an
 * internal page from seeing its shell / triggering its client fetches: the gated children never
 * mount for a non-admin, and a safe, localized "access denied" is shown instead (403 semantics, not
 * a network/server error). Permissions come from trusted server-provided account data (`admin_permissions`), never a
 * client override or a client-side role mapping. While the session is still resolving we render a neutral loading state so the
 * privileged content never flashes.
 */
export function RequirePlatformAdmin({
  children,
  anyOf,
}: {
  children: ReactNode;
  /** Render only when the server-resolved permissions include ANY of these (default: any admin permission). */
  anyOf?: readonly string[];
}) {
  const auth = useAuthOptional();
  const t = useT();
  const status = auth?.status;
  const granted = adminPermissions(auth?.account);
  const isAdmin = anyOf ? hasAnyPermission(granted, anyOf) : granted.length > 0;

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
