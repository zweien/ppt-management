"use client";

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";
import Button from "./Button";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  /** Footer actions (rendered right-aligned). */
  footer?: ReactNode;
  /** Size variant. */
  size?: "sm" | "md" | "lg";
  /** Disable close on backdrop click / ESC (for destructive confirm flows). */
  disableBackdropClose?: boolean;
}

const SIZE = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-2xl",
};

/**
 * Modal — Vercel Level-5 elevation dialog (ex-modal-card). Closes on ESC and
 * backdrop click; traps focus within the panel while open.
 */
export default function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
  disableBackdropClose = false,
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !disableBackdropClose) onClose();
    };
    document.addEventListener("keydown", onKey);
    // Lock body scroll while modal open.
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // Focus the panel for keyboard users.
    panelRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose, disableBackdropClose]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/40 animate-fade-in"
        onClick={() => !disableBackdropClose && onClose()}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
        className={cn(
          "relative w-full bg-surface text-ink rounded-lg shadow-e5 outline-none animate-scale-in",
          SIZE[size],
        )}
      >
        {(title || description) && (
          <div className="px-6 pt-5 pb-3">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                {title && <h2 className="text-lg font-semibold tracking-tight">{title}</h2>}
                {description && <p className="text-sm text-body mt-1">{description}</p>}
              </div>
              <button
                onClick={onClose}
                aria-label="关闭"
                className="text-mute hover:text-ink -mr-1 -mt-1 p-1 rounded-md hover:bg-canvas-soft-2"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
        <div className="px-6 pb-5">{children}</div>
        {footer && (
          <div className="px-6 py-4 border-t border-hairline flex justify-end gap-2 bg-canvas-soft rounded-b-lg">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}

/** Convenience confirm dialog footer: cancel + destructive/primary confirm. */
export function ConfirmFooter({
  confirmText = "确认",
  cancelText = "取消",
  loading = false,
  destructive = false,
  onCancel,
  onConfirm,
}: {
  confirmText?: string;
  cancelText?: string;
  loading?: boolean;
  destructive?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <>
      <Button variant="ghost" onClick={onCancel} disabled={loading}>
        {cancelText}
      </Button>
      <Button variant={destructive ? "danger" : "primary"} onClick={onConfirm} loading={loading}>
        {confirmText}
      </Button>
    </>
  );
}
