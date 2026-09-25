import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { AdminConsole } from "@/components/admin/AdminConsole";

export const metadata: Metadata = { title: "Platform Admin" };

// Internal operations surface (PLATFORM_ADMIN only). English by design (§14): not a
// candidate-facing screen. The server enforces authorization; the client only hides UI.
export default function AdminPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Platform operations"
        title="Platform Admin"
        description="Operational metadata only. No candidate-private content is accessible here."
      />
      <AdminConsole />
    </section>
  );
}
