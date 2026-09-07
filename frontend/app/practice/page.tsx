import type { Metadata } from "next";
import { PracticeClient } from "@/components/interview/PracticeClient";

export const metadata: Metadata = { title: "Practice" };

export default async function PracticePage({
  searchParams,
}: {
  searchParams: Promise<{ session?: string }>;
}) {
  const { session } = await searchParams;
  return <PracticeClient sessionId={session} />;
}
