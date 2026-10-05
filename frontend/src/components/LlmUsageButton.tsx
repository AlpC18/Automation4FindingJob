"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Cpu, RefreshCw, X } from "lucide-react";
import { fetchFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

type LlmUsage = {
  model: string; input_tokens: number; output_tokens: number; tokens_used: number; budget_tokens: number;
  remaining_tokens: number | null; percent_used: number; calls: number;
  estimated_cost_usd: number | null; average_cost_per_call_usd: number | null;
};

const compact = (value: number) => (value >= 1000 ? `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k` : String(value));
const dollars = (value: number | null) => (value === null ? "—" : `$${value.toFixed(value < 1 ? 3 : 2)}`);

export default function LlmUsageButton() {
  const { translate: t } = useLanguage();
  const [usage, setUsage] = useState<LlmUsage | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    setLoading(true);
    setError("");
    try { setUsage(await fetchFromApi<LlmUsage>("/llm/usage")); }
    catch (cause: any) { setError(cause?.message || t("Kullanım bilgisi alınamadı.")); }
    finally { setLoading(false); }
  }

  useEffect(() => { void refresh(); }, []);
  useEffect(() => { if (open) void refresh(); }, [open]);

  const tile = (label: string, value: string) => (
    <div className="rounded-xl p-2" style={{ background: "var(--surface-muted)" }}>
      <p className="text-xs" style={{ color: "var(--muted)" }}>{label}</p>
      <p className="mt-1 text-sm font-bold">{value}</p>
    </div>
  );

  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} className="inline-flex h-8 items-center gap-1 rounded-lg border px-2 text-xs font-semibold transition-colors" style={{ color: "var(--text)", borderColor: "var(--border)", background: "var(--surface-raised)" }} title={t("Yapay zekâ token kullanımı")}>
        <Cpu className="h-3.5 w-3.5" style={{ color: "var(--accent-strong)" }} />
        <span>{usage ? `${compact(usage.tokens_used)}${usage.budget_tokens ? ` / ${compact(usage.budget_tokens)}` : ""}` : t("AI")}</span>
        {usage && usage.estimated_cost_usd !== null && <span className="hidden text-xs sm:inline" style={{ color: "var(--muted)" }}>{dollars(usage.estimated_cost_usd)}</span>}
      </button>
      {open && <section className="absolute right-0 top-11 z-50 w-[min(22rem,calc(100vw-1.5rem))] rounded-2xl border p-4 shadow-2xl" style={{ color: "var(--text)", borderColor: "var(--border)", background: "var(--surface-raised)" }} aria-label={t("Yapay zekâ token kullanımı")}>
        <div className="flex items-start justify-between gap-3">
          <div><h2 className="text-sm font-semibold">{t("Bugünkü yapay zekâ kullanımı")}</h2><p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{usage ? `${usage.model} · ${usage.calls} ${t("çağrı")}` : t("Yükleniyor...")}</p></div>
          <div className="flex items-center gap-1">
            <button type="button" onClick={() => void refresh()} disabled={loading} className="rounded-lg p-1.5 hover:bg-black/10 disabled:opacity-50" aria-label={t("Yenile")}><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /></button>
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg p-1.5 hover:bg-black/10" aria-label={t("Kapat")}><X className="h-4 w-4" /></button>
          </div>
        </div>
        {usage && <>
          <div className="mt-4 grid grid-cols-2 gap-2 text-center">
            {tile(t("Kullanılan token"), usage.tokens_used.toLocaleString())}
            {tile(t("Kalan token"), usage.remaining_tokens === null ? "∞" : usage.remaining_tokens.toLocaleString())}
            {tile(t("Tahmini maliyet"), dollars(usage.estimated_cost_usd))}
            {tile(t("Çağrı başına"), dollars(usage.average_cost_per_call_usd))}
          </div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full" style={{ background: "var(--surface-muted)" }}><div className={`h-full rounded-full transition-all ${usage.percent_used >= 90 ? "bg-amber-500" : "bg-emerald-500"}`} style={{ width: `${usage.percent_used}%` }} /></div>
          <p className="mt-3 text-xs leading-relaxed" style={{ color: "var(--muted)" }}>{t("Günlük sınır yalnızca Claude için geçerlidir; dolunca şablon motoru yanıt verir. Maliyet yalnızca fiyatı bilinen modellerde gösterilir.")}</p>
        </>}
        {error && <p role="status" className="mt-3 text-xs text-red-500">{error}</p>}
        <Link href="/llm" onClick={() => setOpen(false)} className="mt-3 block rounded-lg border px-3 py-2 text-center text-xs font-semibold" style={{ borderColor: "var(--border)" }}>{t("Anahtarları yönet")}</Link>
      </section>}
    </div>
  );
}
