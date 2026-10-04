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
  aiManage: "platform.ai.manage",
  aiActivate: "platform.ai.activate",
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
  { id: "review", label: "Review / Diagnostics", href: "/review", description: "Evaluation and knowledge diagnostics", anyOf: [P.ai, P.knowledge] },
  { id: "audit", label: "Audit", href: "/admin/audit", description: "Privileged-action log", anyOf: [P.audit] },
  { id: "billing", label: "Billing", href: "/admin/billing", description: "Mock billing (not live)", anyOf: [P.billingRead] },
  { id: "privacy", label: "Privacy", href: "/admin/privacy", description: "Privacy requests", anyOf: [P.privacyRead] },
  { id: "legal", label: "Legal", href: "/admin/legal", description: "Legal document versions", anyOf: [P.privacyRead] },
  { id: "knowledge", label: "Knowledge", href: "/admin/knowledge", description: "Governed knowledge sources", anyOf: [P.knowledge] },
  { id: "configuration", label: "Configuration", href: "/admin/configuration", description: "Platform pause", anyOf: [P.flagsRead] },
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
