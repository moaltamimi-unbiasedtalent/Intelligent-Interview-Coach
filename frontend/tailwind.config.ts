import type { Config } from "tailwindcss";

/**
 * Precision Coach design system (Sprint 4 Phase 3A, Concept D).
 * Colours are driven by CSS variables defined in app/globals.css, so light/dark
 * switch happens there (via [data-theme] + prefers-color-scheme) and Tailwind
 * utilities like `bg-background` / `text-foreground` resolve to the active theme.
 */
/**
 * Theme colour token backed by a CSS variable (light/dark switch lives in globals.css).
 *
 * A plain `"var(--x)"` string is opaque to Tailwind, so alpha utilities such as `border-warning/50`
 * silently emitted NO CSS (TD-W9-01). This function form keeps the unmodified utility byte-for-byte the
 * same (`var(--x)`) and, ONLY when an alpha modifier is used, emits a valid mix of the same token with
 * transparency, so the one colour system (the CSS variables) still drives light and dark.
 */
function token(name: string): string {
  const fn = ({ opacityValue }: { opacityValue?: string }) =>
    opacityValue === undefined || opacityValue === "1" || opacityValue.startsWith("var(")
      ? `var(--${name})`
      : `color-mix(in srgb, var(--${name}) calc(${opacityValue} * 100%), transparent)`;
  // Tailwind accepts a function colour at runtime; its `theme.extend` typing only lists strings.
  return fn as unknown as string;
}

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: token("background"),
        foreground: token("foreground"),
        surface: token("surface"),
        "surface-2": token("surface-2"),
        muted: token("muted"),
        border: token("border"),
        accent: token("accent"),
        "accent-foreground": token("accent-foreground"),
        secondary: token("secondary"),
        success: token("success"),
        warning: token("warning"),
        danger: token("danger"),
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "10px",
        lg: "14px",
      },
      boxShadow: {
        soft: "var(--shadow)",
      },
      maxWidth: {
        content: "1180px",
        reading: "68ch",
      },
    },
  },
  plugins: [],
};

export default config;
