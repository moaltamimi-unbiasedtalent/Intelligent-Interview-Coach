import type { Metadata } from "next";

import { TransferAccept } from "@/components/workspaces/TransferAccept";

export const metadata: Metadata = { title: "Ownership transfer" };

export default function WorkspaceOwnershipTransferPage() {
  return <TransferAccept />;
}
