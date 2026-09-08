import type { Metadata } from "next";
import { ProgressClient } from "@/components/progress/ProgressClient";

export const metadata: Metadata = { title: "Progress" };

export default function ProgressPage() {
  return <ProgressClient />;
}
