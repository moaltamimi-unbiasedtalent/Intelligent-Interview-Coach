import type { Metadata } from "next";
import { Suspense } from "react";
import { SignInForm } from "@/components/auth/SignInForm";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Sign in" };

export default function SignInPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading" />}>
      <SignInForm />
    </Suspense>
  );
}
