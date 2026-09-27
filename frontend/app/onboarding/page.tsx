import type { Metadata } from "next";
import { OnboardingClient } from "@/components/onboarding/OnboardingClient";

export const metadata: Metadata = { title: "Set up Ask4Mo", robots: { index: false, follow: false } };

// First-run onboarding (P10B Wave 2). Auth-gated + focused chrome are applied by AppShell for the
// /onboarding route; RouteGuard sends an account that has not completed onboarding here.
export default function OnboardingPage() {
  return <OnboardingClient />;
}
