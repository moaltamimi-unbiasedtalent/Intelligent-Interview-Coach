"use client";

import { api } from "@/lib/api/client";
import { P } from "@/lib/admin/capabilities";
import { Panel, PermissionGate, ResourceState, Table, useAdminResource } from "./ui";

export function AuditView() {
  return (
    <PermissionGate anyOf={[P.audit]}>
      <Body />
    </PermissionGate>
  );
}

function Body() {
  const loaded = useAdminResource(() => api.admin.audit());
  return (
    <ResourceState loaded={loaded}>
      {loaded.state === "ready" ? (
        <Panel title="Recent events">
          <Table
            caption="Recent audit events"
            rows={loaded.data.events.slice(0, 100).map((e) => ({
              ...e,
              change: e.context && "before" in e.context ? `${String(e.context.before)} to ${String(e.context.after)}` : "",
            }))}
            cols={["created_at", "event_type", "result", "actor_user_id", "target_type", "target_id", "change", "request_id"]}
          />
        </Panel>
      ) : null}
    </ResourceState>
  );
}
