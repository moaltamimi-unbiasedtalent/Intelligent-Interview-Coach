"use client";

import Link from "@/components/ui/VerifiedLink";
import { api } from "@/lib/api/client";
import { P } from "@/lib/admin/capabilities";
import { KeyValue, Panel, PermissionGate, ResourceState, Stat, StatusLabel, useAdminResource } from "./ui";

export function CommandCenter() {
  return (
    <PermissionGate anyOf={[P.overview]}>
      <CommandCenterBody />
    </PermissionGate>
  );
}

function CommandCenterBody() {
  const loaded = useAdminResource(() => api.admin.home());
  return (
    <ResourceState loaded={loaded}>
      {loaded.state === "ready" ? <Overview home={loaded.data} /> : null}
    </ResourceState>
  );
}

function Overview({ home }: { home: Awaited<ReturnType<typeof api.admin.home>> }) {
  const { build, migrations, health, rate_limit: rl, pause, privacy_requests: pr } = home;
  const paused = Object.entries(pause.paused).filter(([, v]) => v).map(([k]) => k);
  return (
    <div className="grid gap-4">
      <Panel title="Release">
        <KeyValue
          rows={[
            ["Version", build.version],
            ["Git revision", build.git_sha],
            ["Built", build.build_time],
            ["Environment", build.environment],
          ]}
        />
        {build.git_sha === "unknown" ? (
          <p className="text-xs text-muted">Build details were not injected into this deployment.</p>
        ) : null}
      </Panel>

      <Panel title="Database migrations">
        <p>
          {migrations.state === "match" ? (
            <StatusLabel tone="ok">Up to date</StatusLabel>
          ) : migrations.state === "mismatch" ? (
            <StatusLabel tone="warn">Revision mismatch</StatusLabel>
          ) : (
            <StatusLabel tone="neutral">Unknown</StatusLabel>
          )}
        </p>
        <KeyValue
          rows={[
            ["Repository head", migrations.repository_head ?? "unknown"],
            ["Database revision", migrations.database_revision ?? "unknown"],
          ]}
        />
        {migrations.warning ? <p role="alert" className="text-sm">{migrations.warning}</p> : null}
      </Panel>

      <Panel title="Runtime">
        <KeyValue
          rows={[
            ["Database", health.database],
            ["Provider health", "Health not tested"],
            ["Rate limiting", rl.mode === "in_memory_process_local" ? "In memory, per process (not shared across replicas)" : "Shared store"],
            ["Paused capabilities", paused.length ? paused.join(", ") : "None"],
          ]}
        />
        <p className="text-xs text-muted">{pause.note}</p>
      </Panel>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Users" value={home.accounts.users_total} />
        <Stat label="Platform admins" value={home.accounts.platform_admins} />
        <Stat label="Premium accounts" value={home.accounts.premium_accounts} />
        <Stat label="Workspaces" value={home.workspaces.workspaces_total} />
      </div>

      {home.integrations ? (
        <Panel title="Integrations">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Supported integrations" value={home.integrations.total} />
            <Stat label="Configured" value={home.integrations.configured} />
            <Stat label="Not yet tested" value={home.integrations.not_tested} />
            <Stat label="Last test failed" value={home.integrations.unhealthy} />
          </div>
          <p className="text-xs text-muted">Health is shown only after a manual test; nothing is assumed healthy.</p>
        </Panel>
      ) : null}

      {home.knowledge ? (
        <Panel title="Knowledge base">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Awaiting review" value={home.knowledge.awaiting_review} />
            <Stat label="Indexing" value={home.knowledge.indexing} />
            <Stat label="Failed" value={home.knowledge.failed} />
            <Stat label="Active governed sources" value={home.knowledge.active} />
          </div>
          <p className="text-xs text-muted">Counts of Admin-governed sources only. Nothing is retrievable until it is approved, indexed and activated.</p>
        </Panel>
      ) : null}

      {home.jobs ? (
        <Panel title="Jobs">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Queued" value={home.jobs.queue.queued} />
            <Stat label="Running" value={home.jobs.queue.running} />
            <Stat label="Failed" value={home.jobs.queue.failed} />
            <Stat label="Stale leases" value={home.jobs.queue.stale_leases} />
          </div>
          <p className="text-xs text-muted">Queue counts only. A worker is healthy only if it has reported in recently (see Jobs).</p>
        </Panel>
      ) : null}

      {home.plans ? (
        <Panel title="Plans">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(home.plans.by_plan).map(([code, n]) => (
              <Stat key={code} label={`${code} (accounts)`} value={n.users} />
            ))}
            <Stat label="Accounts without a subscription" value={home.plans.accounts_without_subscription} />
          </div>
          <p className="text-xs text-muted">Counts only. There are no prices, payments or revenue figures.</p>
        </Panel>
      ) : null}

      {home.support ? (
        <Panel title="Support">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Open tickets" value={home.support.open} />
            <Stat label="Unassigned" value={home.support.unassigned} />
            <Stat label="Waiting for customer" value={home.support.waiting_for_customer} />
            <Stat label="High or urgent" value={home.support.high_or_urgent} />
          </div>
          <p className="text-xs text-muted">Counts only. No response-time target or breach figure exists.</p>
        </Panel>
      ) : null}

      <Panel title="Privacy requests">
        {pr.status === "operational" ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Open" value={pr.open} />
            <Stat label="Unassigned" value={pr.unassigned_open} />
            <Stat label="Waiting for the candidate" value={pr.waiting_for_user} />
            <Stat label="Completed" value={pr.completed} />
          </div>
        ) : null}
        <p className="text-sm text-muted">{pr.note}</p>
      </Panel>

      {home.diagnostics_links.length ? (
        <Panel title="Diagnostics">
          <ul className="grid gap-1 text-sm">
            {home.diagnostics_links.map((l) => (
              <li key={l.path}>
                <Link href={l.path} className="underline underline-offset-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}
      <p className="text-xs text-muted">{home.boundary}</p>
    </div>
  );
}
