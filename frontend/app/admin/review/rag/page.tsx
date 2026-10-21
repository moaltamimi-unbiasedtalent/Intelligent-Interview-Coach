import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { RagDiagnosticsClient } from "@/components/review/RagDiagnosticsClient";
import { RequirePlatformAdmin } from "@/components/auth/RequirePlatformAdmin";
import { P } from "@/lib/admin/capabilities";

export const metadata: Metadata = { title: "Knowledge & RAG", robots: { index: false, follow: false } };

// P10B-W9.3: internal RAG engineering diagnostics — platform-admin-only.
export default function RagInspectorPage() {
  return (
    <RequirePlatformAdmin anyOf={[P.knowledge]}>
    <section>
      <PageHeader
        eyebrow="Review & Diagnostics"
        title="Knowledge & RAG"
        description="Governed knowledge runtime and offline retrieval-quality evaluation (read-only)."
      />
      <RagDiagnosticsClient />
    </section>
    </RequirePlatformAdmin>
  );
}
