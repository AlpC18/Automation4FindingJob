"use client";
import { useLanguage } from "@/lib/i18n";
import { useEffect, useState } from "react";
import { Newspaper, Send, TrendingUp, AlertTriangle, Sparkles, CheckCircle2, RefreshCw } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function WeeklyDigestPage() {
  const { translate: t } = useLanguage();
  const [digest, setDigest] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [dispatching, setDispatching] = useState(false);
  const [dispatchResult, setDispatchResult] = useState<any>(null);

  async function loadDigest() {
    try {
      setLoading(true);
      const res = await fetchFromApi("/outcome/digest");
      setDigest(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDigest();
  }, []);

  async function handleDispatch() {
    try {
      setDispatching(true);
      const res = await fetchFromApi("/outcome/digest/dispatch", { method: "POST" });
      setDispatchResult(res);
    } catch (e) {
      alert(t("Gönderim sırasında hata oluştu."));
    } finally {
      setDispatching(false);
    }
  }

  if (loading) {
    return <div className="text-center py-20 text-slate-500">{t("Haftalık bülten derleniyor...")}</div>;
  }

  const m = digest?.metrics || {};

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Newspaper className="w-7 h-7 text-indigo-400" /> {t("Haftalık Kariyer & İstihbarat Bülteni")}</h1>
          <p className="text-slate-400 mt-1">
            {t("Dönem:")}<strong className="text-slate-200">{digest?.period}</strong> {t("• Otomatik Pazartesi Raporu")}</p>
        </div>
        <button
          onClick={handleDispatch}
          disabled={dispatching}
          className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold flex items-center gap-2 transition-all disabled:opacity-50 shadow-lg shadow-indigo-600/20"
        >
          {dispatching ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
          {dispatching ? t("Gönderiliyor...") : t("Telegram & Kanallara Gönder")}
        </button>
      </div>

      {dispatchResult && (
        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-4 text-xs text-emerald-300 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <span>
            {t("Bülten başarıyla dağıtıldı!")}{dispatchResult.telegram_sent ? t("(Telegram mesajı iletildi)") : t("(Telegram yapılandırılmamış)")}
          </span>
        </div>
      )}

      {/* KPI Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="text-xs text-slate-400">{t("Yeni Keşif")}</div>
          <div className="text-2xl font-bold text-blue-400 mt-1">{m.new_jobs_found || 0} {t("İlan")}</div>
          <div className="text-[10px] text-slate-500 mt-1">{t("Son 7 günde taranan")}</div>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="text-xs text-slate-400">{t("Uyum tahmini hesaplanan")}</div>
          <div className="text-2xl font-bold text-emerald-400 mt-1">{m.evaluated_ranked || 0} {t("İlan")}</div>
          <div className="text-[10px] text-slate-500 mt-1">{t("Yüksek eşleşme filtresi")}</div>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="text-xs text-slate-400">{t("Yapılan Başvuru")}</div>
          <div className="text-2xl font-bold text-indigo-400 mt-1">{m.applications_submitted || 0} {t("Gönderim")}</div>
          <div className="text-[10px] text-slate-500 mt-1">{t("Drafter-Reviewer onaylı")}</div>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="text-xs text-slate-400">{t("Kapanan / Son Günler")}</div>
          <div className="text-2xl font-bold text-amber-400 mt-1">{m.closing_soon_count || 0} {t("Fırsat")}</div>
          <div className="text-[10px] text-slate-500 mt-1">{t("5 gün içinde son tarih")}</div>
        </div>
      </div>

      {/* Top Opportunities */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
        <h2 className="text-base font-bold text-white flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-amber-400" /> {t("Haftanın En Yüksek Eşleşen Fırsatları")}</h2>
        {(!digest?.top_opportunities || digest.top_opportunities.length === 0) ? (
          <div className="text-xs text-slate-500">{t("Henüz yüksek puanlı ilan bulunmuyor.")}</div>
        ) : (
          <div className="space-y-3">
            {digest.top_opportunities.map((job: any, i: number) => (
              <div key={i} className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
                <div>
                  <div className="text-sm font-semibold text-white">{job.title}</div>
                  <div className="text-xs text-slate-400 mt-0.5">{job.company} {t("•")}{job.location || "Uzaktan"}</div>
                </div>
                <div className="text-right">
                  <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">
                    ≈ %{job.match_score ?? "—"} {t("Tahmini uyum")}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Urgent Closing Soon */}
      {digest?.closing_soon_jobs && digest.closing_soon_jobs.length > 0 && (
        <div className="bg-amber-500/5 border border-amber-500/20 rounded-2xl p-6 space-y-3">
          <h2 className="text-base font-bold text-amber-300 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-400" /> {t("Acil: Kapanmak Üzere Olan Başvurular")}</h2>
          <div className="space-y-2">
            {digest.closing_soon_jobs.map((job: any, i: number) => (
              <div key={i} className="text-xs text-slate-300 flex items-center justify-between p-2.5 bg-slate-900/60 rounded-lg">
                <span><strong>{job.company}</strong> — {job.title}</span>
                <span className="text-amber-400 font-mono font-semibold">{job.days_left} {t("gün kaldı (")}{job.deadline})</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Strategic Advice */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-3">
        <h2 className="text-base font-bold text-white flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-blue-400" /> {t("Stratejik Kariyer Tavsiyeleri")}</h2>
        <div className="space-y-2">
          {digest?.strategic_recommendations?.map((rec: string, i: number) => (
            <div key={i} className="text-xs text-slate-300 bg-slate-950/60 rounded-xl p-3.5 border border-slate-800/80">
              💡 {rec}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
