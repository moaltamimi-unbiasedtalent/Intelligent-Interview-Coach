/**
 * Admin capability contract (P10B-W10.1). UX ONLY.
 *
 * The backend resolves the signed-in account's role to permissions and returns them as
 * `account.admin_permissions`. This module never maps roles to permissions (that mapping lives
 * only on the server) and never reads or writes browser storage. Hiding a destination is a
 * convenience; every admin API call is authorised again by the server.
 */
import type { AccountResponse } from "@/lib/api/types";

export const P = {
  overview: "platform.overview.read",
  users: "platform.users.read",
  workspaces: "platform.workspaces.read",
  audit: "platform.audit.read",
  integrations: "platform.integrations.read",
  ai: "platform.ai.read",
  knowledge: "platform.knowledge.read",
  usersManage: "platform.users.manage",
  roleAssign: "platform.users.role.assign",
  sessionsRevoke: "platform.users.sessions.revoke",
  workspacesManage: "platform.workspaces.manage",
  integrationsManage: "platform.integrations.manage",
  secretRotate: "platform.integrations.secret.rotate",
  plansRead: "platform.plans.read",
  plansManage: "platform.plans.manage",
  subscriptionsManage: "platform.subscriptions.manage",
  supportRead: "platform.support.read",
  supportReply: "platform.support.reply",
  supportManage: "platform.support.manage",
  supportNote: "platform.support.note",
  jobsRead: "platform.jobs.read",
  jobsManage: "platform.jobs.manage",
  billingRead: "platform.billing.read",
  billingRecover: "platform.billing.recover",
  billingRefund: "platform.billing.refund",
  priceChange: "platform.plans.price.change",
  privacyRead: "platform.privacy.read",
  privacyExecute: "platform.privacy.execute",
  legalManage: "platform.legal.manage",
  knowledgeManage: "platform.knowledge.manage",
  knowledgeApprove: "platform.knowledge.approve",
  flagsRead: "platform.flags.read",
  flagsManage: "platform.flags.manage",
  configManage: "platform.config.manage",
  reportsRead: "platform.reports.read",
  reportsCommercial: "platform.reports.commercial.read",
  aiManage: "platform.ai.manage",
  aiActivate: "platform.ai.activate",
  securityRead: "platform.security.read",
  securityManage: "platform.security.manage",
  incidentsManage: "platform.incidents.manage",
  auditExport: "platform.audit.export",
} as const;

export interface AdminDestination {
  id: string;
  label: string;
  href: string;
  description: string;
  /** Visible when the caller holds ANY of these permissions. */
  anyOf: readonly string[];
}

/** Only destinations that are operational TODAY. Support, Billing, Jobs, etc. are not listed. */
export const ADMIN_DESTINATIONS: readonly AdminDestination[] = [
  { id: "overview", label: "Overview", href: "/admin", description: "Command Center", anyOf: [P.overview] },
  { id: "users", label: "Users", href: "/admin/users", description: "Account metadata", anyOf: [P.users] },
  { id: "workspaces", label: "Workspaces", href: "/admin/workspaces", description: "Workspace metadata", anyOf: [P.workspaces] },
  { id: "plans", label: "Plans", href: "/admin/plans", description: "Plans and entitlements", anyOf: [P.plansRead] },
  { id: "support", label: "Support", href: "/admin/support", description: "Customer support queue", anyOf: [P.supportRead] },
  { id: "review", label: "Review / Diagnostics", href: "/admin/review", description: "Evaluation and knowledge diagnostics", anyOf: [P.ai, P.knowledge] },
  { id: "security", label: "Security", href: "/admin/security", description: "Events, incidents, alerts and role approvals", anyOf: [P.securityRead, P.audit, P.roleAssign] },
  { id: "audit", label: "Audit", href: "/admin/audit", description: "Privileged-action log", anyOf: [P.audit] },
  { id: "billing", label: "Billing", href: "/admin/billing", description: "Billing operations and mock records (not live)", anyOf: [P.billingRead] },
  { id: "privacy", label: "Privacy", href: "/admin/privacy", description: "Privacy requests", anyOf: [P.privacyRead] },
  { id: "legal", label: "Legal", href: "/admin/legal", description: "Legal document versions", anyOf: [P.privacyRead] },
  { id: "knowledge", label: "Knowledge", href: "/admin/knowledge", description: "Governed knowledge sources", anyOf: [P.knowledge] },
  { id: "reports", label: "Reports", href: "/admin/reports", description: "Aggregate reporting", anyOf: [P.reportsRead, P.reportsCommercial] },
  { id: "configuration", label: "Configuration", href: "/admin/configuration", description: "Platform pause", anyOf: [P.flagsRead] },
  { id: "speech", label: "Speech", href: "/admin/speech", description: "Governed speech (not active)", anyOf: [P.flagsRead] },
  { id: "flags", label: "Feature flags", href: "/admin/flags", description: "Governed feature flags", anyOf: [P.flagsRead] },
  { id: "ai", label: "AI and models", href: "/admin/ai", description: "Governed model configuration", anyOf: [P.ai] },
  { id: "jobs", label: "Jobs", href: "/admin/jobs", description: "Queue and worker diagnostics", anyOf: [P.jobsRead] },
  { id: "integrations", label: "Integrations", href: "/admin/integrations", description: "Connections and credentials", anyOf: [P.integrations] },
  { id: "providers", label: "Provider status", href: "/admin/providers", description: "Configuration status", anyOf: [P.integrations] },
] as const;

export function adminPermissions(account: Pick<AccountResponse, "admin_permissions"> | null | undefined): readonly string[] {
  return account?.admin_permissions ?? [];
}

export function hasAnyPermission(granted: readonly string[], anyOf: readonly string[]): boolean {
  return anyOf.some((p) => granted.includes(p));
}

export function visibleDestinations(granted: readonly string[]): AdminDestination[] {
  return ADMIN_DESTINATIONS.filter((d) => hasAnyPermission(granted, d.anyOf));
}

/**
 * 03A (REQ-OWN-08): the six owner-approved Admin menu sections. Every destination id appears in exactly one group (enforced by a unit test); a destination's own `anyOf`
 * still decides whether it is shown, and a group with no visible destination is hidden. UX only: the API authorises every request.
 */
export interface AdminGroup {
  id: string;
  label: string;
  destinationIds: readonly string[];
}

export const ADMIN_GROUPS: readonly AdminGroup[] = [
  { id: "command", label: "Command Center", destinationIds: ["overview"] },
  { id: "customers", label: "Customers and Workspaces", destinationIds: ["users", "workspaces", "support", "privacy"] },
  { id: "commercial", label: "Products and Commercial", destinationIds: ["plans", "billing"] },
  { id: "ai", label: "AI and Knowledge", destinationIds: ["ai", "knowledge", "speech", "providers", "review"] },
  { id: "insights", label: "Insights and Operations", destinationIds: ["reports", "jobs", "integrations"] },
  { id: "governance", label: "Governance and Settings", destinationIds: ["security", "audit", "legal", "configuration", "flags"] },
] as const;

export interface VisibleGroup {
  group: AdminGroup;
  destinations: AdminDestination[];
}

/** Visible destinations arranged by section in the declared order. Groups with nothing visible are omitted; a destination missing from every group lands in a trailing "Other" group instead of disappearing. */
export function groupedDestinations(granted: readonly string[]): VisibleGroup[] {
  const visible = visibleDestinations(granted);
  const byId = new Map(visible.map((d) => [d.id, d]));
  const placed = new Set<string>();
  const out: VisibleGroup[] = [];
  for (const group of ADMIN_GROUPS) {
    const destinations = group.destinationIds.map((id) => byId.get(id)).filter((d): d is AdminDestination => Boolean(d));
    destinations.forEach((d) => placed.add(d.id));
    if (destinations.length) out.push({ group, destinations });
  }
  const rest = visible.filter((d) => !placed.has(d.id));
  if (rest.length) out.push({ group: { id: "other", label: "Other", destinationIds: rest.map((d) => d.id) }, destinations: rest });
  return out;
}

/** Quick navigation: filters an ALREADY permission-filtered list. It never adds a destination and uses no data beyond the static labels. */
export function filterDestinations(list: readonly VisibleGroup[], query: string): VisibleGroup[] {
  const q = query.trim().toLowerCase();
  if (!q) return list.map((g) => ({ group: g.group, destinations: [...g.destinations] }));
  return list
    .map((g) => ({
      group: g.group,
      destinations: g.destinations.filter((d) => `${d.label} ${d.description} ${g.group.label}`.toLowerCase().includes(q)),
    }))
    .filter((g) => g.destinations.length > 0);
}

export interface Crumb {
  label: string;
  /** Absent for the current page and for a section heading that has no page of its own. */
  href?: string;
}

function isActiveHref(pathname: string, href: string): boolean {
  return href === "/admin" ? pathname === "/admin" : pathname === href || pathname.startsWith(href + "/");
}

/** The destination (among those given) that owns this path; the longest matching href wins. */
export function currentDestination(pathname: string, list: readonly AdminDestination[]): AdminDestination | undefined {
  return [...list].filter((d) => isActiveHref(pathname, d.href)).sort((a, b) => b.href.length - a.href.length)[0];
}

function segmentLabel(segment: string): string {
  if (/^\d+$/.test(segment) || /^[0-9a-f]{16,}$/i.test(segment)) return "Details";
  const words = decodeURIComponent(segment).replace(/[-_]+/g, " ").trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : "Details";
}

/** Breadcrumb trail: Admin, section, destination, deeper segments. Empty when the path is not an Admin destination the caller can see. */
export function breadcrumbsFor(pathname: string, groups: readonly VisibleGroup[]): Crumb[] {
  const flat = groups.flatMap((g) => g.destinations.map((d) => ({ d, g: g.group })));
  const hit = currentDestination(pathname, flat.map((x) => x.d));
  if (!hit) return [];
  const group = flat.find((x) => x.d.id === hit.id)!.g;
  if (pathname === "/admin") return [{ label: "Admin" }];
  const rest = pathname.slice(hit.href.length).split("/").filter(Boolean);
  const crumbs: Crumb[] = [{ label: "Admin", href: "/admin" }];
  if (hit.id !== "overview") crumbs.push({ label: group.label });
  crumbs.push(rest.length ? { label: hit.label, href: hit.href } : { label: hit.label });
  rest.forEach((seg, i) => crumbs.push(i === rest.length - 1 ? { label: segmentLabel(seg) } : { label: segmentLabel(seg), href: hit.href + "/" + rest.slice(0, i + 1).join("/") }));
  return crumbs;
}
