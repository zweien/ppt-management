"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
// (mounted state intentionally unused after cleanup)

/**
 * Lightweight theme provider — avoids next-themes' inline-script approach
 * which mutates <html> before hydration and triggers React #418/#423
 * warnings at the document root (where suppressHydrationWarning does not
 * reliably apply in React 18.3).
 *
 * Instead, theme is read/applied in useEffect (runs AFTER hydration), so
 * the server-rendered <html> and first client render are identical → no
 * hydration mismatch. Theme persists to localStorage; default is light.
 */
type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);
const STORAGE_KEY = "theme";

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Start as "light" on both server and first client render (matches SSR).
  const [theme, setThemeState] = useState<Theme>("light");

  useEffect(() => {
    // Apply persisted theme on mount (client-only, post-hydration).
    const stored = (typeof window !== "undefined" && localStorage.getItem(STORAGE_KEY)) as Theme | null;
    const initial: Theme = stored === "dark" ? "dark" : "light";
    setThemeState(initial);
    document.documentElement.classList.toggle("dark", initial === "dark");
    document.documentElement.style.colorScheme = initial;
  }, []);

  const applyTheme = useCallback((t: Theme) => {
    setThemeState(t);
    if (typeof document !== "undefined") {
      document.documentElement.classList.toggle("dark", t === "dark");
      document.documentElement.style.colorScheme = t;
      try {
        localStorage.setItem(STORAGE_KEY, t);
      } catch {
        /* storage may be unavailable */
      }
    }
  }, []);

  const setTheme = useCallback((t: Theme) => applyTheme(t), [applyTheme]);
  const toggleTheme = useCallback(
    () => applyTheme(theme === "dark" ? "light" : "dark"),
    [theme, applyTheme],
  );

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    // Fallback for any consumer rendered outside provider.
    return {
      theme: "light",
      setTheme: () => {},
      toggleTheme: () => {},
    };
  }
  return ctx;
}
