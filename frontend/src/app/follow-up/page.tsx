"use client";
import { notify } from "@/lib/notify";
import { useLanguage } from "@/lib/i18n";
import { useEffect, useState } from "react";
import { Calendar, Clock, Copy, Check, ExternalLink, AlertCircle, CalendarPlus } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function FollowUpPage() {
  const { translate: t } = useLanguage();
  const [pendingList, setPendingList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Calendar event state
  const [calendarForm, setCalendarForm] = useState({
    title: "",
    company: "",
    interview_time_iso: new Date(Date.now() + 86400000).toISOString().slice(0, 16),
    meeting_link: ""
  });
  const [calendarUrl, setCalendarUrl] = useState<string | null>(null);

  useEffect(() => {
    fetchFromApi("/outcome/follow_up/pending")
      .then((res) => setPendingList(res.pending_follow_ups || []))
      .catch(() => notify(t("Veriler yüklenemedi. Sayfayı yenileyip tekrar dene.")))
      .finally(() => setLoading(false));
  }, []);

  async function handleCreateCalendarLink() {
    if (!calendarForm.company.trim() || !calendarForm.title.trim()) {
      notify(t("Şirket ve pozisyon alanlarını doldurun."));
      return;
    }
    try {
      const res = await fetchFromApi("/outcome/calendar/event_url", {
        method: "POST",
        body: JSON.stringify(calendarForm)
      });
      setCalendarUrl(res.calendar_url);
    } catch (e) {
      notify(t("Takvim linki oluşturulamadı."));
    }
  }

  async function handleResolveReminder(jobId: string) {
    try {
      await fetchFromApi(`/outcome/follow_up/${encodeURIComponent(jobId)}/resolve`, { method: "POST" });
      setPendingList((items) => items.filter((item) => item.job_key !== jobId));
    } catch {
      notify(t("Hatırlatma kapatılamadı. Tekrar deneyin."));
    }
  }

  function copyText(text: string, id: string) {
    navigator.clipboard.writeText(text);
    setCopiedKey(id);
    setTimeout(() => setCopiedKey(null), 2000);
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Calendar className="w-7 h-7 text-amber-400" /> {t("Takip takvimi")}</h1>
        <p className="text-slate-400 mt-1">
          {t("Başvurusu yapılan rollerin yanıt sürelerini takip edin, 3 aşamalı nazik takip e-postalarını kopyalayın ve mülakatları takvime işleyin.")}</p>
      </div>

      {/* Grid: Follow Up Alerts & Calendar Scheduler */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Overdue Follow-ups */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Clock className="w-4 h-4 text-amber-400" />
              {t("Takip Zamanı Gelen Başvurular (")}{pendingList.length})
            </h2>
          </div>

          {loading ? (
            <div className="text-center py-16 text-slate-400">{t("Yükleniyor...")}</div>
          ) : pendingList.length === 0 ? (
            <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-8 text-center">
              <AlertCircle className="w-8 h-8 text-slate-400 mx-auto mb-2" />
              <div className="text-xs text-slate-400">{t("Şu anda zamanı gelmiş bekleyen takip bulunmuyor.")}</div>
            </div>
          ) : (
            <div className="space-y-4">
              {pendingList.map((item) => (
                <div
                  key={item.job_key}
                  className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-4"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-bold text-white">{item.title}</div>
                      <div className="text-xs text-blue-400 font-medium">{item.company}</div>
                    </div>
                    <div className="text-right">
                      <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                        {item.days_since_applied} {t("gündür yanıt yok")}</span>
                    </div>
                  </div>

                  {/* Cadence Steps */}
                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-slate-400">{t("Önerilen Takip Şablonları:")}</div>
                    <div className="grid grid-cols-1 gap-2">
                      {item.cadence.map((c: any, i: number) => (
                        <div
                          key={i}
                          className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-3 text-xs space-y-2"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-slate-300">{c.stage} — {c.purpose}</span>
                            <button
                              onClick={() => copyText(c.body, `${item.job_key}-${i}`)}
                              className="text-slate-400 hover:text-white flex items-center gap-1 text-xs"
                            >
                              {copiedKey === `${item.job_key}-${i}` ? (
                                <Check className="w-3 h-3 text-emerald-400" />
                              ) : (
                                <Copy className="w-3 h-3" />
                              )}
                              {t("Kopyala")}</button>
                          </div>
                          <div className="text-xs text-slate-400 whitespace-pre-wrap font-sans max-h-24 overflow-y-auto bg-slate-900/50 p-2 rounded-lg">
                            {c.body}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleResolveReminder(item.job_key)}
                    className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:border-emerald-500 hover:text-emerald-300"
                  >
                    {t("Takip hatırlatmasını kapat")}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Google Calendar Event Generator */}
        <div className="space-y-4">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-4">
            <div className="flex items-center gap-2 text-sm font-bold text-white">
              <CalendarPlus className="w-4 h-4 text-emerald-400" />
              <span>{t("Mülakatı Takvime Ekle")}</span>
            </div>
            <div className="text-xs text-slate-400">
              {t("Yaklaşan teknik veya HR mülakatını tek tıkla Google Calendar'a işleyin.")}</div>

            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-400 uppercase font-mono">{t("Şirket")}</label>
                <input
                  value={calendarForm.company}
                  onChange={(e) => setCalendarForm({ ...calendarForm, company: e.target.value })}
                  className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2 text-xs text-white"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 uppercase font-mono">{t("Pozisyon")}</label>
                <input
                  value={calendarForm.title}
                  onChange={(e) => setCalendarForm({ ...calendarForm, title: e.target.value })}
                  className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2 text-xs text-white"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 uppercase font-mono">{t("Tarih & Saat")}</label>
                <input
                  type="datetime-local"
                  value={calendarForm.interview_time_iso}
                  onChange={(e) => setCalendarForm({ ...calendarForm, interview_time_iso: e.target.value })}
                  className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2 text-xs text-white"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 uppercase font-mono">{t("Toplantı Linki")}</label>
                <input
                  value={calendarForm.meeting_link}
                  onChange={(e) => setCalendarForm({ ...calendarForm, meeting_link: e.target.value })}
                  className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2 text-xs text-white"
                />
              </div>

              <button
                onClick={handleCreateCalendarLink}
                className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5"
              >
                <Calendar className="w-3.5 h-3.5" />
                {t("Takvim Bağlantısı Oluştur")}</button>

              {calendarUrl && (
                <a
                  href={calendarUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 shadow-lg shadow-blue-600/20"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  {t("Google Calendar'da Aç")}</a>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
