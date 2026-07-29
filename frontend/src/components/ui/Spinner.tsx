import { Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

/** Inline spinner. Uses ink color by default; sizeable via className. */
export default function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("animate-spin-fast", className)} aria-hidden />;
}

/** Inline spinner + label, sized for button/loading contexts. */
export function SpinnerLabel({ label, className }: { label?: string; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <Spinner className="w-3.5 h-3.5" />
      {label}
    </span>
  );
}
