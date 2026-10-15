import type { Metadata } from "next";
import { Suspense } from "react";
import { ReturnPanel } from "@/components/billing/ReturnPanel";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Checkout status", robots: { index: false, follow: false } };

export default function BillingReturnPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <ReturnPanel />
    </Suspense>
  );
}
