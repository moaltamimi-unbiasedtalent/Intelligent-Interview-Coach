import { PageHeader } from "@/components/layout/PageHeader";
import { SupportTicketAdminView } from "@/components/admin/SupportTicketAdminView";

export default async function AdminSupportTicketPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Support ticket" description="What the candidate sent to Support, safe account metadata and staff-only notes." />
      <SupportTicketAdminView reference={id} />
    </section>
  );
}
