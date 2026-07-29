import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

type Variant = "marketing" | "soft" | "template" | "flat";

const VARIANT: Record<Variant, string> = {
  // card-marketing: canvas + Level 3 soft stack + 24px padding + 8px radius.
  marketing: "bg-surface text-ink rounded-md p-6 shadow-e3",
  // card-soft: canvas-soft fill.
  soft: "bg-canvas-soft text-ink rounded-md p-6 shadow-e2",
  // template-card: canvas + Level 2 + 16px padding + 16:9 thumb slot.
  template: "bg-surface text-ink rounded-md p-4 shadow-e2",
  // flat — no shadow, just hairline border (for nested panels).
  flat: "bg-surface text-ink rounded-md border border-hairline",
};

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: Variant;
  /** Make the card hoverable (lift to Level 3). */
  interactive?: boolean;
  /** Polarity-flipped dark surface (primary bg, on-primary text). */
  flipped?: boolean;
}

/** Card — Vercel card surface ladder (marketing / soft / template / flat). */
export function Card({
  variant = "marketing",
  interactive = false,
  flipped = false,
  className,
  children,
  ...rest
}: CardProps) {
  return (
    <div
      className={cn(
        VARIANT[variant],
        interactive && "transition hover:shadow-e3 cursor-pointer",
        flipped && "bg-primary text-on-primary border-transparent",
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("mb-4", className)} {...rest}>
      {children}
    </div>
  );
}

export function CardTitle({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <h3
      className={cn("text-lg font-semibold tracking-tight tracking-display2", className)}
    >
      {children}
    </h3>
  );
}

export function CardDescription({ className, children }: { className?: string; children: ReactNode }) {
  return <p className={cn("text-sm text-body mt-1", className)}>{children}</p>;
}
