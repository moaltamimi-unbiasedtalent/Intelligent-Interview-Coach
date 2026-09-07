import type { Metadata } from "next";
import { SourcesClient } from "@/components/preparation/SourcesClient";

export const metadata: Metadata = { title: "Sources" };

export default function SourcesPage() {
  return <SourcesClient />;
}
