"use client";
import { useLanguage } from "@/lib/i18n";
import { useState } from "react";
import { FileText, Download, BarChart3, Loader2 } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function ReportsPage() {
  const { translate: t } = useLanguage();
  const [generating, setGenerating] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);

  async function generate(type: "job_search" | "pipeline") {
    setGenerating(type);
    setResult(null);
    try {
      const res = await fetchFromApi(`/reports/${type}`, { method: "POST" });
      setResult(res);
    } catch (e) {
      console.error(e);
    } finally {
      setGenerating(null);
    }
  }

  const reports = [
    {
      id: "job_search",
      title: "İş Arama Raporu",
      desc: "Tüm takip edilen ilanlar, skorlar, durum dağılımı ve istatistikler",
      icon: "📊",
      color: "blue",
    },
    {
      id: "pipeline",
      title: "Başvuru Pipeline Raporu",
      desc: "Başvuru hunisi, aşama dağılımı ve detaylı başvuru listesi",
      icon: "📈",
      color: "purple",
    },
  ];

  return (
    <div className="space-y-8 max-w-3xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <FileText className="w-7 h-7 text-sky-400" /> {t("Rapor Oluşturucu")}</h1>
        <p className="text-slate-400 mt-1">{t("Standalone HTML raporları oluşturun — çevrimdışı görüntülenebilir")}</p>
      </div>

      <div className="grid gap-4">
        {reports.map((r) => (
          <div key={r.id} className="bg-slate-800/60 border border-slate-700/40 rounded-2xl p-6 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="text-3xl">{r.icon}</div>
              <div>
                <div className="text-sm font-semibold text-white">{t(r.title)}</div>
                <div className="text-xs text-slate-400 mt-0.5">{t(r.desc)}</div>
              </div>
            </div>
            <button
              onClick={() => generate(r.id as any)}
              disabled={generating === r.id}
              className={`px-5 py-2.5 rounded-xl text-sm font-medium transition-colors flex items-center gap-2
                ${generating === r.id
                  ? "bg-slate-700 text-slate-400"
                  : "bg-sky-600 hover:bg-sky-500 text-white"}`}
            >
              {generating === r.id ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> {t("Oluşturuluyor...")}</>
              ) : (
                <><Download className="w-4 h-4" /> {t("Oluştur")}</>
              )}
            </button>
          </div>
        ))}
      </div>

      {result && (
        <div className="bg-emerald-500/5 border border-emerald-500/30 rounded-2xl p-6 text-center">
          <div className="text-3xl mb-3">✅</div>
          <div className="text-sm font-semibold text-white mb-1">{t("Rapor Oluşturuldu!")}</div>
          <div className="text-xs text-slate-400 mb-4">
            {result.filename} {t("•")}{result.total_jobs || 0} {t("ilan •")}{result.generated_at?.slice(0, 16)}
          </div>
          <div className="text-xs text-slate-500 font-mono bg-slate-900/60 rounded-lg p-3 break-all">
            📁 {result.report_path}
          </div>
        </div>
      )}
    </div>
  );
}
