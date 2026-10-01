import type { Metadata } from "next";
import { DataPrivacyCenter } from "@/components/account/DataPrivacyCenter";

export const metadata: Metadata = { title: "Your data & privacy" };

export default function AccountDataPage() {
  return <DataPrivacyCenter />;
}
