"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { CheckCircle2, AlertCircle, Info, X } from "lucide-react";
import { cn } from "@/lib/cn";

type Tone = "success" | "error" | "info";

interface Toast {
  id: number;
  tone: Tone;
  message: string;
}

interface ToastContextValue {
  toast: (message: string, tone?: Tone) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TONE_STYLES: Record<Tone, { cls: string; icon: ReactNode }> = {
  success: { cls: "text-success-deep", icon: <CheckCircle2 className="w-4 h-4" /> },
  error: { cls: "text-error-deep", icon: <AlertCircle className="w-4 h-4" /> },
  info: { cls: "text-link-deep", icon: <Info className="w-4 h-4" /> },
};

/** Provider — mount once near the app root. Exposes `useToast()`. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [mounted, setMounted] = useState(false);
  const nextId = useRef(1);

  // Defer portal creation until after hydration so SSR and first client
  // render produce identical output (no portal), avoiding React #418.
  useEffect(() => setMounted(true), []);

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (message: string, tone: Tone = "info") => {
      const id = nextId.current++;
      setToasts((prev) => [...prev, { id, tone, message }]);
      window.setTimeout(() => remove(id), 4000);
    },
    [remove],
  );

  const ctx: ToastContextValue = {
    toast,
    success: (m) => toast(m, "success"),
    error: (m) => toast(m, "error"),
    info: (m) => toast(m, "info"),
  };

  return (
    <ToastContext.Provider value={ctx}>
      {children}
      {mounted &&
        typeof document !== "undefined" &&
        createPortal(
          <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 w-[360px] max-w-[calc(100vw-2rem)]">
            {toasts.map((t) => {
              const s = TONE_STYLES[t.tone];
              return (
                <div
                  key={t.id}
                  className="flex items-start gap-3 bg-surface text-ink rounded-md shadow-e4 px-4 py-3 animate-slide-up"
                >
                  <span className={cn("mt-0.5 shrink-0", s.cls)}>{s.icon}</span>
                  <p className="text-sm flex-1 leading-relaxed">{t.message}</p>
                  <button
                    onClick={() => remove(t.id)}
                    aria-label="关闭"
                    className="text-mute hover:text-ink shrink-0"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })}
          </div>,
          document.body,
        )}
    </ToastContext.Provider>
  );
}

/** Access the toast API. Must be used inside <ToastProvider>. */
export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // Safe no-op fallback so pages that render before provider mounts don't crash.
    const noop = () => {};
    return { toast: noop, success: noop, error: noop, info: noop };
  }
  return ctx;
}
