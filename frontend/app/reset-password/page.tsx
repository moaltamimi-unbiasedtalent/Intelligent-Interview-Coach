import type { Metadata } from "next";
import { Suspense } from "react";
import { ResetPasswordForm } from "@/components/auth/ResetPasswordForm";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Reset password" };

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading" />}>
      <ResetPasswordForm />
    </Suspense>
  );
}
