import type { SVGProps } from "react";

/**
 * P10B Wave 7: a small, restrained inline-SVG icon set for marketing surfaces - never emoji as
 * product iconography (founder brand rule). Icons are decorative: they are aria-hidden and always
 * accompanied by a text label, so meaning is never carried by the icon (or colour) alone. Line
 * style, stroke=currentColor, so they inherit the design-token colour they are given.
 */

export type IconName =
  | "target" | "search" | "shield" | "chat" | "mic" | "users" | "check";

const PATHS: Record<IconName, string> = {
  // Opportunity - a target
  target: "M12 3a9 9 0 100 18 9 9 0 000-18zm0 4a5 5 0 100 10 5 5 0 000-10zm0 4a1 1 0 100 2 1 1 0 000-2z",
  // Company intelligence - a magnifier
  search: "M11 4a7 7 0 105.2 11.7l4.05 4.05 1.4-1.4-4.05-4.05A7 7 0 0011 4zm0 2a5 5 0 110 10 5 5 0 010-10z",
  // Evidence - a shield
  shield: "M12 2l8 3v6c0 5-3.4 9-8 11-4.6-2-8-6-8-11V5l8-3z",
  // Prepare with Mo - a chat bubble
  chat: "M4 4h16a1 1 0 011 1v11a1 1 0 01-1 1H8l-4 4V5a1 1 0 011-1z",
  // Practice - a microphone
  mic: "M12 3a3 3 0 013 3v5a3 3 0 01-6 0V6a3 3 0 013-3zm-6 8a6 6 0 0012 0h-2a4 4 0 01-8 0H6zm5 7h2v3h-2v-3z",
  // Collaboration - people
  users: "M8 11a3 3 0 100-6 3 3 0 000 6zm8 0a3 3 0 100-6 3 3 0 000 6zM2 19a6 6 0 0112 0v1H2v-1zm12.5 0v1H22v-1a6 6 0 00-9-5.2A7.9 7.9 0 0114.5 19z",
  // Differentiator - a check
  check: "M20 6L9 17l-5-5 1.4-1.4L9 14.2l9.6-9.6L20 6z",
};

export function MarketingIcon({ name, ...props }: { name: IconName } & SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false" {...props}>
      <path d={PATHS[name]} />
    </svg>
  );
}
