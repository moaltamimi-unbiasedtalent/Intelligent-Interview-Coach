import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { WorkspaceDetail } from "@/components/workspaces/WorkspaceDetail";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Workspace" };

export default async function WorkspaceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const numericId = Number(id);
  if (!Number.isInteger(numericId) || numericId <= 0) notFound();
  return (
    <Suspense fallback={<LoadingState />}>
      <WorkspaceDetail workspaceId={numericId} />
    </Suspense>
  );
}
