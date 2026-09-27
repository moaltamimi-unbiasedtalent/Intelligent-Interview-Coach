import type { Metadata } from "next";
import { PracticeClient } from "@/components/interview/PracticeClient";
import { VoiceCoordinationProvider } from "@/lib/speech/voiceCoordination";

export const metadata: Metadata = { title: "Practice" };

export default async function PracticePage({
  searchParams,
}: {
  searchParams: Promise<{ session?: string; opportunity?: string }>;
}) {
  const { session, opportunity } = await searchParams;
  // VoiceCoordinationProvider scopes STT/TTS mutual exclusion to this surface (P7 closure).
  return (
    <VoiceCoordinationProvider>
      <PracticeClient sessionId={session} opportunityId={opportunity} />
    </VoiceCoordinationProvider>
  );
}
