import { forwardRef } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: ReactNode;
}

/**
 * Checkbox — compact, baseline-aligned inline control. The native input is
 * sized to 16px and given `shrink-0` so the label/input never stretch a row.
 * Wraps input + label in an inline-flex with consistent height.
 */
export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { label, className, ...rest },
  ref,
) {
  return (
    <label className={cn("inline-flex items-center gap-1.5 shrink-0 cursor-pointer select-none text-sm text-body h-7", className)}>
      <input
        ref={ref}
        type="checkbox"
        className={cn(
          "w-4 h-4 shrink-0 cursor-pointer rounded-[3px]",
          "border border-hairline-strong bg-canvas",
          "accent-[rgb(var(--primary))] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-link/40",
        )}
        {...rest}
      />
      {label != null && <span className="leading-none whitespace-nowrap">{label}</span>}
    </label>
  );
});

export default Checkbox;
