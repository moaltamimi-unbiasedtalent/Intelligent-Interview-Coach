import type { Config } from "tailwindcss";

/**
 * Precision Coach design system (Sprint 4 Phase 3A, Concept D).
 * Colours are driven by CSS variables defined in app/globals.css, so light/dark
 * switch happens there (via [data-theme] + prefers-color-scheme) and Tailwind
 * utilities like `bg-background` / `text-foreground` resolve to the active theme.
 */
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        muted: "var(--muted)",
        border: "var(--border)",
        accent: "var(--accent)",
        "accent-foreground": "var(--accent-foreground)",
        secondary: "var(--secondary)",
        success: "var(--success)",
        warning: "var(--warning)",
        danger: "var(--danger)",
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
