import type { Metadata } from "next";
import { Suspense } from "react";
import { PrepareEntry } from "@/components/preparation/PrepareEntry";
import { LoadingState } from "@/components/ui/States";
import { VoiceCoordinationProvider } from "@/lib/speech/voiceCoordination";

export const metadata: Metadata = { title: "Prepare" };

export default function PreparePage() {
  // Suspense boundary: the Agent Coach reads the run id from the URL (useSearchParams).
  // VoiceCoordinationProvider scopes STT/TTS mutual exclusion to this surface (P7 closure).
  return (
    <Suspense fallback={<LoadingState label="Loading your preparation workspace" />}>
      <VoiceCoordinationProvider>
        <PrepareEntry />
      </VoiceCoordinationProvider>
    </Suspense>
  );
}
