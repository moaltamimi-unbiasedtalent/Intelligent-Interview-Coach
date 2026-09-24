import type { Metadata } from "next";
import { Suspense } from "react";
import { VerifyEmailPanel } from "@/components/auth/VerifyEmailPanel";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Verify email" };

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading" />}>
      <VerifyEmailPanel />
    </Suspense>
  );
}
