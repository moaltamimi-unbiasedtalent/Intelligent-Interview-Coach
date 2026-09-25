import type { Metadata } from "next";

import { ProductContent } from "@/components/marketing/ProductContent";

export const metadata: Metadata = {
  title: "Product",
  description:
    "How Ask4Mo works: grounded preparation, Interview Practice, private documents and Story Bank, multilingual voice, Memory you approve, and private-by-default sharing.",
  alternates: { canonical: "/product" },
};

export default function ProductPage() {
  return <ProductContent />;
}
