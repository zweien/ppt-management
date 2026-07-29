import type { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type Tone =
  | "default" // canvas-soft / body
  | "primary" // ink polarity
  | "success" // link-blue (Vercel success == link)
  | "warning"
  | "error"
  | "violet" // AI / semantic-similar accent
  | "info"; // neutral informational

const TONE: Record<Tone, string> = {
  default: "bg-canvas-soft text-body",
  primary: "bg-primary text-on-primary",
  success: "bg-success-soft text-success-deep",
  warning: "bg-warning-soft text-warning-deep",
  error: "bg-error-soft text-error-deep",
  violet: "bg-violet-soft text-violet",
  info: "bg-link-soft text-link-deep",
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
  /** Render as a dot-prefixed status pill. */
  dot?: boolean;
}

/** Badge — small inline pill (Vercel badge-secondary / semantic status pills). */
export function Badge({ tone = "default", dot = false, className, children, ...rest }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        TONE[tone],
        className,
      )}
      {...rest}
    >
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" />}
      {children}
    </span>
  );
}

export default Badge;
