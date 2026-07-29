import { forwardRef } from "react";
import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type Size = "xs" | "sm" | "md" | "lg";

const SIZE: Record<Size, string> = {
  xs: "h-7 text-xs px-2.5", // 28px — inline toolbar controls (aligns w/ Checkbox/Tabs)
  sm: "h-8 text-[13px] px-3", // 32px — tight forms
  md: "h-10 text-sm px-3", // 40px — default (--geist-form-height)
  lg: "h-12 text-base px-3", // 48px — hero CTAs
};

const base =
  "bg-canvas text-ink border border-hairline rounded-sm w-full outline-none transition placeholder:text-mute focus:border-hairline-strong focus:ring-2 focus:ring-link/30 disabled:opacity-50 disabled:bg-canvas-soft-2";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  inputSize?: Size;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { inputSize = "md", className, ...rest },
  ref,
) {
  return <input ref={ref} className={cn(base, SIZE[inputSize], className)} {...rest} />;
});

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  inputSize?: Size;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { inputSize = "md", className, children, ...rest },
  ref,
) {
  return (
    <select ref={ref} className={cn(base, "pr-8 cursor-pointer", SIZE[inputSize], className)} {...rest}>
      {children}
    </select>
  );
});

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  inputSize?: Size;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { inputSize = "md", className, ...rest },
  ref,
) {
  return (
    <textarea
      ref={ref}
      className={cn(base, "py-2 resize-y min-h-[80px]", SIZE[inputSize], className)}
      {...rest}
    />
  );
});

/** Field label + optional hint, Vercel body-sm styling. */
export function Field({
  label,
  hint,
  htmlFor,
  children,
  className,
}: {
  label?: string;
  hint?: string;
  htmlFor?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      {label && (
        <label htmlFor={htmlFor} className="block text-[13px] font-medium text-body">
          {label}
        </label>
      )}
      {children}
      {hint && <p className="text-xs text-mute">{hint}</p>}
    </div>
  );
}
