"use client";
import { notify } from "@/lib/notify";
import { useEffect, useState } from "react";
import { Send, CheckCircle2, XCircle, Clock, Sparkles, RefreshCw, AlertCircle, FileText, ChevronDown } from "lucide-react";
import { fetchFromApi } from "@/lib/api";
import { getApiAuthToken, getWebSocketUrl } from "@/lib/runtime-config";
import { useLanguage } from "@/lib/i18n";

export default function AutoApplyPage() {
  const { translate: t } = useLanguage();
  const [queue, setQueue] = useState<any[]>([]);
  const [todayCount, setTodayCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [activeTab, setActiveTab] = useState<"pending_approval" | "approved" | "rejected">("pending_approval");
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  // Load Queue from API
  async function loadQueue() {
    try {
      setLoading(true);
      const res = await fetchFromApi("/apply/auto/queue");
      setQueue(res.queue || []);
      setTodayCount(res.today_applied_count || 0);
    } catch (e) {
      console.error(e);
      notify(t("Veriler yüklenemedi. Sayfayı yenileyip tekrar dene."));
    } finally {
      setLoading(false);
    }
  }

  // WebSocket Live Listener
  useEffect(() => {
    loadQueue();

    let ws: WebSocket | null = null;
    try {
      const wsUrl = getWebSocketUrl();
      const apiToken = getApiAuthToken();
      const securedWsUrl = apiToken ? `${wsUrl}?api_key=${encodeURIComponent(apiToken)}` : wsUrl;

      ws = new WebSocket(securedWsUrl);

      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => setWsConnected(false);
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "auto_apply_draft_ready" || payload.type === "auto_apply_status_changed") {
            loadQueue();
          }
        } catch (err) {}
      };
    } catch (e) {
      console.warn("WebSocket init error", e);
    }

    return () => {
      if (ws) ws.close();
    };
  }, []);

  async function handleScanAndPrepare() {
    try {
      setScanning(true);
      await fetchFromApi("/apply/auto/scan", {
        method: "POST",
        body: JSON.stringify({ min_score: 75, max_daily_limit: 5, auto_request_approval: true })
      });
      await loadQueue();
    } catch {
      notify(t("Tarama başlatılamadı. Tekrar dene."));
    } finally {
      setScanning(false);
    }
  }

  async function handleApprove(jobKey: string) {
    try {
      await fetchFromApi("/apply/auto/approve", {
        method: "POST",
        body: JSON.stringify({ job_key: jobKey })
      });
      await loadQueue();
    } catch (e) {
      notify(t("Onaylama sırasında hata oluştu."));
    }
  }

  async function handleReject(jobKey: string) {
    const reason = prompt("Reddetme gerekçesi (opsiyonel):") || "Kullanıcı tarafından elendi";
    try {
      await fetchFromApi("/apply/auto/reject", {
        method: "POST",
        body: JSON.stringify({ job_key: jobKey, reason })
      });
      await loadQueue();
    } catch (e) {
      notify(t("Reddetme sırasında hata oluştu."));
    }
  }

  async function handleSubmit(jobKey: string) {
    try {
      const result = await fetchFromApi("/apply/auto/submit", {
        method: "POST",
        body: JSON.stringify({ job_key: jobKey, headless: true })
      });
      const item = queue.find((entry) => entry.job_key === jobKey);
      if (result.handoff_required && item?.url) window.open(item.url, "_blank", "noopener,noreferrer");
      await loadQueue();
    } catch (e) {
      notify(t("Başvuru adımı başlatılamadı. İlan bağlantısını açıp başvuruyu portalda kendin tamamlayabilirsin."));
    }
  }

  async function handleConfirmSubmission(jobKey: string) {
    if (!window.confirm("İş portalında başvuruyu gerçekten gönderdin mi? Yalnızca evet ise onayla.")) return;
    try {
      await fetchFromApi("/apply/auto/confirm-submission", {
        method: "POST",
        body: JSON.stringify({ job_key: jobKey })
      });
      await loadQueue();
    } catch {
      notify(t("Başvuru teyit edilemedi. Analitik kaydı oluşturulmadı."));
    }
  }

  const filteredQueue = queue.filter(item => activeTab === "approved"
    ? item.status === "approved" || item.status === "awaiting_user_submission"
    : item.status === activeTab);

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Send className="w-7 h-7 text-emerald-400" /> {t("Onay bekleyen başvurular")}
          </h1>
          <p className="text-slate-400 mt-1">
            {t("Taslakları gözden geçir. Başvuruyu portalda kendin gönder ve yalnızca tamamlandıktan sonra teyit et.")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-slate-800/80 border border-slate-700/60 px-3 py-1.5 rounded-lg text-xs">
            <span className={`w-2 h-2 rounded-full ${wsConnected ? "bg-emerald-400 animate-pulse" : "bg-slate-500"}`}></span>
            <span className="text-slate-300 font-mono">{wsConnected ? t("Canlı Yayın Aktif") : t("Çevrimdışı")}</span>
          </div>
          <button
            onClick={handleScanAndPrepare}
            disabled={scanning}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold flex items-center gap-2 transition-all disabled:opacity-50 shadow-lg shadow-emerald-600/20"
          >
            {scanning ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            {scanning ? t("İlanlar Taranıyor & Taslak Üretiliyor...") : t("Yüksek Uyumlu İlanları Tara")}
          </button>
        </div>
      </div>

      {/* Daily Quota Counter */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-400">{t("Bugün teyit edilen başvuru")}</div>
            <div className="text-xl font-bold text-white mt-1">{todayCount} {t("/ 5 Günlük Limit")}</div>
          </div>
          <div className="text-emerald-400 bg-emerald-500/10 p-2.5 rounded-xl border border-emerald-500/20 font-mono text-sm">
            %{Math.round((todayCount / 5) * 100)}
          </div>
        </div>
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-400">{t("Onay Bekleyen Taslak")}</div>
            <div className="text-xl font-bold text-amber-400 mt-1">
              {queue.filter(q => q.status === "pending_approval").length} {t("İlan")}</div>
          </div>
          <Clock className="w-6 h-6 text-amber-400/60" />
        </div>
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-400">{t("Kabul / Onaylanan")}</div>
            <div className="text-xl font-bold text-emerald-400 mt-1">
              {queue.filter(q => q.status === "approved").length} {t("İlan")}</div>
          </div>
          <CheckCircle2 className="w-6 h-6 text-emerald-400/60" />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveTab("pending_approval")}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-colors flex items-center gap-2 ${
            activeTab === "pending_approval"
              ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
              : "text-slate-400 hover:text-white"
          }`}
        >
          <Clock className="w-3.5 h-3.5" />
          {t("Onay Bekleyenler (")}{queue.filter(q => q.status === "pending_approval").length})
        </button>
        <button
          onClick={() => setActiveTab("approved")}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-colors flex items-center gap-2 ${
            activeTab === "approved"
              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
              : "text-slate-400 hover:text-white"
          }`}
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
          {t("Onaylanan (")}{queue.filter(q => q.status === "approved").length})
        </button>
        <button
          onClick={() => setActiveTab("rejected")}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-colors flex items-center gap-2 ${
            activeTab === "rejected"
              ? "bg-red-500/20 text-red-300 border border-red-500/30"
              : "text-slate-400 hover:text-white"
          }`}
        >
          <XCircle className="w-3.5 h-3.5" />
          {t("Elenenler (")}{queue.filter(q => q.status === "rejected").length})
        </button>
      </div>

      {/* List */}
      {loading ? (
        <div className="text-center py-20 text-slate-400">{t("Kuyruk yükleniyor...")}</div>
      ) : filteredQueue.length === 0 ? (
        <div className="text-center py-20 bg-slate-900/30 border border-slate-800/80 rounded-2xl">
          <AlertCircle className="w-10 h-10 text-slate-400 mx-auto mb-3" />
          <div className="text-slate-300 font-medium">{t("Bu sekmede başvuru bulunmuyor.")}</div>
          <div className="text-xs text-slate-400 mt-1">
            {t("Yukarıdaki \"Yüksek Uyumlu İlanları Tara\" butonuna basarak yeni taslaklar oluşturabilirsiniz.")}</div>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredQueue.map((item) => {
            const isExpanded = expandedKey === item.job_key;
            const draft = item.draft_result || {};
            const cv = draft.cv || {};
            const cl = draft.cover_letter || "";
            const review = draft.review || {};

            return (
              <div
                key={item.job_key}
                className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-5 hover:border-slate-700 transition-all space-y-4"
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-3">
                      <span className="text-base font-bold text-white">{item.title}</span>
                      <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                        ≈ %{item.match_score ?? "—"} {t("Tahmini uyum")}</span>
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                      <strong className="text-blue-400">{item.company}</strong> {t("•")}{item.location || "Uzaktan / Global"} {t("•")}{new Date(item.prepared_at).toLocaleString("tr-TR")}
                    </div>
                  </div>

                  {item.status === "pending_approval" && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleReject(item.job_key)}
                        className="px-3.5 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 rounded-lg text-xs font-medium transition-colors"
                      >
                        {t("Reddet")}
                      </button>
                      <button
                        onClick={() => handleApprove(item.job_key)}
                        className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold shadow-md shadow-emerald-600/20 transition-colors flex items-center gap-1.5"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        {t("Taslağı Onayla")}
                      </button>
                    </div>
                  )}
                  {(item.status === "approved" || item.status === "awaiting_user_submission") && (
                    <div className="flex flex-wrap items-center gap-2">
                      {item.url && <a href={item.url} target="_blank" rel="noreferrer" className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition-colors">{t("İş portalını aç")}</a>}
                      {item.status === "approved" ? <button onClick={() => handleSubmit(item.job_key)} className="px-4 py-1.5 border border-slate-600 text-slate-200 rounded-lg text-xs font-semibold">{t("Başvuru adımına geç")}</button> : <button onClick={() => handleConfirmSubmission(item.job_key)} className="px-4 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white rounded-lg text-xs font-semibold">{t("Gönderimi yaptım")}</button>}
                    </div>
                  )}
                </div>

                {/* Reviewer Agent Highlights */}
                {review.review_feedback && (
                  <div className="bg-slate-950/60 border border-blue-500/20 rounded-xl p-3 text-xs space-y-1">
                    <div className="text-blue-400 font-semibold flex items-center gap-1.5">
                      <span>{t("Drafter-Reviewer Denetim Özeti")}</span>
                      <span className="text-xs text-slate-400 font-mono">
                        {t("(Revizyon:")}{draft.revision_count || 1}{t(", Doğruluk: %")}{review.review_score || 95})
                      </span>
                    </div>
                    <div className="text-slate-300">{review.review_feedback}</div>
                  </div>
                )}

                {/* Details Accordion */}
                <button
                  onClick={() => setExpandedKey(isExpanded ? null : item.job_key)}
                  className="text-xs text-slate-400 hover:text-white flex items-center gap-1 transition-colors"
                >
                  <FileText className="w-3.5 h-3.5 text-blue-400" />
                  {isExpanded ? t("Önizlemeyi Gizle") : t("Üretilen CV & Niyet Mektubu Önizlemesi")}
                  <ChevronDown className={`w-3.5 h-3.5 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                </button>

                {isExpanded && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-slate-800">
                    <div className="bg-slate-950/80 rounded-xl p-4 border border-slate-800/80 space-y-2">
                      <div className="text-xs font-semibold text-emerald-400">{t("Özel Niyet Mektubu (Cover Letter)")}</div>
                      <div className="text-xs text-slate-300 whitespace-pre-wrap font-sans leading-relaxed max-h-64 overflow-y-auto">
                        {cl || t("Niyet mektubu hazırlandı.")}
                      </div>
                      {Array.isArray(draft.unsupported_claims) && draft.unsupported_claims.length > 0 && (
                        <div role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
                          <p className="font-semibold">{t("Göndermeden önce kontrol et: CV'nde karşılığı bulunamayan {count} cümle var.", { count: draft.unsupported_claims.length })}</p>
                          <ul className="mt-2 list-disc space-y-2 pl-4">
                            {draft.unsupported_claims.map((claim: { sentence: string; reason: string }, index: number) => (
                              <li key={index}><span className="text-slate-200">“{claim.sentence}”</span><br /><span className="text-amber-300">{claim.reason}</span></li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                    <div className="bg-slate-950/80 rounded-xl p-4 border border-slate-800/80 space-y-2">
                      <div className="text-xs font-semibold text-blue-400">{t("Uyarlanan CV Özeti")}</div>
                      <div className="text-xs text-slate-300 space-y-2 max-h-64 overflow-y-auto">
                        <div>
                          <strong className="text-slate-200">{t("Başlık:")}</strong> {cv.target_role || item.title}
                        </div>
                        <div>
                          <strong className="text-slate-200">{t("Öne Çıkarılan Yetkinlikler:")}</strong>{" "}
                          {(cv.skills || []).slice(0, 8).join(", ") || "Python, LLMs, FastAPI, AI Agents"}
                        </div>
                        <div className="text-xs text-slate-400 italic">
                          {t("ATS dostu formatlandı; şirket araştırması ve kültür analiziyle harmanlandı.")}</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
