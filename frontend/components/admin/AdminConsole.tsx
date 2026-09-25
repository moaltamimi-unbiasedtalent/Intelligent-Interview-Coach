"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { Card, CardBody } from "@/components/ui/Card";
import { api } from "@/lib/api/client";

type Row = Record<string, unknown>;

export function AdminConsole() {
  const { account } = useAuth();
  const isAdmin = account?.platform_role === "platform_admin";
  const [home, setHome] = useState<Row | null>(null);
  const [users, setUsers] = useState<Row[]>([]);
  const [workspaces, setWorkspaces] = useState<Row[]>([]);
  const [providers, setProviders] = useState<Row | null>(null);
  const [audit, setAudit] = useState<Row[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "forbidden" | "error">("loading");

  useEffect(() => {
    if (!isAdmin) {
      setStatus("forbidden");
      return;
    }
    Promise.all([
      api.admin.home(),
      api.admin.users(),
      api.admin.workspaces(),
      api.admin.providers(),
      api.admin.audit(),
    ])
      .then(([h, u, w, p, a]) => {
        setHome(h);
        setUsers(u.users as Row[]);
        setWorkspaces(w.workspaces as Row[]);
        setProviders(p);
        setAudit((a.events as Row[]).slice(0, 15));
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, [isAdmin]);

  if (status === "forbidden")
    return <p className="text-sm text-muted">This area requires a platform administrator account.</p>;
  if (status === "loading") return <p className="text-sm text-muted">Loading…</p>;
  if (status === "error") return <p className="text-sm text-muted">That request could not be processed.</p>;

  const accounts = (home?.accounts ?? {}) as Row;
  const ws = (home?.workspaces ?? {}) as Row;

  return (
    <div className="grid gap-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Users" value={accounts.users_total} />
        <Stat label="Platform admins" value={accounts.platform_admins} />
        <Stat label="Premium accounts" value={accounts.premium_accounts} />
        <Stat label="Open privacy requests" value={accounts.deletion_requests_open} />
        <Stat label="Workspaces" value={ws.workspaces_total} />
        <Stat label="Active shares" value={ws.active_shares} />
        <Stat label="Pending invitations" value={ws.pending_invitations} />
        <Stat label="Knowledge readiness" value={String((home?.knowledge as Row)?.overall_readiness ?? "—")} />
      </div>

      <Panel title="Users (metadata only)">
        <Table rows={users.slice(0, 20)} cols={["email", "platform_role", "tier", "status", "email_verified"]} />
      </Panel>

      <Panel title="Workspaces (metadata only)">
        <Table rows={workspaces.slice(0, 20)} cols={["id", "name", "status", "member_count"]} />
      </Panel>

      <Panel title="Provider status (no secrets)">
        <pre className="overflow-x-auto text-xs text-muted">{JSON.stringify(providers, null, 2)}</pre>
      </Panel>

      <Panel title="Recent audit events">
        <Table rows={audit} cols={["event_type", "result", "actor_user_id", "target_type", "created_at"]} />
      </Panel>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: unknown }) {
  return (
    <Card>
      <CardBody>
        <p className="text-xs text-muted">{label}</p>
        <p className="text-xl font-semibold">{value === undefined || value === null ? "—" : String(value)}</p>
      </CardBody>
    </Card>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardBody className="grid gap-2">
        <h2 className="text-base font-semibold">{title}</h2>
        {children}
      </CardBody>
    </Card>
  );
}

function Table({ rows, cols }: { rows: Row[]; cols: string[] }) {
  if (rows.length === 0) return <p className="text-sm text-muted">Nothing to show.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="text-xs text-muted">
            {cols.map((c) => <th key={c} className="py-1 pr-4 font-medium">{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-default">
              {cols.map((c) => <td key={c} className="py-1 pr-4">{String(r[c] ?? "—")}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
