"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "./ThemeProvider";
import { cn } from "@/lib/cn";

/** Sidebar theme toggle — switches between light (Vercel-native) and dark. */
export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      onClick={toggleTheme}
      aria-label={isDark ? "切换到浅色" : "切换到深色"}
      title={isDark ? "切换到浅色" : "切换到深色"}
      className={cn(
        "inline-flex items-center gap-2 px-2 py-1 rounded-md text-sm transition",
        "text-mute hover:text-ink hover:bg-canvas-soft-2",
      )}
    >
      {isDark ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
      <span className="text-xs">{isDark ? "深色" : "浅色"}</span>
    </button>
  );
}
