"use client";
import { useLanguage } from "@/lib/i18n";

import { useEffect, useState } from "react";
import {
  Inbox,
  Send,
  Sparkles,
  CheckCircle2,
  Video,
  RefreshCw,
  Plus,
  Smartphone,
  ExternalLink,
  Mail,
  Layers,
} from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function InboxPage() {
  const { translate: t } = useLanguage();
  const [messages, setMessages] = useState<any[]>([]);
  const [telegramStatus, setTelegramStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Dispatching Telegram briefing
  const [dispatchingBriefing, setDispatchingBriefing] = useState(false);
  const [, setBriefingResult] = useState<string | null>(null);

  // Telegram test command
  const [testCmd, setTestCmd] = useState("/status");
  const [cmdResult, setCmdResult] = useState<string | null>(null);

  // Simulate incoming email modal
  const [showSimulateModal, setShowSimulateModal] = useState(false);
  const [simSender, setSimSender] = useState("recruiter@stripe.com");
  const [simName, setSimName] = useState("Stripe Talent Team");
  const [simSubject, setSimSubject] = useState("Interview Invitation: Senior Systems Engineer");
  const [simBody, setSimBody] = useState(
    "Hi Alperen,\n\nWe were impressed by your background in autonomous systems. We would love to invite you to a 30-minute introductory call: https://meet.google.com/xyz-abcd-efg"
  );
  const [simulating, setSimulating] = useState(false);

  // Selected message for replying
  const [selectedMessage, setSelectedMessage] = useState<any>(null);
  const [customReply, setCustomReply] = useState("");
  const [sendingReply, setSendingReply] = useState(false);

  // Official OAuth2 & Celery Queue State
  const [oauthStatus, setOauthStatus] = useState<any>(null);
  const [queueStatus, setQueueStatus] = useState<any>(null);
  const [backgroundJobs, setBackgroundJobs] = useState<any[]>([]);
  const [retryingJobId, setRetryingJobId] = useState<string | null>(null);
  const [syncingOAuth, setSyncingOAuth] = useState(false);
  const [oauthFeedback, setOauthFeedback] = useState<string | null>(null);

  async function loadData() {
    try {
      setLoading(true);
      const [inboxRes, tgRes, oauthRes, qRes, jobsRes] = await Promise.all([
        fetchFromApi("/inbox/messages").catch(() => ({ messages: [] })),
        fetchFromApi("/telegram/status").catch(() => ({ is_configured: false, events: [] })),
        fetchFromApi("/inbox/oauth/status").catch(() => null),
        fetchFromApi("/tasks/status").catch(() => null),
        fetchFromApi("/tasks/jobs?limit=30").catch(() => ({ jobs: [] }))
      ]);
      setMessages(inboxRes.messages || []);
      setTelegramStatus(tgRes);
      setOauthStatus(oauthRes);
      setQueueStatus(qRes);
      setBackgroundJobs(jobsRes.jobs || []);
    } finally {
      setLoading(false);
    }
  }

  async function handleConnectOAuthInstant(provider: string) {
    try {
      setSyncingOAuth(true);
      setOauthFeedback(null);
      const res = await fetchFromApi("/inbox/oauth/connect_instant", {
        method: "POST",
        body: JSON.stringify({ provider })
      });
      setOauthFeedback(res.message || `✓ ${provider.toUpperCase()} bağlandı!`);
      await loadData();
    } catch (e: any) {
      setOauthFeedback("Bağlantı hatası oluştu.");
    } finally {
      setSyncingOAuth(false);
    }
  }

  async function handleSyncOAuth() {
    try {
      setSyncingOAuth(true);
      setOauthFeedback(null);
      const res = await fetchFromApi("/inbox/oauth/sync", { method: "POST" });
      setOauthFeedback(res.message || "E-postalar senkronize edildi.");
      await loadData();
    } catch (e: any) {
      setOauthFeedback("Senkronizasyon hatası.");
    } finally {
      setSyncingOAuth(false);
    }
  }

  async function handleDisconnectOAuth(provider: string) {
    if (!confirm(t("Are you sure you want to disconnect {provider}?", { provider: provider.toUpperCase() }))) return;
    try {
      await fetchFromApi("/inbox/oauth/disconnect", {
        method: "POST",
        body: JSON.stringify({ provider })
      });
      setOauthFeedback(`${provider.toUpperCase()} hesabı bağlantısı kesildi.`);
      await loadData();
    } catch (e) {
      // ignore
    }
  }

  useEffect(() => {
    loadData();
    const refreshJobs = window.setInterval(async () => {
      try {
        const response = await fetchFromApi("/tasks/jobs?limit=30");
        setBackgroundJobs(response.jobs || []);
      } catch {
        // Preserve the last successful snapshot when the worker API is offline.
      }
    }, 8000);
    return () => window.clearInterval(refreshJobs);
  }, []);

  async function retryBackgroundJob(jobId: string) {
    setRetryingJobId(jobId);
    try {
      await fetchFromApi(`/tasks/jobs/${encodeURIComponent(jobId)}/retry`, { method: "POST" });
      const response = await fetchFromApi("/tasks/jobs?limit=30");
      setBackgroundJobs(response.jobs || []);
    } catch (error: any) {
      setOauthFeedback(error?.message || "İş yeniden denenemedi.");
    } finally {
      setRetryingJobId(null);
    }
  }

  async function handleDispatchBriefing() {
    try {
      setDispatchingBriefing(true);
      const res = await fetchFromApi("/telegram/dispatch_briefing", { method: "POST" });
      setBriefingResult(res.briefing);
      await loadData();
    } finally {
      setDispatchingBriefing(false);
    }
  }

  async function handleSendTelegramCommand() {
    if (!testCmd.trim()) return;
    try {
      const res = await fetchFromApi("/telegram/command", {
        method: "POST",
        body: JSON.stringify({ command: testCmd })
      });
      setCmdResult(res.reply);
    } catch (e) {
      setCmdResult("Komut çalıştırılamadı.");
    }
  }

  async function handleSimulateEmail() {
    try {
      setSimulating(true);
      await fetchFromApi("/inbox/simulate_email", {
        method: "POST",
        body: JSON.stringify({
          sender_email: simSender,
          sender_name: simName,
          subject: simSubject,
          body_text: simBody
        })
      });
      setShowSimulateModal(false);
      await loadData();
    } finally {
      setSimulating(false);
    }
  }

  async function handleApproveAndSendReply() {
    if (!selectedMessage) return;
    try {
      setSendingReply(true);
      await fetchFromApi("/inbox/send_reply", {
        method: "POST",
        body: JSON.stringify({
          message_id: selectedMessage.id,
          final_reply: customReply || selectedMessage.proposed_reply
        })
      });
      setSelectedMessage(null);
      await loadData();
    } finally {
      setSendingReply(false);
    }
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Inbox className="w-6 h-6 text-blue-500" />
            {t("Gelen kutusu")}</h1>
          <p className="text-xs text-slate-400 mt-1">
            {t("İşverenlerden gelen yanıtları sınıflandırın, mülakat randevularını takviminizle senkronize edin ve tüm süreci Telegram'dan yönetin.")}</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowSimulateModal(true)}
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold px-4 py-2 rounded-xl transition border border-slate-700"
          >
            <Plus className="w-3.5 h-3.5" /> {t("Gelen E-posta Simüle Et")}</button>
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-4 py-2 rounded-xl transition shadow-md shadow-blue-600/20 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /> {t("Yenile")}</button>
        </div>
      </div>

      <section className="rounded-2xl border border-slate-800/80 bg-[#0e1524] p-5 space-y-4" aria-labelledby="background-jobs-title">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 id="background-jobs-title" className="text-sm font-semibold text-white flex items-center gap-2">
              <Layers className="h-4 w-4 text-blue-400" /> {t("Arka Plan İşleri")}</h2>
            <p className="mt-1 text-xs text-slate-400">{t("Tarama ve başvuru işlerinin kalıcı durumu · otomatik yenileme 8 sn.")}</p>
          </div>
          <button onClick={loadData} className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800">{t("Yenile")}</button>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[
            ["Bekliyor", ["queued", "retrying"]],
            ["Çalışıyor", ["running"]],
            ["Başarılı", ["succeeded"]],
            ["Başarısız", ["failed"]],
          ].map(([label, statuses]: any) => (
            <div key={label} className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
              <div className="text-xs uppercase tracking-wide text-slate-400">{t(label)}</div>
              <div className="mt-1 text-lg font-semibold text-slate-100">
                {backgroundJobs.filter((job) => statuses.includes(job.status)).length}
              </div>
            </div>
          ))}
        </div>
        {queueStatus?.durable_jobs && (
          <p className="text-xs text-slate-400">
            {t("Kalıcı kuyruk")}: {queueStatus.durable_jobs.queued + queueStatus.durable_jobs.retrying} {t("bekliyor")} · {queueStatus.durable_jobs.running} {t("çalışıyor")} · {queueStatus.durable_jobs.failed} {t("başarısız")}
          </p>
        )}
        {backgroundJobs.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-800 p-4 text-xs text-slate-400">{t("Henüz kaydedilmiş bir iş yok.")}</p>
        ) : (
          <div className="max-h-96 space-y-2 overflow-y-auto">
            {backgroundJobs.map((job) => {
              const failed = job.status === "failed";
              const statusColor = failed ? "text-rose-300" : job.status === "succeeded" ? "text-emerald-300" : job.status === "running" ? "text-blue-300" : "text-amber-300";
              return (
                <article key={job.id} className="flex flex-col gap-2 rounded-lg border border-slate-800 bg-slate-950/50 p-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                      <span className="font-medium text-slate-100">{job.job_type === "scrape" ? t("İlan tarama") : job.job_type === "application_submit" ? t("Başvuru gönderimi") : job.job_type}</span>
                      <span className={`uppercase ${statusColor}`}>{job.status}</span>
                      <span className="text-slate-400">{t("Deneme")}{job.attempts}/{job.max_attempts}</span>
                      <time className="text-slate-400">{job.updated_at || job.created_at}</time>
                    </div>
                    {job.payload?.keywords && <p className="truncate text-xs text-slate-400">{t("Arama:")}{job.payload.keywords}</p>}
                    {job.error_text && <p className="break-words text-xs text-rose-300">{t("Hata:")}{job.error_text}</p>}
                  </div>
                  {failed && (
                    <button
                      onClick={() => retryBackgroundJob(job.id)}
                      disabled={retryingJobId === job.id}
                      className="shrink-0 rounded-lg border border-rose-500/30 px-3 py-1.5 text-xs font-medium text-rose-200 hover:bg-rose-950/40 disabled:opacity-50"
                    >
                      {retryingJobId === job.id ? "Yeniden deneniyor…" : "Yeniden dene"}
                    </button>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>

      {/* Official OAuth2 Connection & Celery Queue Engine */}
      <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <Mail className="w-5 h-5 text-indigo-400" />
              {t("Resmi E-posta OAuth2 Bağlantısı (Gmail & Outlook)")}</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              {t("Uygulama şifresi zorunluluğu olmadan, tek tıkla resmi Google Cloud Console & Microsoft Azure OAuth2 yetkilendirmesi.")}</p>
          </div>

          <div className="flex items-center gap-2">
            {/* Celery / Redis Queue Badge */}
            <span
              className={`text-xs px-3 py-1 rounded-xl font-mono flex items-center gap-1.5 border ${
                queueStatus?.redis_connected
                  ? "bg-emerald-950/40 text-emerald-400 border-emerald-500/30"
                  : "bg-slate-900 text-slate-300 border-slate-700"
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              {queueStatus?.mode === "CELERY_REDIS" ? "Celery + Redis Worker: Aktif" : "Asenkron Kuyruk (Local): Aktif"}
            </span>

            <button
              onClick={handleSyncOAuth}
              disabled={syncingOAuth}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-4 py-2 rounded-xl transition shadow-md shadow-indigo-600/20 disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${syncingOAuth ? "animate-spin" : ""}`} />
              {syncingOAuth ? t("E-postalar Çekiliyor...") : t("OAuth E-postalarını Senkronize Et")}
            </button>
          </div>
        </div>

        {/* OAuth Provider Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
          {/* Google Card */}
          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center justify-center font-bold text-red-400 text-xs">
                  G
                </div>
                <div>
                  <div className="text-xs font-bold text-white">{t("Google Gmail API")}</div>
                  <div className="text-xs text-slate-400">
                    {oauthStatus?.google?.connected
                      ? `Bağlı: ${oauthStatus.google.email}`
                      : t("Gmail gelen kutusu ve yanıt yetkisi")}
                  </div>
                </div>
              </div>

              <span
                className={`text-xs px-2 py-0.5 rounded-full font-mono ${
                  oauthStatus?.google?.connected
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    : "bg-slate-800 text-slate-400"
                }`}
              >
                {oauthStatus?.google?.connected ? t("● Bağlı (Aktif)") : t("○ Bağlı Değil")}
              </span>
            </div>

            <div className="flex gap-2">
              {oauthStatus?.google?.connected ? (
                <button
                  onClick={() => handleDisconnectOAuth("google")}
                  className="w-full bg-slate-900 hover:bg-rose-950/40 hover:text-rose-300 text-slate-400 text-xs py-2 rounded-lg border border-slate-800 transition"
                >
                  {t("Bağlantıyı Kes")}</button>
              ) : (
                <>
                  <a
                    href={oauthStatus?.google?.auth_url || "#"}
                    className="flex-1 bg-red-600 hover:bg-red-500 text-white text-xs font-semibold py-2 rounded-lg text-center transition shadow-sm"
                  >
                    {t("Google ile Bağlan")}</a>
                  <button
                    onClick={() => handleConnectOAuthInstant("google")}
                    disabled={syncingOAuth}
                    className="px-3 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg border border-slate-700 transition"
                    title={t("Geliştirici testi için anında bağla")}
                  >
                    {t("Hızlı Bağla")}</button>
                </>
              )}
            </div>
          </div>

          {/* Microsoft Outlook Card */}
          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center font-bold text-blue-400 text-xs">
                  M
                </div>
                <div>
                  <div className="text-xs font-bold text-white">{t("Microsoft Outlook (Graph API)")}</div>
                  <div className="text-xs text-slate-400">
                    {oauthStatus?.microsoft?.connected
                      ? `Bağlı: ${oauthStatus.microsoft.email}`
                      : "Outlook & Office365 gelen kutusu"}
                  </div>
                </div>
              </div>

              <span
                className={`text-xs px-2 py-0.5 rounded-full font-mono ${
                  oauthStatus?.microsoft?.connected
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    : "bg-slate-800 text-slate-400"
                }`}
              >
                {oauthStatus?.microsoft?.connected ? t("● Bağlı (Aktif)") : t("○ Bağlı Değil")}
              </span>
            </div>

            <div className="flex gap-2">
              {oauthStatus?.microsoft?.connected ? (
                <button
                  onClick={() => handleDisconnectOAuth("microsoft")}
                  className="w-full bg-slate-900 hover:bg-rose-950/40 hover:text-rose-300 text-slate-400 text-xs py-2 rounded-lg border border-slate-800 transition"
                >
                  {t("Bağlantıyı Kes")}</button>
              ) : (
                <>
                  <a
                    href={oauthStatus?.microsoft?.auth_url || "#"}
                    className="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold py-2 rounded-lg text-center transition shadow-sm"
                  >
                    {t("Outlook ile Bağlan")}</a>
                  <button
                    onClick={() => handleConnectOAuthInstant("microsoft")}
                    disabled={syncingOAuth}
                    className="px-3 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg border border-slate-700 transition"
                    title={t("Geliştirici testi için anında bağla")}
                  >
                    {t("Hızlı Bağla")}</button>
                </>
              )}
            </div>
          </div>
        </div>

        {oauthFeedback && (
          <div className="text-xs text-sky-400 font-medium bg-sky-950/30 p-2.5 rounded-xl border border-sky-900/50">
            {oauthFeedback}
          </div>
        )}
      </div>

      {/* Grid: Telegram Center (Left) & Inbox Messages (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Telegram Mobile Command Card (1 col) */}
        <div className="space-y-6">
          <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Smartphone className="w-5 h-5 text-sky-400" />
                <h2 className="text-sm font-semibold text-white">{t("Telegram Mobil Komuta")}</h2>
              </div>
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-mono ${
                  telegramStatus?.is_configured
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                }`}
              >
                {telegramStatus?.is_configured ? t("Canlı Bot Bağlı") : t("Simüle Modu (Aktif)")}
              </span>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              {t("Her sabah günün en yüksek ATS puanlı ilanlarını ve mülakat davetlerini Telegram'a anlık brifing olarak gönderir.")}</p>

            <button
              onClick={handleDispatchBriefing}
              disabled={dispatchingBriefing}
              className="w-full bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold py-2.5 rounded-xl transition flex items-center justify-center gap-2 shadow-lg shadow-sky-600/20 disabled:opacity-50"
            >
              <Send className={`w-3.5 h-3.5 ${dispatchingBriefing ? "animate-spin" : ""}`} />
              {dispatchingBriefing ? t("Brifing Gönderiliyor...") : t("Günlük Brifingi Şimdi Gönder")}
            </button>

            {/* Test Command Box */}
            <div className="pt-3 border-t border-slate-800 space-y-2">
              <div className="text-xs font-semibold text-slate-300">{t("Telegram Komut Simülatörü:")}</div>
              <div className="flex gap-2">
                <select
                  value={testCmd}
                  onChange={(e) => setTestCmd(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white flex-1 focus:outline-none"
                >
                  <option value="/status">{t("/status (Kanban Durumu)")}</option>
                  <option value="/briefing">{t("/briefing (Günün İlanları)")}</option>
                  <option value="/apply job_demo">{t("/apply &lt;id&gt; (Başvuru Onayı)")}</option>
                  <option value="/help">{t("/help (Komut Rehberi)")}</option>
                </select>
                <button
                  onClick={handleSendTelegramCommand}
                  className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs px-3 py-1.5 rounded-lg font-medium border border-slate-700"
                >
                  {t("Çalıştır")}</button>
              </div>

              {cmdResult && (
                <pre className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-xs font-mono text-slate-300 whitespace-pre-wrap">
                  {cmdResult}
                </pre>
              )}
            </div>

            {/* Recent Telegram Dispatches */}
            {telegramStatus?.events && telegramStatus.events.length > 0 && (
              <div className="pt-3 border-t border-slate-800 space-y-2">
                <div className="text-xs font-semibold text-slate-300">{t("Son Gönderim Kayıtları:")}</div>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {telegramStatus.events.map((ev: any) => (
                    <div key={ev.id} className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 text-xs space-y-1">
                      <div className="flex justify-between items-center text-slate-400">
                        <span className="font-mono uppercase text-sky-400">{ev.event_type}</span>
                        <span className="text-emerald-400">{ev.status}</span>
                      </div>
                      <div className="text-slate-200 line-clamp-2">{ev.message_text}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Incoming Employer Inbox List (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Inbox className="w-5 h-5 text-indigo-400" />
                <h2 className="text-sm font-semibold text-white">{t("Gelen İşveren E-postaları (")}{messages.length})</h2>
              </div>
            </div>

            {messages.length === 0 ? (
              <div className="p-12 text-center text-slate-400 bg-slate-950/60 rounded-xl border border-slate-800">
                {t("Gelen kutusu boş. \"Gelen E-posta Simüle Et\" butonuna basarak bir mülakat daveti veya ret e-postası simüle edebilirsiniz.")}</div>
            ) : (
              <div className="space-y-3">
                {messages.map((m: any) => {
                  const isInvite = m.classification === "INTERVIEW_INVITE";
                  const isRejection = m.classification === "REJECTION";

                  return (
                    <div
                      key={m.id}
                      className={`p-4 rounded-xl border transition space-y-3 ${
                        isInvite
                          ? "bg-emerald-950/20 border-emerald-500/30"
                          : isRejection
                          ? "bg-rose-950/20 border-rose-500/20"
                          : "bg-slate-900/60 border-slate-800"
                      }`}
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-white">{m.sender_name || m.sender_email}</span>
                            <span className="text-xs text-slate-400 font-mono">&lt;{m.sender_email}&gt;</span>
                          </div>
                          <div className="text-xs font-semibold text-slate-200 mt-0.5">{m.subject}</div>
                        </div>

                        <div className="flex items-center gap-2">
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full font-mono font-semibold ${
                              isInvite
                                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                                : isRejection
                                ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                                : "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                            }`}
                          >
                            {m.classification}
                          </span>
                          <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">
                            {m.status}
                          </span>
                        </div>
                      </div>

                      <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
                        {m.body_text}
                      </p>

                      {/* Detected Video Call Link */}
                      {m.detected_meet_url && (
                        <div className="flex items-center gap-2 p-2.5 rounded-lg bg-indigo-950/40 border border-indigo-500/30 text-xs">
                          <Video className="w-4 h-4 text-indigo-400 shrink-0" />
                          <span className="text-indigo-200 font-medium">{t("Tespit Edilen Toplantı Linki:")}</span>
                          <a
                            href={m.detected_meet_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sky-400 hover:underline font-mono truncate flex items-center gap-1"
                          >
                            {m.detected_meet_url} <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                      )}

                      {/* Proposed Auto-Scheduler Reply */}
                      {m.proposed_reply && (
                        <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-semibold text-slate-300 flex items-center gap-1.5">
                              <Sparkles className="w-3.5 h-3.5 text-blue-400" />
                              {t("Yapay Zeka & Takvim Otomatik Yanıt Taslağı:")}</span>
                            <button
                              onClick={() => {
                                setSelectedMessage(m);
                                setCustomReply(m.proposed_reply);
                              }}
                              className="text-blue-400 hover:text-blue-300 font-medium text-xs"
                            >
                              {t("Düzenle & Gönder →")}</button>
                          </div>
                          <pre className="text-xs font-sans text-slate-400 whitespace-pre-wrap leading-relaxed">
                            {m.proposed_reply}
                          </pre>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Reply Approval Modal */}
      {selectedMessage && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0e1524] border border-slate-800 rounded-2xl w-full max-w-2xl p-6 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-white">{t("İşverene SMTP ile Yanıt Gönder")}</h3>
                <div className="text-xs text-slate-400">{t("Alıcı:")} {selectedMessage.sender_email}</div>
              </div>
              <button onClick={() => setSelectedMessage(null)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <textarea
              value={customReply}
              onChange={(e) => setCustomReply(e.target.value)}
              className="w-full h-44 bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 leading-relaxed focus:outline-none focus:border-blue-500"
            />

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setSelectedMessage(null)}
                className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-semibold"
              >
                {t("İptal")}</button>
              <button
                onClick={handleApproveAndSendReply}
                disabled={sendingReply}
                className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-blue-600/20 disabled:opacity-50"
              >
                <Send className="w-3.5 h-3.5" />
                {sendingReply ? t("Gönderiliyor...") : t("Onayla & E-postayı Gönder")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Simulate Incoming Email Modal */}
      {showSimulateModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0e1524] border border-slate-800 rounded-2xl w-full max-w-lg p-6 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white">{t("Gelen E-posta Simülasyonu")}</h3>
              <button onClick={() => setShowSimulateModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-slate-400">{t("Gönderen E-posta:")}</label>
                <input
                  type="text"
                  value={simSender}
                  onChange={(e) => setSimSender(e.target.value)}
                  className="w-full mt-1 bg-slate-950 border border-slate-800 rounded-lg p-2 text-white"
                />
              </div>

              <div>
                <label className="text-slate-400">{t("Şirket / Gönderen Adı:")}</label>
                <input
                  type="text"
                  value={simName}
                  onChange={(e) => setSimName(e.target.value)}
                  className="w-full mt-1 bg-slate-950 border border-slate-800 rounded-lg p-2 text-white"
                />
              </div>

              <div>
                <label className="text-slate-400">{t("Konu (Subject):")}</label>
                <input
                  type="text"
                  value={simSubject}
                  onChange={(e) => setSimSubject(e.target.value)}
                  className="w-full mt-1 bg-slate-950 border border-slate-800 rounded-lg p-2 text-white"
                />
              </div>

              <div>
                <label className="text-slate-400">{t("E-posta İçeriği:")}</label>
                <textarea
                  value={simBody}
                  onChange={(e) => setSimBody(e.target.value)}
                  className="w-full mt-1 h-28 bg-slate-950 border border-slate-800 rounded-lg p-2 text-white"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowSimulateModal(false)}
                className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-semibold"
              >
                {t("Kapat")}</button>
              <button
                onClick={handleSimulateEmail}
                disabled={simulating}
                className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-emerald-600/20 disabled:opacity-50"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                {simulating ? t("İşleniyor...") : t("Gelen Kutusuna Düşür")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
