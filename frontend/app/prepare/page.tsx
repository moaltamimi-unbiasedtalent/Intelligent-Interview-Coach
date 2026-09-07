import type { Metadata } from "next";
import { PrepareWorkspace } from "@/components/preparation/PrepareWorkspace";

export const metadata: Metadata = { title: "Prepare" };

export default function PreparePage() {
  return <PrepareWorkspace />;
}
