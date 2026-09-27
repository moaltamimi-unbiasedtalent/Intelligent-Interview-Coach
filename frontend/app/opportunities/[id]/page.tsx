import type { Metadata } from "next";
import { Suspense } from "react";

import { OpportunityHome } from "@/components/opportunities/OpportunityHome";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Opportunity" };

export default async function OpportunityDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const numericId = Number(id);
  return (
    <Suspense fallback={<LoadingState label="Loading" />}>
      <OpportunityHome opportunityId={numericId} />
    </Suspense>
  );
}
