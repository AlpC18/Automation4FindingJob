"use client";
import { notify } from "@/lib/notify";
import { useLanguage } from "@/lib/i18n";
import { useEffect, useState } from "react";
import { GitCommit, Clock } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function TimelinePage() {
  const { translate: t } = useLanguage();
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchFromApi("/scrape/seen_jobs/stats")
      .then(async () => {
        const res = await fetchFromApi("/scrape/jobs");
        setJobs(res.jobs || []);
      })
      .catch(() => notify(t("Veriler yüklenemedi. Sayfayı yenileyip tekrar dene.")))
      .finally(() => setLoading(false));
  }, []);

  const stages = [
    { key: "new", label: "Taranan" },
    { key: "ranked", label: "Uyum tahmini hesaplandı" },
    { key: "applied", label: "Başvuruldu" },
    { key: "interview", label: "Mülakat Daveti" },
    { key: "offer", label: "Teklif Alındı" }
  ];

  function getStageIndex(status: string) {
    const idx = stages.findIndex(s => s.key === status);
    return idx === -1 ? 1 : idx;
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <GitCommit className="w-7 h-7 text-indigo-400" /> {t("Başvuru zaman çizelgesi")}</h1>
        <p className="text-slate-400 mt-1">
          {t("Her ilanın keşif anından teklif aşamasına kadar geçirdiği evreleri ve bekleme sürelerini yatay çizelgede izleyin.")}</p>
      </div>

      {loading ? (
        <div className="text-center py-20 text-slate-400">{t("Zaman çizelgesi yükleniyor...")}</div>
      ) : jobs.length === 0 ? (
        <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-12 text-center text-slate-400">
          {t("Henüz taranmış ilan bulunmuyor.")}</div>
      ) : (
        <div className="space-y-4">
          {jobs.slice(0, 15).map((job, i) => {
            const currentStageIdx = getStageIndex(String(job.status || "ranked").toLowerCase());
            
            return (
              <div
                key={i}
                className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-4 hover:border-slate-700 transition-all"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <div className="text-sm font-bold text-white flex items-center gap-2">
                      <span>{job.title}</span>
                      <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                        {job.company}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      {job.location || "Uzaktan"} {t("• Tahmini uyum: ≈ %")}{job.match_score ?? "—"}
                    </div>
                  </div>

                  <div className="text-xs font-mono text-slate-400 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    <span>{t("Son Güncelleme:")} {job.first_seen?.slice(0, 10) || t("Bugün")}</span>
                  </div>
                </div>

                {/* Horizontal Step Timeline Bar */}
                <div className="grid grid-cols-5 gap-2 pt-2">
                  {stages.map((stage, idx) => {
                    const isPassed = idx <= currentStageIdx;
                    const isCurrent = idx === currentStageIdx;

                    return (
                      <div key={stage.key} className="space-y-1.5">
                        <div
                          className={`h-2 rounded-full transition-all ${
                            isCurrent
                              ? "bg-indigo-500 shadow-lg shadow-indigo-500/50 animate-pulse"
                              : isPassed
                              ? "bg-blue-600"
                              : "bg-slate-800"
                          }`}
                        />
                        <div
                          className={`text-xs font-medium truncate ${
                            isCurrent
                              ? "text-indigo-400 font-bold"
                              : isPassed
                              ? "text-slate-300"
                              : "text-slate-400"
                          }`}
                        >
                          {t(stage.label)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
