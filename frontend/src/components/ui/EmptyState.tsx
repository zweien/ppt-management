import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface EmptyStateProps {
  /** Lucide icon node. */
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  /** Optional action (e.g. a Button). */
  action?: ReactNode;
  /** Use the mesh gradient as backdrop (for landing-level empties). */
  mesh?: boolean;
  className?: string;
}

/** Empty state — canvas-soft frame with generous padding (ex-empty-state-card). */
export default function EmptyState({
  icon,
  title,
  description,
  action,
  mesh = false,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-lg border border-dashed border-hairline-strong p-12 text-center",
        mesh ? "bg-mesh" : "bg-canvas-soft",
        className,
      )}
    >
      <div className="relative flex flex-col items-center gap-3">
        {icon && (
          <div className="w-12 h-12 rounded-full bg-canvas-soft-2 border border-hairline flex items-center justify-center text-mute">
            {icon}
          </div>
        )}
        <h3 className="text-base font-semibold text-ink">{title}</h3>
        {description && <p className="text-sm text-body max-w-md">{description}</p>}
        {action && <div className="mt-2">{action}</div>}
      </div>
    </div>
  );
}
