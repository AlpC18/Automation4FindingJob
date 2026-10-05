"use client";
import { notify } from "@/lib/notify";
import { useLanguage } from "@/lib/i18n";
import { useEffect, useState } from "react";
import { Mail, Send, ShieldCheck, Copy, Check, Sparkles, RefreshCw, UserCheck } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function ColdOutreachPage() {
  const { translate: t } = useLanguage();
  const [form, setForm] = useState({
    manager_name: "Sarah Jenkins",
    manager_title: "VP of Engineering",
    company: "Stripe",
    target_role: "Staff Backend & Autonomous Systems Architect",
    recent_news_or_stack: "their expansion into real-time payment agent orchestration and high-concurrency event streams"
  });

  const [loading, setLoading] = useState(false);
  const [generatedOutreach, setGeneratedOutreach] = useState<any>(null);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  useEffect(() => {
    fetchFromApi("/apply/outreach/list")
      .then((res) => setCampaigns(res.outreach_list || []))
      .catch(() => {});
  }, []);

  async function handleGenerate() {
    try {
      setLoading(true);
      const res = await fetchFromApi("/apply/outreach/generate", {
        method: "POST",
        body: JSON.stringify(form)
      });
      setGeneratedOutreach(res);
      // Refresh list
      const updated = await fetchFromApi("/apply/outreach/list");
      setCampaigns(updated.outreach_list || []);
    } catch (e) {
      notify(t("Soğuk e-posta oluşturulamadı."));
    } finally {
      setLoading(false);
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
          <Mail className="w-7 h-7 text-rose-400" /> {t("Yöneticiye doğrudan ulaş")}</h1>
        <p className="text-slate-400 mt-1">
          {t("İşe alım portallarındaki kuyrukları atlayın: Mühendislik Yöneticisi ve CTO'lara 1-e-1 değer odaklı, spam puanı denetlenmiş kişiselleştirilmiş e-postalar gönderin.")}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Input Form */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-4">
          <div className="text-sm font-bold text-white flex items-center gap-2">
            <UserCheck className="w-4 h-4 text-rose-400" />
            <span>{t("Karar Verici & Şirket Bilgileri")}</span>
          </div>

          <div className="space-y-3">
            <div>
              <label className="text-xs text-slate-400 uppercase font-mono">{t("Yönetici Adı Soyadı")}</label>
              <input
                value={form.manager_name}
                onChange={(e) => setForm({ ...form, manager_name: e.target.value })}
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2.5 text-xs text-white"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 uppercase font-mono">{t("Unvanı (Örn: VP of Eng, CTO)")}</label>
              <input
                value={form.manager_title}
                onChange={(e) => setForm({ ...form, manager_title: e.target.value })}
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2.5 text-xs text-white"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 uppercase font-mono">{t("Şirket")}</label>
              <input
                value={form.company}
                onChange={(e) => setForm({ ...form, company: e.target.value })}
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2.5 text-xs text-white"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 uppercase font-mono">{t("Hedef Pozisyonunuz")}</label>
              <input
                value={form.target_role}
                onChange={(e) => setForm({ ...form, target_role: e.target.value })}
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2.5 text-xs text-white"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 uppercase font-mono">{t("Şirket Odak Noktası / Kanca")}</label>
              <textarea
                rows={3}
                value={form.recent_news_or_stack}
                onChange={(e) => setForm({ ...form, recent_news_or_stack: e.target.value })}
                placeholder={t("Örn: Son yayınladıkları blog yazısı, kullandıkları Kafka mimarisi...")}
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2.5 text-xs text-white"
              />
            </div>

            <button
              onClick={handleGenerate}
              disabled={loading}
              className="w-full py-2.5 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-50 shadow-lg shadow-rose-600/20"
            >
              {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              {loading ? t("Mektup Kurgulanıyor...") : t("Yönetici E-Postası Üret")}
            </button>
          </div>
        </div>

        {/* Right: Generated Outreach & Deliverability Diagnostics */}
        <div className="lg:col-span-2 space-y-4">
          {generatedOutreach ? (
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="text-xs font-bold text-rose-400 uppercase tracking-wider">
                  {t("Kişiselleştirilmiş Yönetici E-Postası")}</div>
                <button
                  onClick={() => copyText(`${generatedOutreach.subject}\n\n${generatedOutreach.body}`, "full")}
                  className="text-xs text-slate-400 hover:text-white flex items-center gap-1"
                >
                  {copiedKey === "full" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  {t("Tümünü Kopyala")}</button>
              </div>

              {/* Subject */}
              <div className="bg-slate-950/80 border border-slate-800 p-3 rounded-xl">
                <div className="text-xs text-slate-400 font-mono">{t("KONU BAŞLIĞI:")}</div>
                <div className="text-xs font-semibold text-white mt-0.5">{generatedOutreach.subject}</div>
              </div>

              {/* Body */}
              <div className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl text-xs text-slate-200 whitespace-pre-wrap leading-relaxed font-sans">
                {generatedOutreach.body}
              </div>

              {/* 5-day Follow-up Hook */}
              {generatedOutreach.follow_up_note && (
                <div className="bg-slate-950/60 border border-slate-800/80 p-3 rounded-xl text-xs space-y-1">
                  <div className="text-amber-400 font-semibold text-xs">{t("⏳ 5 Gün Sonraki Yanıt Yok Hatırlatma Notu:")}</div>
                  <div className="text-slate-400 italic font-mono text-xs">{generatedOutreach.follow_up_note}</div>
                </div>
              )}

              {/* Deliverability & Spam Score Banner */}
              {generatedOutreach.spam_check && (
                <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-3 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    <span className="text-slate-200 font-semibold">{generatedOutreach.spam_check.verdict}</span>
                  </div>
                  <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                    {t("Teslimat Puanı: %")}{generatedOutreach.spam_check.deliverability_score}
                  </span>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-12 text-center text-slate-400 space-y-2">
              <Mail className="w-8 h-8 text-slate-400 mx-auto" />
              <div className="text-xs">{t("Sol taraftaki formu doldurup \"Yönetici E-Postası Üret\" butonuna basın.")}</div>
            </div>
          )}

          {/* Past Outreach History */}
          {campaigns.length > 0 && (
            <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-4 space-y-3">
              <div className="text-xs font-bold text-slate-300">{t("Önceki Yönetici Temasları (")}{campaigns.length})</div>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {campaigns.map((c, i) => (
                  <div key={i} className="text-xs bg-slate-950/60 p-2.5 rounded-lg border border-slate-800 flex items-center justify-between">
                    <div>
                      <strong className="text-white">{c.manager_name}</strong> ({c.manager_title}) • <span className="text-rose-400">{c.company}</span>
                    </div>
                    <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono uppercase">
                      {c.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
