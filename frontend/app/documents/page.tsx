import type { Metadata } from "next";
import { Suspense } from "react";
import { DocumentsClient } from "@/components/documents/DocumentsClient";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Documents" };

export default function DocumentsPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading" />}>
      <DocumentsClient />
    </Suspense>
  );
}
