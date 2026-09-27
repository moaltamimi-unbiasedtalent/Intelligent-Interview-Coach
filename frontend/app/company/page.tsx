import type { Metadata } from "next";
import { Suspense } from "react";

import { CompanyResearchClient } from "@/components/company/CompanyResearchClient";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Company research" };

export default function CompanyPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading" />}>
      <CompanyResearchClient />
    </Suspense>
  );
}
