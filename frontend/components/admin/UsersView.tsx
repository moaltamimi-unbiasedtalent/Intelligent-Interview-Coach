"use client";

import { api } from "@/lib/api/client";
import { P } from "@/lib/admin/capabilities";
import { Panel, PermissionGate, ResourceState, Table, useAdminResource } from "./ui";

export function UsersView() {
  return (
    <PermissionGate anyOf={[P.users]}>
      <Body />
    </PermissionGate>
  );
}

function Body() {
  const loaded = useAdminResource(() => api.admin.users());
  return (
    <ResourceState loaded={loaded}>
      {loaded.state === "ready" ? (
        <Panel title="Accounts (metadata only)">
          <Table
            caption="Accounts"
            rows={loaded.data.users.slice(0, 100)}
            cols={["email", "platform_role", "tier", "status", "email_verified"]}
          />
        </Panel>
      ) : null}
    </ResourceState>
  );
}
