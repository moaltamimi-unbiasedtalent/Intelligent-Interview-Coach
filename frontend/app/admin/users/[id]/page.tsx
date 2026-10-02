import { PageHeader } from "@/components/layout/PageHeader";
import { UserDetailView } from "@/components/admin/UserDetailView";

export default async function AdminUserDetailViewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Account" description="Safe account detail. No candidate content is shown." />
      <UserDetailView userId={Number(id)} />
    </section>
  );
}
