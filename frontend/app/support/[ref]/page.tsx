import type { Metadata } from "next";
import { Suspense } from "react";
import { SupportTicketView } from "@/components/support/SupportTicketView";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Support request" };

export default async function SupportTicketPage({ params }: { params: Promise<{ ref: string }> }) {
  const { ref } = await params;
  return (
    <Suspense fallback={<LoadingState />}>
      <SupportTicketView publicId={ref} />
    </Suspense>
  );
}
