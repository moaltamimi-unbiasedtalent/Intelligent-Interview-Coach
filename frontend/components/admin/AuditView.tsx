"use client";

import Link from "@/components/ui/VerifiedLink";
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
          <p className="text-xs text-muted">The 100 most recent privileged-action events. For filters, pagination and the audited export, use <Link href="/admin/security#audit" className="underline underline-offset-2">Security, Audit</Link> (the primary audit view).</p>
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
