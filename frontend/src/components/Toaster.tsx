"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { useLanguage } from "@/lib/i18n";

type Toast = { id: number; text: string };
const VISIBLE_MS = 7000;

/** Renders messages sent with notify(); they are announced to screen readers and close by themselves. */
export default function Toaster() {
  const { translate: t } = useLanguage();
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    let nextId = 1;
    const timers: number[] = [];
    function onNotify(event: Event) {
      const text = (event as CustomEvent<string>).detail;
      if (!text) return;
      const id = nextId++;
      setToasts((current) => [...current.slice(-3), { id, text }]);
      timers.push(window.setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), VISIBLE_MS));
    }
    window.addEventListener("app-notify", onNotify);
    return () => {
      window.removeEventListener("app-notify", onNotify);
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, []);

  return (
    <div role="status" aria-live="polite" className="fixed bottom-20 right-4 z-[60] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2 lg:bottom-6">
      {toasts.map((toast) => (
        <div key={toast.id} className="flex items-start justify-between gap-3 rounded-xl border p-3 text-sm shadow-2xl" style={{ color: "var(--text)", borderColor: "var(--border)", background: "var(--surface-raised)" }}>
          <span className="leading-relaxed">{toast.text}</span>
          <button type="button" onClick={() => setToasts((current) => current.filter((item) => item.id !== toast.id))} className="rounded-lg p-1 hover:bg-black/10" aria-label={t("Kapat")}><X className="h-4 w-4" /></button>
        </div>
      ))}
    </div>
  );
}
