"use client";

import { api } from "@/lib/api/client";
import { P } from "@/lib/admin/capabilities";
import { Panel, PermissionGate, ResourceState, Table, useAdminResource } from "./ui";

export function WorkspacesView() {
  return (
    <PermissionGate anyOf={[P.workspaces]}>
      <Body />
    </PermissionGate>
  );
}

function Body() {
  const loaded = useAdminResource(() => api.admin.workspaces());
  return (
    <ResourceState loaded={loaded}>
      {loaded.state === "ready" ? (
        <Panel title="Workspaces (metadata only)">
          <Table caption="Workspaces" rows={loaded.data.workspaces.slice(0, 100)} cols={["id", "name", "status", "member_count"]} />
        </Panel>
      ) : null}
    </ResourceState>
  );
}
