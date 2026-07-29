"use client";

import { cn } from "@/lib/cn";

export interface TabItem<K extends string> {
  key: K;
  label: string;
}

interface TabsProps<K extends string> {
  items: TabItem<K>[];
  value: K;
  onChange: (k: K) => void;
  className?: string;
}

/**
 * Tabs — Vercel tab-ghost pill row. Active tab polarity-flips to primary
 * (ink); inactive tabs are body-colored ghosts.
 */
export function Tabs<K extends string>({ items, value, onChange, className }: TabsProps<K>) {
  return (
    <div className={cn("inline-flex items-center gap-1 p-1 bg-canvas-soft-2 rounded-pill-sm w-fit", className)}>
      {items.map((item) => {
        const active = item.key === value;
        return (
          <button
            key={item.key}
            onClick={() => onChange(item.key)}
            className={cn(
              "px-3 h-8 text-sm font-medium rounded-pill-sm transition whitespace-nowrap",
              active
                ? "bg-primary text-on-primary"
                : "text-body hover:text-ink hover:bg-canvas-soft",
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

export default Tabs;
