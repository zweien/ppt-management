import type { Config } from "tailwindcss";

/**
 * Design token system based on vercel/DESIGN.md (Vercel design language).
 *
 * All colors reference CSS variables defined in globals.css, so the same
 * utility class (e.g. `bg-canvas`, `text-ink`) automatically responds to
 * light/dark theme. Variables hold space-separated RGB channels, enabling
 * Tailwind's `<alpha-value>` opacity modifier (e.g. `bg-primary/50`).
 */
const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // Surfaces (4-step ladder: canvas → canvas-soft → canvas-soft-2)
        canvas: "rgb(var(--canvas) / <alpha-value>)",
        "canvas-soft": "rgb(var(--canvas-soft) / <alpha-value>)",
        "canvas-soft-2": "rgb(var(--canvas-soft-2) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        // Text
        ink: "rgb(var(--ink) / <alpha-value>)",
        body: "rgb(var(--body) / <alpha-value>)",
        mute: "rgb(var(--mute) / <alpha-value>)",
        // Lines
        hairline: "rgb(var(--hairline) / <alpha-value>)",
        "hairline-strong": "rgb(var(--hairline-strong) / <alpha-value>)",
        // Primary (ink CTA) + on-primary
        primary: "rgb(var(--primary) / <alpha-value>)",
        "on-primary": "rgb(var(--on-primary) / <alpha-value>)",
        // Link / semantic
        link: "rgb(var(--link) / <alpha-value>)",
        "link-deep": "rgb(var(--link-deep) / <alpha-value>)",
        "link-soft": "rgb(var(--link-soft) / <alpha-value>)",
        success: "rgb(var(--success) / <alpha-value>)",
        "success-soft": "rgb(var(--success-soft) / <alpha-value>)",
        "success-deep": "rgb(var(--success-deep) / <alpha-value>)",
        error: "rgb(var(--error) / <alpha-value>)",
        "error-soft": "rgb(var(--error-soft) / <alpha-value>)",
        "error-deep": "rgb(var(--error-deep) / <alpha-value>)",
        warning: "rgb(var(--warning) / <alpha-value>)",
        "warning-soft": "rgb(var(--warning-soft) / <alpha-value>)",
        "warning-deep": "rgb(var(--warning-deep) / <alpha-value>)",
        // Mesh gradient stops (brand decoration, hero scale only)
        violet: "rgb(var(--violet) / <alpha-value>)",
        "violet-soft": "rgb(var(--violet-soft) / <alpha-value>)",
        cyan: "rgb(var(--cyan) / <alpha-value>)",
        pink: "rgb(var(--pink) / <alpha-value>)",
        // Compat alias for legacy brand-* classes during migration (→ primary). Remove after migration.
        brand: {
          DEFAULT: "rgb(var(--primary) / <alpha-value>)",
          50: "rgb(var(--canvas-soft) / <alpha-value>)",
          100: "rgb(var(--link-soft) / <alpha-value>)",
          200: "rgb(var(--hairline) / <alpha-value>)",
          300: "rgb(var(--hairline-strong) / <alpha-value>)",
          400: "rgb(var(--link) / <alpha-value>)",
          500: "rgb(var(--primary) / <alpha-value>)",
          600: "rgb(var(--primary) / <alpha-value>)",
          700: "rgb(var(--primary) / <alpha-value>)",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: {
        none: "0px",
        xs: "4px",
        sm: "6px", // --geist-radius: in-app buttons/inputs/dropdowns
        md: "8px", // --geist-marketing-radius: feature/template cards
        lg: "12px",
        xl: "16px",
        "pill-sm": "64px", // tab-ghost pills
        pill: "100px", // marketing CTA pills
      },
      boxShadow: {
        // Stacked shadows per DESIGN.md (inset hairline + multiple small offsets).
        // Use with explicit ring/hairline where needed.
        "e1": "0 0 0 1px rgb(0 0 0 / 0.08)", // inset hairline equivalent
        "e2": "0px 1px 1px rgb(0 0 0 / 0.04), 0px 2px 2px rgb(0 0 0 / 0.04), 0 0 0 1px rgb(0 0 0 / 0.08)",
        "e3": "0px 2px 2px rgb(0 0 0 / 0.04), 0px 8px 8px -8px rgb(0 0 0 / 0.04), 0 0 0 1px rgb(0 0 0 / 0.08)",
        "e4": "0px 2px 2px rgb(0 0 0 / 0.04), 0px 8px 16px -4px rgb(0 0 0 / 0.04), 0 0 0 1px rgb(0 0 0 / 0.08)",
        "e5": "0px 1px 1px rgb(0 0 0 / 0.03), 0px 8px 16px -4px rgb(0 0 0 / 0.04), 0px 24px 32px -8px rgb(0 0 0 / 0.06), 0 0 0 1px rgb(0 0 0 / 0.08)",
      },
      letterSpacing: {
        // Negative tracking is part of the Vercel voice (display sizes).
        display1: "-0.04em",
        display2: "-0.03em",
      },
      maxWidth: {
        content: "1280px", // --ds-page-width target
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.96)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        "slide-in-right": {
          from: { transform: "translateX(100%)" },
          to: { transform: "translateX(0)" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "spin-fast": {
          to: { transform: "rotate(360deg)" },
        },
      },
      animation: {
        "fade-in": "fade-in 150ms ease-out",
        "scale-in": "scale-in 150ms ease-out",
        "slide-in-right": "slide-in-right 200ms ease-out",
        "slide-up": "slide-up 200ms ease-out",
      },
    },
  },
  plugins: [],
};
export default config;
