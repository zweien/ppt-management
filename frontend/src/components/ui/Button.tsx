import { forwardRef } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";
import Spinner from "./Spinner";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  /** Render as a full-width block. */
  block?: boolean;
  /** Leading icon node. */
  leadingIcon?: ReactNode;
}

const VARIANT: Record<Variant, string> = {
  // Ink pill — the conversion target (button-primary per DESIGN.md).
  primary:
    "bg-primary text-on-primary hover:opacity-90 active:opacity-100 rounded-[100px] shadow-e2",
  // White pill paired with the ink primary.
  secondary:
    "bg-canvas text-ink border border-hairline hover:bg-canvas-soft-2 rounded-[100px] shadow-e2",
  // Plain text / icon button.
  ghost: "bg-transparent text-body hover:bg-canvas-soft-2 hover:text-ink rounded-md",
  // Destructive — error red.
  danger: "bg-error text-white hover:opacity-90 rounded-[100px] shadow-e2",
};

const SIZE: Record<Size, string> = {
  // nav-scale: 14px label, 6px radius flavor, tighter padding.
  sm: "h-7 px-2 text-[15px] font-medium gap-1",
  md: "h-9 px-3 text-sm font-medium gap-1.5",
  // marketing-scale: 16px label.
  lg: "h-12 px-4 text-base font-medium gap-2",
};

/**
 * Button — Vercel pill CTA. `primary` is the ink CTA, `secondary` the white
 * pill. Marketing CTAs use `lg`; in-app use `md`/`sm`.
 */
const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "secondary",
    size = "md",
    loading = false,
    block = false,
    leadingIcon,
    className,
    children,
    disabled,
    ...rest
  },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap transition disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-link/50",
        VARIANT[variant],
        // sm keeps the tighter nav radius; md/lg keep the pill radius from VARIANT.
        size === "sm" && variant !== "ghost" ? "" : "",
        SIZE[size],
        variant === "ghost" && size === "sm" && "rounded-sm",
        block && "w-full",
        className,
      )}
      {...rest}
    >
      {loading ? <Spinner className="w-4 h-4 shrink-0" /> : leadingIcon}
      {children}
    </button>
  );
});

export default Button;
