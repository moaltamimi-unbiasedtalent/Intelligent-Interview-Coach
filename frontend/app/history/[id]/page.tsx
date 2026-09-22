import type { Metadata } from "next";
import { HistoryDetailClient } from "@/components/interview/HistoryDetailClient";

export const metadata: Metadata = { title: "Interview · History" };

export default async function HistoryDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <HistoryDetailClient reportId={id} />;
}
