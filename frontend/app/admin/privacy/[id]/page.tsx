import { PageHeader } from "@/components/layout/PageHeader";
import { PrivacyDetailView } from "@/components/admin/PrivacyDetailView";

export default async function AdminPrivacyDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Privacy request" description="Request state, safe account metadata, related job and audit." />
      <PrivacyDetailView id={id} />
    </section>
  );
}
