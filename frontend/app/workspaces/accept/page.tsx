import type { Metadata } from "next";

import { InviteAccept } from "@/components/workspaces/InviteAccept";

export const metadata: Metadata = { title: "Workspace invitation" };

export default function WorkspaceInvitationPage() {
  return <InviteAccept />;
}
