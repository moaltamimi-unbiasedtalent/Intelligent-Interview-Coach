import type { Metadata } from "next";
import { Suspense } from "react";
import { PrepareEntry } from "@/components/preparation/PrepareEntry";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Prepare" };

export default function PreparePage() {
  // Suspense boundary: the Agent Coach reads the run id from the URL (useSearchParams).
  return (
    <Suspense fallback={<LoadingState label="Loading your preparation workspace" />}>
      <PrepareEntry />
    </Suspense>
  );
}
