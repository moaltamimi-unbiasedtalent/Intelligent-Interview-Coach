import { PageHeader } from "@/components/layout/PageHeader";
import { UsersView } from "@/components/admin/UsersView";

export default function AdminUsersViewPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Users" description="Account metadata only. Candidate content is never shown." />
      <UsersView />
    </section>
  );
}
