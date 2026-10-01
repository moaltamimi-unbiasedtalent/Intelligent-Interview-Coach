import type { Metadata } from "next";
import { Suspense } from "react";

import { OpportunitiesClient } from "@/components/opportunities/OpportunitiesClient";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Opportunities" };

export default function OpportunitiesPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <OpportunitiesClient />
    </Suspense>
  );
}
