import type { Metadata } from "next";
import { Suspense } from "react";
import { SupportHome } from "@/components/support/SupportHome";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Support" };

export default function SupportPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <SupportHome />
    </Suspense>
  );
}
