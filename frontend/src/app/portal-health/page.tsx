"use client";
import { useLanguage } from "@/lib/i18n";
import { useEffect, useState } from "react";
import { Activity, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function PortalHealthPage() {
  const { translate: t } = useLanguage();
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Try to get health from last scrape results
    fetchFromApi("/scrape/health")
      .then(setReport)
      .catch(() => setReport(null))
      .finally(() => setLoading(false));
  }, []);

  const portals = [
    { id: "linkedin", name: "LinkedIn", color: "blue" },
    { id: "kosovajob", name: "KosovaJob", color: "emerald" },
    { id: "upwork", name: "Upwork", color: "green" },
    { id: "fiverr", name: "Fiverr", color: "green" },
    { id: "freelancer", name: "Freelancer.com", color: "blue" },
    { id: "toptal", name: "Toptal", color: "blue" },
    { id: "gjirafawork", name: "GjirafaWork", color: "emerald" },
    { id: "kariyernet", name: "Kariyer.net", color: "purple" },
    { id: "indeed", name: "Indeed", color: "blue" },
    { id: "glassdoor", name: "Glassdoor", color: "emerald" },
    { id: "wellfound", name: "Wellfound", color: "purple" },
    { id: "remote", name: "Remote Boards", color: "purple" },
  ];

  function getStatusIcon(status: string) {
    if (status === "healthy") return <CheckCircle2 className="w-5 h-5 text-emerald-400" />;
    if (status === "warning") return <AlertTriangle className="w-5 h-5 text-amber-400" />;
    if (status === "degraded") return <XCircle className="w-5 h-5 text-red-400" />;
    return <Activity className="w-5 h-5 text-slate-400" />;
  }

  function getStatusBg(status: string) {
    if (status === "healthy") return "border-emerald-500/30 bg-emerald-500/5";
    if (status === "warning") return "border-amber-500/30 bg-amber-500/5";
    if (status === "degraded") return "border-red-500/30 bg-red-500/5";
    return "border-slate-700/40 bg-slate-800/50";
  }

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Activity className="w-7 h-7 text-lime-400" /> {t("Portal Sağlık Monitörü")}</h1>
        <p className="text-slate-400 mt-1">{t("İlan kaynaklarının çalışma durumu")}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {portals.map((portal) => {
          const portalReport = report?.portals?.[portal.id];
          const status = portalReport?.status || "no_data";
          const healthScore = portalReport?.health_score;

          return (
            <div key={portal.id} className={`border rounded-2xl p-6 ${getStatusBg(status)} transition-all`}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  {getStatusIcon(status)}
                  <div>
                    <div className="text-sm font-semibold text-white">{portal.name}</div>
                    <div className="text-xs text-slate-400 capitalize">{status === "no_data" ? "Veri yok" : status}</div>
                  </div>
                </div>
                {healthScore !== undefined && (
                  <div className={`text-2xl font-bold ${healthScore >= 80 ? "text-emerald-400" : healthScore >= 50 ? "text-amber-400" : "text-red-400"}`}>
                    {healthScore}
                  </div>
                )}
              </div>

              {portalReport?.result_count !== undefined && (
                <div className="text-xs text-slate-400 mb-2">{t("Son taramada")}{portalReport.result_count} {t("sonuç")}</div>
              )}

              {portalReport?.issues?.length > 0 && (
                <div className="space-y-1 mt-2">
                  {portalReport.issues.map((issue: string, i: number) => (
                    <div key={i} className="text-xs text-red-300 bg-red-500/10 rounded-lg px-3 py-1.5">{issue}</div>
                  ))}
                </div>
              )}

              {portalReport?.warnings?.length > 0 && (
                <div className="space-y-1 mt-2">
                  {portalReport.warnings.map((w: string, i: number) => (
                    <div key={i} className="text-xs text-amber-300 bg-amber-500/10 rounded-lg px-3 py-1.5">{w}</div>
                  ))}
                </div>
              )}

              {status === "no_data" && (
                <div className="text-xs text-slate-400 mt-2">{t("Henüz bu portaldan tarama yapılmadı.")}</div>
              )}
            </div>
          );
        })}
      </div>

      <div className="bg-slate-800/50 border border-slate-700/40 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-white mb-2">{t("ℹ️ Portal Sağlığı Nedir?")}</h3>
        <div className="text-xs text-slate-400 space-y-1">
          <p>{t("•")}<strong className="text-emerald-400">{t("Sağlıklı:")}</strong> {t("Parser düzgün çalışıyor, sonuçlar tutarlı")}</p>
          <p>{t("•")}<strong className="text-amber-400">{t("Uyarı:")}</strong> {t("Bazı sonuçlarda eksik alan veya yanlış URL tespit edildi")}</p>
          <p>{t("•")}<strong className="text-red-400">{t("Bozulmuş:")}</strong> {t("Parser büyük olasılıkla kırılmış — HTML artifact, boş alanlar")}</p>
        </div>
      </div>
    </div>
  );
}
