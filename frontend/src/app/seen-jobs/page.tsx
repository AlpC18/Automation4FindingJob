"use client";
import { useLanguage } from "@/lib/i18n";
import { useEffect, useState } from "react";
import { Eye, Clock, AlertTriangle, CheckCircle2, Filter, RefreshCw } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function SeenJobsPage() {
  const { translate: t } = useLanguage();
  const [stats, setStats] = useState<any>(null);
  const [newJobs, setNewJobs] = useState<any>({});
  const [closingSoon, setClosingSoon] = useState<any[]>([]);
  const [tab, setTab] = useState<"new" | "ranked" | "closing">("new");
  const [loading, setLoading] = useState(true);

  async function loadData() {
    setLoading(true);
    try {
      const [s, n, c] = await Promise.all([
        fetchFromApi("/scrape/seen_jobs/stats").catch(() => null),
        fetchFromApi("/scrape/seen_jobs/new").catch(() => ({ jobs: {} })),
        fetchFromApi("/scrape/seen_jobs/closing_soon?days=7").catch(() => ({ jobs: [] })),
      ]);
      setStats(s);
      setNewJobs(n?.jobs || {});
      setClosingSoon(c?.jobs || []);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, []);

  async function handleSweep() {
    await fetchFromApi("/scrape/seen_jobs/sweep_expired", { method: "POST", body: JSON.stringify({ dry_run: false }) });
    loadData();
  }

  const jobsList = Object.entries(newJobs);
  const statusColors: Record<string, string> = {
    new: "bg-blue-500/20 text-blue-300", ranked: "bg-emerald-500/20 text-emerald-300",
    applied: "bg-purple-500/20 text-purple-300", expired: "bg-red-500/20 text-red-300",
    skipped: "bg-slate-500/20 text-slate-400",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Eye className="w-7 h-7 text-cyan-400" /> {t("Görülen İlanlar Takibi")}</h1>
          <p className="text-slate-400 mt-1">{t("Daha önce görülen ilanlar ve son başvuru tarihi uyarıları")}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleSweep} className="px-4 py-2 bg-red-600/20 text-red-300 border border-red-500/30 rounded-lg text-sm hover:bg-red-600/30 transition-colors">
            {t("Süresi Geçenleri Temizle")}</button>
          <button onClick={loadData} className="px-4 py-2 bg-slate-700/60 text-slate-300 rounded-lg text-sm hover:bg-slate-700 transition-colors">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="bg-slate-800/60 border border-slate-700/40 rounded-xl p-4 text-center">
            <div className="text-2xl font-bold text-white">{stats.total_jobs || 0}</div>
            <div className="text-xs text-slate-400">{t("Toplam İlan")}</div>
          </div>
          {Object.entries(stats.by_status || {}).slice(0, 4).map(([status, count]: [string, any]) => (
            <div key={status} className="bg-slate-800/60 border border-slate-700/40 rounded-xl p-4 text-center">
              <div className="text-2xl font-bold text-white">{count}</div>
              <div className="text-xs text-slate-400 capitalize">{status}</div>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-700/40 pb-2">
        {[
          { key: "new", label: "Yeni İlanlar", count: jobsList.length },
          { key: "closing", label: "Yakında Kapanan", count: closingSoon.length },
        ].map((item) => (
          <button key={item.key} onClick={() => setTab(item.key as any)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === item.key ? "bg-cyan-600/20 text-cyan-300 border border-cyan-500/30" : "text-slate-400 hover:text-white"}`}>
            {t(item.label)} <span className="ml-1 text-xs opacity-60">({item.count})</span>
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="text-center py-16 text-slate-400">{t("Yükleniyor...")}</div>
      ) : tab === "new" ? (
        <div className="space-y-2">
          {jobsList.length === 0 && <div className="text-center py-16 text-slate-400">{t("Yeni ilan yok")}</div>}
          {jobsList.map(([key, job]: [string, any]) => (
            <div key={key} className="bg-slate-800/50 border border-slate-700/40 rounded-xl p-4 flex items-center justify-between hover:bg-slate-800/80 transition-colors">
              <div className="flex-1">
                <div className="text-sm font-medium text-white">{job.title || "—"}</div>
                <div className="text-xs text-slate-400 mt-0.5">{job.company} {t("•")}{job.portal} {t("•")}{job.location}</div>
              </div>
              <div className="flex items-center gap-3">
                {job.deadline && (
                  <span className="text-xs text-amber-400 flex items-center gap-1">
                    <Clock className="w-3 h-3" /> {job.deadline}
                  </span>
                )}
                <span className={`text-xs px-2 py-0.5 rounded-full ${statusColors[job.status] || statusColors.new}`}>
                  {job.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {closingSoon.length === 0 && <div className="text-center py-16 text-slate-400">{t("Yakında kapanan ilan yok")}</div>}
          {closingSoon.map((job: any, i: number) => (
            <div key={i} className="bg-slate-800/50 border border-amber-500/20 rounded-xl p-4 flex items-center justify-between">
              <div className="flex-1">
                <div className="text-sm font-medium text-white">{job.title}</div>
                <div className="text-xs text-slate-400">{job.company}</div>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono text-amber-400 bg-amber-500/10 px-2 py-1 rounded-lg">
                  {job.days_left === 0 ? t("BUGÜN!") : `${job.days_left} gün kaldı`}
                </span>
                <span className="text-xs text-emerald-400">{job.match_score?.toFixed(0) || "—"} {t("puan")}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
