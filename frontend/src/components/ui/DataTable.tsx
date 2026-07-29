import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes, TableHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

/** DataTable — Vercel table chrome (ex-data-table-cell).
 * Header on canvas-soft with caption-mono uppercase; body in body-sm; row
 * hairlines; hover lifts to canvas-soft-2. */

export function Table({ className, children, ...rest }: TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="w-full overflow-x-auto rounded-md border border-hairline bg-surface">
      <table className={cn("w-full text-sm border-collapse", className)} {...rest}>
        {children}
      </table>
    </div>
  );
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead className="bg-canvas-soft">
      <tr className="border-b border-hairline">{children}</tr>
    </thead>
  );
}

export function TH({ className, children, ...rest }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        "text-left font-normal uppercase font-mono text-[11px] tracking-wide text-mute px-4 py-3 whitespace-nowrap",
        className,
      )}
      {...rest}
    >
      {children}
    </th>
  );
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y divide-hairline">{children}</tbody>;
}

export function TR({
  className,
  children,
  ...rest
}: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr className={cn("transition hover:bg-canvas-soft-2", className)} {...rest}>
      {children}
    </tr>
  );
}

export function TD({ className, children, ...rest }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={cn("px-4 py-3 text-body align-middle", className)} {...rest}>
      {children}
    </td>
  );
}
