"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { fetchUiConfig } from "@/lib/version";

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
    // Apply theme on mount (client-only, post-hydration).
    // 优先用用户已选(localStorage);未选时 fallback 到配置的默认主题。
    const hasStored = typeof window !== "undefined" && localStorage.getItem(STORAGE_KEY) !== null;
    const stored = (typeof window !== "undefined" && localStorage.getItem(STORAGE_KEY)) as Theme | null;
    let initial: Theme = stored === "dark" ? "dark" : "light";
    if (!hasStored) {
      // 异步拉配置默认主题;首次渲染先用 light 避免 flash,拿到后再调整。
      fetchUiConfig().then((c) => {
        const cfg = c.default_theme === "dark" ? "dark" : "light";
        // 仅当用户仍未手动选择时才应用配置默认值。
        if (localStorage.getItem(STORAGE_KEY) === null && cfg !== initial) {
          initial = cfg;
          setThemeState(cfg);
          document.documentElement.classList.toggle("dark", cfg === "dark");
          document.documentElement.style.colorScheme = cfg;
        }
      });
    }
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
