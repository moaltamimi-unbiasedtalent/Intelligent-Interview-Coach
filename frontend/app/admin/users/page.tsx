import { PageHeader } from "@/components/layout/PageHeader";
import { InvitationsPanel } from "@/components/admin/InvitationsPanel";
import { PermissionGate } from "@/components/admin/ui";
import { UsersView } from "@/components/admin/UsersView";
import { P } from "@/lib/admin/capabilities";

export default function AdminUsersViewPage() {
  return (
    <section className="grid gap-6">
      <div>
        <PageHeader eyebrow="Platform operations" title="Users" description="Account metadata only. Candidate content is never shown." />
        <UsersView />
      </div>
      <div>
        <h2 className="mb-2 text-lg font-semibold">Private beta invitations</h2>
        <PermissionGate anyOf={[P.users]}>
          <InvitationsPanel />
        </PermissionGate>
      </div>
    </section>
  );
}
