"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function systemTheme(): Theme {
  return typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = localStorage.getItem("iic-theme");
    } catch {
      /* storage unavailable */
    }
    setTheme(stored === "dark" || stored === "light" ? stored : systemTheme());
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("iic-theme", next);
    } catch {
      /* ignore */
    }
  }

  const isDark = theme === "dark";
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      className="inline-flex h-9 min-w-9 items-center justify-center rounded-[8px] border border-border bg-surface px-2.5 text-sm text-muted transition-colors hover:text-foreground"
    >
      {isDark ? "☀" : "☾"}
    </button>
  );
}
