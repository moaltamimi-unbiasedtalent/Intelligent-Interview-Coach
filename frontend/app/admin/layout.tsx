import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AdminShell } from "@/components/admin/AdminShell";

export const metadata: Metadata = { title: "Platform Admin", robots: { index: false, follow: false } };

// Internal operations surface. English by design (AD-01). The server enforces authorization on every
// request; the shell and its navigation only reflect the permissions the server returned.
export default function AdminLayout({ children }: { children: ReactNode }) {
  return <AdminShell>{children}</AdminShell>;
}
