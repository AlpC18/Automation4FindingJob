"use client";
import { notify } from "@/lib/notify";
import { useLanguage } from "@/lib/i18n";
import { useEffect, useState } from "react";
import { Activity, Play, Square, RefreshCw, Send, CheckCircle2, AlertCircle, Radio, Bell } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function DaemonSettingsPage() {
  const { translate: t } = useLanguage();
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  // Webhook Test Form State
  const [slackUrl, setSlackUrl] = useState("");
  const [discordUrl, setDiscordUrl] = useState("");
  const [webhookResult, setWebhookResult] = useState<string | null>(null);

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
      notify(t("{sweep} completed!", { sweep: t(sweepType === "nightly" ? "Gece taraması" : "Sabah başvuru hazırlığı") }));
      await loadStatus();
    } catch (e) {
      notify(t("Tetikleme başarısız."));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleTestSlack() {
    if (!slackUrl) return notify(t("Lütfen Slack Webhook URL girin."));
    try {
      const res = await fetchFromApi("/webhook/slack", {
        method: "POST",
        body: JSON.stringify({
          webhook_url: slackUrl,
          title: "Test Uyarısı: %92 Uyumlu İlan Bulundu",
          message: "Autonomous Career Agent Engine başarıyla Slack kanalınıza bağlandı.",
          company: "Stripe",
          score: 92
        })
      });
      setWebhookResult(res.success ? "Slack testi başarılı!" : `Hata: ${res.error}`);
    } catch (e) {
      setWebhookResult("Slack bağlantı hatası.");
    }
  }

  async function handleTestDiscord() {
    if (!discordUrl) return notify(t("Lütfen Discord Webhook URL girin."));
    try {
      const res = await fetchFromApi("/webhook/discord", {
        method: "POST",
        body: JSON.stringify({
          webhook_url: discordUrl,
          title: "Test Uyarısı: Mülakat Daveti Alındı",
          message: "Discord kariyer kanalınız başarıyla aktive edildi.",
          company: "Shopify",
          score: 88
        })
      });
      setWebhookResult(res.success ? "Discord testi başarılı!" : `Hata: ${res.error}`);
    } catch (e) {
      setWebhookResult("Discord bağlantı hatası.");
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
            {t("Kullanıcı arayüzü kapalıyken bile arka planda çalışan zamanlanmış otonom taramaları ve Slack/Discord entegrasyonlarını yönetin.")}</p>
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

      {/* Webhook Hub Config Card */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
        <div className="text-sm font-bold text-white flex items-center gap-2">
          <Bell className="w-4 h-4 text-blue-400" />
          <span>{t("Slack & Discord Webhook Entegrasyon Kanalı")}</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-xs text-slate-400 uppercase font-mono">{t("Slack Incoming Webhook URL")}</label>
            <div className="flex gap-2">
              <input
                value={slackUrl}
                onChange={(e) => setSlackUrl(e.target.value)}
                placeholder="https://hooks.slack.com/services/..."
                className="flex-1 bg-slate-950/80 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white"
              />
              <button
                onClick={handleTestSlack}
                className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 rounded-xl"
              >
                {t("Test Et")}</button>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs text-slate-400 uppercase font-mono">{t("Discord Webhook URL")}</label>
            <div className="flex gap-2">
              <input
                value={discordUrl}
                onChange={(e) => setDiscordUrl(e.target.value)}
                placeholder="https://discord.com/api/webhooks/..."
                className="flex-1 bg-slate-950/80 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white"
              />
              <button
                onClick={handleTestDiscord}
                className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 rounded-xl"
              >
                {t("Test Et")}</button>
            </div>
          </div>
        </div>

        {webhookResult && (
          <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 font-mono">
            {webhookResult}
          </div>
        )}
      </div>
    </div>
  );
}
