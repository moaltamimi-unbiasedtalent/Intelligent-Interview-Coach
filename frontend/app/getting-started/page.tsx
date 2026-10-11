import { permanentRedirect } from "next/navigation";

export default function GettingStartedPage() {
  permanentRedirect("/product#how-it-works");
}
