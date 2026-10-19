"use client";

import type { ReactNode } from "react";
import { AdminNavShell } from "@/components/admin/AdminShell";
import { useAuthOptional } from "@/components/auth/AuthProvider";
import { adminPermissions } from "@/lib/admin/capabilities";

/**
 * W12.5 (F-01): Review and Diagnostics now render inside the Admin navigation for an account that holds Admin permissions, so an administrator can move between
 * Review, Diagnostics and every other Admin destination without the global menu. The routes, services and per-page permission gates are unchanged.
 *
 * The candidate's own Agent Inspector (`/review/agent`, owner-scoped, reached from a Coach run) lives under the same prefix and must stay a plain page for a
 * candidate: the Admin navigation is added only when the server returned at least one Admin permission, and it never grants access (every API call is authorised again).
 */
export default function ReviewLayout({ children }: { children: ReactNode }) {
  const auth = useAuthOptional();
  const isAdmin = auth?.status !== "loading" && adminPermissions(auth?.account).length > 0;
  return isAdmin ? <AdminNavShell>{children}</AdminNavShell> : <>{children}</>;
}
