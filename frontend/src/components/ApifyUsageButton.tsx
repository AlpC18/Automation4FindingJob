"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CircleAlert, CircleCheck, Coins, RefreshCw, X } from "lucide-react";
import { fetchFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

type AccountStatus = { slot: number; masked: string; valid: boolean; used_usd: number | null; remaining_usd: number | null; error?: string | null };
type Quota = { configured_keys: number; valid_keys: number; invalid_keys: number; distinct_accounts: number; budget_usd: number; theoretical_budget_usd: number; used_usd: number; remaining_usd: number; last_scan_cost_usd: number | null; percent_used: number; cycle_end?: string | null; budget_note: string; accounts: AccountStatus[] };
type UsageSnapshot = { used_usd: number; budget_usd: number; percent_used: number; checked_at?: string };

export default function ApifyUsageButton() {
  const { translate: t } = useLanguage();
  const [quota, setQuota] = useState<Quota | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<UsageSnapshot[]>([]);

  async function refresh(force = false) {
    setLoading(true);
    setError("");
    try {
      setQuota(await fetchFromApi(`/scrape/apify-quota${force ? "?force_refresh=true" : ""}`));
      const historyResponse = await fetchFromApi<{ snapshots?: UsageSnapshot[] }>("/scrape/apify-quota/history?limit=8");
      setHistory(historyResponse.snapshots || []);
    }
    catch (cause: any) { setError(cause?.message || t("Kota bilgisi alınamadı.")); }
    finally { setLoading(false); }
  }

  useEffect(() => { void refresh(); }, []);

  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} className="inline-flex h-8 items-center gap-1 rounded-lg border px-2 text-[11px] font-semibold transition-colors" style={{ color: "var(--text)", borderColor: "var(--border)", background: "var(--surface-raised)" }} title={t("Apify kullanım ve hesap durumu")}>
        <Coins className="h-3.5 w-3.5" style={{ color: "var(--accent-strong)" }} />
        <span>{quota ? `$${quota.remaining_usd.toFixed(2)} ${t("Kalan")}` : t("Apify")}</span>
        {quota && <span className="hidden text-[10px] sm:inline" style={{ color: quota.invalid_keys ? "#f59e0b" : "var(--muted)" }}>{quota.valid_keys}/{quota.configured_keys}</span>}
      </button>
      {open && <section className="absolute right-0 top-11 z-50 w-[min(22rem,calc(100vw-1.5rem))] rounded-2xl border p-4 shadow-2xl" style={{ color: "var(--text)", borderColor: "var(--border)", background: "var(--surface-raised)" }} aria-label={t("Apify kullanım durumu")}>
        <div className="flex items-start justify-between gap-3">
          <div><h2 className="text-sm font-semibold">{t("Apify kullanım")}</h2><p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{quota ? `${quota.valid_keys} ${t("geçerli anahtar")} · ${quota.distinct_accounts} ${t("farklı hesap")}` : t("Hesaplar kontrol ediliyor")}</p></div>
          <div className="flex items-center gap-1">
            <button type="button" onClick={() => void refresh(true)} disabled={loading} className="rounded-lg p-1.5 hover:bg-black/10 disabled:opacity-50" aria-label={t("Kota bilgisini yenile")}><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /></button>
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg p-1.5 hover:bg-black/10" aria-label={t("Kapat")}><X className="h-4 w-4" /></button>
          </div>
        </div>
        {quota && <>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center">
            <div className="rounded-xl p-2" style={{ background: "var(--surface-muted)" }}><p className="text-[10px]" style={{ color: "var(--muted)" }}>{t("Kullanım")}</p><p className="mt-1 text-sm font-bold">${quota.used_usd.toFixed(2)}</p></div>
            <div className="rounded-xl p-2" style={{ background: "var(--surface-muted)" }}><p className="text-[10px]" style={{ color: "var(--muted)" }}>{t("Kalan sınır")}</p><p className="mt-1 text-sm font-bold">${quota.remaining_usd.toFixed(2)}</p></div>
            <div className="rounded-xl p-2" style={{ background: "var(--surface-muted)" }}><p className="text-[10px]" style={{ color: "var(--muted)" }}>{t("Anahtar")}</p><p className="mt-1 text-sm font-bold">{quota.valid_keys}/{quota.configured_keys}</p></div>
          </div>
          <p className="mt-3 flex items-center justify-between rounded-lg px-2 py-1.5 text-xs" style={{ background: "var(--surface-muted)" }}><span>{t("Son tarama maliyeti")}</span><strong>{quota.last_scan_cost_usd === null ? t("Henüz tarama yapılmadı") : `$${quota.last_scan_cost_usd.toFixed(3)}`}</strong></p>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full" style={{ background: "var(--surface-muted)" }}><div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${quota.percent_used}%` }} /></div>
          <div className="mt-3 max-h-48 space-y-1 overflow-y-auto pr-1">
            {quota.accounts.map((account) => <div key={account.slot} className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-xs" style={{ background: "var(--surface-muted)" }}>
              <span className="flex min-w-0 items-center gap-2">{account.valid ? <CircleCheck className="h-3.5 w-3.5 shrink-0 text-emerald-500" /> : <CircleAlert className="h-3.5 w-3.5 shrink-0 text-amber-500" />}<span className="truncate">#{account.slot} {account.masked}</span></span>
              <span className="shrink-0" style={{ color: account.valid ? "var(--muted)" : "#b7791f" }}>{account.valid ? `$${(account.used_usd || 0).toFixed(2)}` : t("Doğrulanamadı")}</span>
            </div>)}
            {!quota.accounts.length && <p className="py-2 text-xs" style={{ color: "var(--muted)" }}>{t("Henüz Apify anahtarı eklenmedi.")}</p>}
          </div>
          <p className="mt-3 text-[10px] leading-relaxed" style={{ color: "var(--muted)" }}>{t("Teorik toplam")}: ${quota.theoretical_budget_usd.toFixed(0)} ({quota.configured_keys} × $5) · {t("Doğrulanmış uygulama sınırı")}: ${quota.budget_usd.toFixed(0)}. {t("5 USD/hesap, uygulamanın güvenlik sınırıdır; Apify fatura/plan bakiyesini göstermez.")}</p>
          {history.length > 1 && <div className="mt-3 border-t pt-3" style={{ borderColor: "var(--border)" }}><p className="mb-2 text-[10px] font-semibold">{t("Kullanım geçmişi")}</p><div className="space-y-1">{history.slice(0, 5).map((item, index) => <div key={`${item.checked_at}-${index}`} className="flex items-center justify-between text-[10px]" style={{ color: "var(--muted)" }}><span>{item.checked_at || ""}</span><span>${Number(item.used_usd || 0).toFixed(2)} / ${Number(item.budget_usd || 0).toFixed(0)} · %{Number(item.percent_used || 0).toFixed(1)}</span></div>)}</div></div>}
        </>}
        {error && <p role="status" className="mt-3 text-xs text-red-500">{error}</p>}
        <Link href="/sources" onClick={() => setOpen(false)} className="mt-3 block rounded-lg border px-3 py-2 text-center text-xs font-semibold" style={{ borderColor: "var(--border)" }}>{t("Hesapları yönet")}</Link>
      </section>}
    </div>
  );
}
