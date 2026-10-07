"use client";
import { notify } from "@/lib/notify";
import { useLanguage } from "@/lib/i18n";
import { useEffect, useState } from "react";
import { Play, Square, RefreshCw, Radio } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function DaemonSettingsPage() {
  const { translate: t } = useLanguage();
  const [status, setStatus] = useState<any>(null);
  const [, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  async function loadStatus() {
    try {
      setLoading(true);
      const res = await fetchFromApi("/daemon/status");
      setStatus(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadStatus();
  }, []);

  async function handleToggleDaemon(action: "start" | "stop") {
    try {
      setActionLoading(true);
      await fetchFromApi(`/daemon/${action}`, { method: "POST" });
      await loadStatus();
    } catch (e) {
      notify(t("Otomatik çalışma durumu değiştirilemedi."));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleManualTrigger(sweepType: "nightly" | "morning") {
    try {
      setActionLoading(true);
      const res = await fetchFromApi(`/daemon/trigger_${sweepType}`, { method: "POST" });
      // A failed sweep still answers HTTP 200, with the failure in the body.
      if (res?.status === "error") throw new Error(res.error);
      notify(t("{sweep} completed!", { sweep: t(sweepType === "nightly" ? "Gece taraması" : "Sabah başvuru hazırlığı") }));
      await loadStatus();
    } catch (e) {
      notify(t("Tetikleme başarısız."));
    } finally {
      setActionLoading(false);
    }
  }


  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Radio className="w-7 h-7 text-emerald-400" /> {t("Otomatik çalışma ayarları")}</h1>
          <p className="text-slate-400 mt-1">
            {t("Kullanıcı arayüzü kapalıyken bile arka planda çalışan zamanlanmış otonom taramaları yönetin.")}</p>
        </div>
        <button
          onClick={loadStatus}
          className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 rounded-lg flex items-center gap-1.5 transition-colors self-start sm:self-auto"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          {t("Yenile")}</button>
      </div>

      {/* Daemon Status Card */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span
              className={`w-3.5 h-3.5 rounded-full ${
                status?.is_running ? "bg-emerald-400 animate-pulse ring-4 ring-emerald-500/20" : "bg-rose-500"
              }`}
            />
            <div>
              <div className="text-sm font-bold text-white">
                {status?.is_running ? t("Otomatik çalışma açık") : "Otomatik çalışma kapalı"}
              </div>
              <div className="text-xs text-slate-400">
                {t("Toplam Tamamlanan Kontrol Döngüsü:")}<strong className="text-white">{status?.total_cycles_executed || 0}</strong>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {status?.is_running ? (
              <button
                onClick={() => handleToggleDaemon("stop")}
                disabled={actionLoading}
                className="px-4 py-2 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors"
              >
                <Square className="w-3.5 h-3.5" />
                {t("Durdur")}</button>
            ) : (
              <button
                onClick={() => handleToggleDaemon("start")}
                disabled={actionLoading}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-lg shadow-emerald-600/20"
              >
                <Play className="w-3.5 h-3.5" />
                {t("Otomatik çalışmayı başlat")}</button>
            )}
          </div>
        </div>

        {/* Schedule List */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
          {(status?.active_schedules || []).map((sch: any, i: number) => (
            <div key={i} className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white">{sch.name}</span>
                <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                  {sch.time || sch.interval}
                </span>
              </div>
              <div className="text-xs text-slate-400 leading-relaxed">{sch.purpose}</div>
            </div>
          ))}
        </div>

        {/* Manual Trigger Buttons */}
        <div className="pt-2 border-t border-slate-800 flex flex-wrap gap-2 text-xs">
          <span className="text-slate-400 font-semibold self-center mr-2">{t("Manuel Tetikleyiciler:")}</span>
          <button
            onClick={() => handleManualTrigger("nightly")}
            disabled={actionLoading}
            className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg transition-colors"
          >
            {t("Gece Taramasını Şimdi Çalıştır")}</button>
          <button
            onClick={() => handleManualTrigger("morning")}
            disabled={actionLoading}
            className="px-3.5 py-1.5 bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 border border-indigo-500/30 rounded-lg transition-colors"
          >
            {t("Sabah Başvuru Hazırlığını Şimdi Çalıştır")}</button>
        </div>
      </div>
    </div>
  );
}
