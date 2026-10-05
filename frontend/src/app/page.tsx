"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Briefcase,
  ShieldAlert,
  Zap,
  CheckCircle2,
  TrendingUp,
  ArrowRight,
  Sparkles,
  ExternalLink,
  RefreshCw,
  Search,
  X
} from "lucide-react";
import { fetchFromApi, waitForBackgroundJob } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import SetupSteps from "@/components/SetupSteps";
import TodayActions from "@/components/TodayActions";

export default function DashboardOverview() {
  const { translate: t } = useLanguage();
  const [jobs, setJobs] = useState<any[]>([]);
  const [health, setHealth] = useState<any>({});
  const [funnel, setFunnel] = useState<any>({});
  const [readiness, setReadiness] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [scraping, setScraping] = useState(false);
  const [scrapeFeedback, setScrapeFeedback] = useState<string | null>(null);
  const [interviewResponses, setInterviewResponses] = useState<any[] | null>(null);
  const [responsesLoading, setResponsesLoading] = useState(false);

  async function loadData() {
    try {
      setLoading(true);
      const [jobsData, healthData, funnelData, readinessData] = await Promise.all([
        fetchFromApi("/scrape/jobs").catch(() => ({ jobs: [] })),
        fetchFromApi("/scrape/health").catch(() => ({})),
        fetchFromApi("/outcome/analytics").catch(() => ({})),
        fetchFromApi("/setup/readiness").catch(() => null)
      ]);
      setJobs(jobsData.jobs || []);
      setHealth(healthData || {});
      setFunnel(funnelData || {});
      setReadiness(readinessData);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function handleScrapeNow() {
    try {
      setScraping(true);
      setScrapeFeedback(null);
      const profileResponse = await fetchFromApi<any>("/setup/profile").catch(() => null);
      const profile = profileResponse?.profile || profileResponse;
      const roles = Array.isArray(profile?.target_roles) ? profile.target_roles.filter(Boolean) : [];
      if (!roles.length && profile?.target_role) roles.push(profile.target_role);
      if (!roles.length) {
        setScrapeFeedback(t("Önce hedef rolünü ve konumunu profilinde belirle; ardından İlanlar sayfasından manuel tarama başlatabilirsin."));
        return;
      }
      let result = await fetchFromApi<any>("/scrape/run", {
        method: "POST",
        body: JSON.stringify({ queries: roles, location_preference: profile?.location || "", remote_type: profile?.work_preference || "" })
      });
      if (result.status === "QUEUED" && result.job_id) {
        setScrapeFeedback(t("Tarama kuyruğa alındı; sonuçlar bekleniyor…"));
        const completed = await waitForBackgroundJob(result.job_id);
        if (!completed) {
          await loadData();
          setScrapeFeedback(t("Tarama arka planda sürüyor. Durumunu Gelen Kutusu sayfasındaki Arka Plan İşleri bölümünden izleyebilirsin."));
          return;
        }
        result = completed;
      }
      await fetchFromApi("/rank/evaluate_all", { method: "POST" });
      await loadData();
      if (result.errors?.length) {
        setScrapeFeedback(`${t("Tarama tamamlandı")}: ${result.current_total ?? 0} ${t("ilan")}. ${result.errors.join(" ")}`);
      } else {
        setScrapeFeedback(`${t("Tarama tamamlandı")}: ${result.current_total ?? result.total_scraped ?? 0} ${t("güncel ilan")}.`);
      }
    } catch (error: any) {
      setScrapeFeedback(error?.message || t("Tarama başarısız oldu. Kaynak ayarlarını kontrol edin."));
    } finally {
      setScraping(false);
    }
  }

  async function showInterviewResponses() {
    setResponsesLoading(true);
    try {
      const result = await fetchFromApi("/outcome/interview-responses");
      setInterviewResponses(result.responses || []);
    } catch (error: any) {
      setScrapeFeedback(error?.message || t("Mülakat dönüşleri yüklenemedi."));
    } finally { setResponsesLoading(false); }
  }

  const currentFeedJobs = jobs.filter((job) => ["Draft", "New", ""].includes(job.status || "Draft"));
  const ghostCount = currentFeedJobs.filter(j => j.ghost_score >= 35).length;
  const highMatchCount = currentFeedJobs.filter(j => j.match_score >= 70).length;

  return (
    <div className="space-y-8">
      {/* Top Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-blue-900/30 via-slate-900/50 to-indigo-900/30 border border-blue-500/20 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-blue-400 text-xs font-semibold uppercase tracking-wider">
            <Sparkles className="w-4 h-4" /> {t("Autonomous Career Engine Aktif")}
          </div>
          <h1 className="text-2xl font-bold text-white mt-1">{t("Genel Bakış")}</h1>
          <p className="text-slate-400 text-xs mt-1">
            {t("Profilini tamamla, sana uygun ilanları bul ve başvurularını tek yerden takip et.")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleScrapeNow}
            disabled={scraping}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition shadow-lg shadow-blue-600/20 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${scraping ? 'animate-spin' : ''}`} />
            {scraping ? t("Taranıyor & Puanlanıyor...") : t("Tüm platformları tara")}
          </button>
          <Link
            href="/kanban"
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold px-4 py-2.5 rounded-xl transition border border-slate-700"
          >
            <span>{t("Kanban Paneli")}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
      {scrapeFeedback && <div className="rounded-xl border border-amber-500/25 bg-amber-500/10 px-4 py-3 text-xs text-amber-200">{scrapeFeedback}</div>}

      <TodayActions />

      <SetupSteps />
      {readiness && !readiness.ready && <Link href="/onboarding" className="block rounded-2xl border border-amber-500/25 bg-amber-500/5 p-4 hover:border-amber-400/50">
        <div className="flex items-center justify-between gap-4"><div><div className="text-sm font-semibold text-white">{t("İş eşleşmelerini iyileştirmek için profili tamamla")}</div><div className="mt-1 text-xs text-slate-400">{t("Eksik:")}{readiness.missing.join(" · ")}</div></div><div className="min-w-16 text-right"><div className="font-mono text-lg font-bold text-amber-300">{readiness.completion_percent}%</div><div className="text-xs text-slate-400">{t("tamamlandı")}</div></div></div>
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-800"><div className="h-full rounded-full bg-amber-400" style={{ width: `${readiness.completion_percent}%` }} /></div>
      </Link>}

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Link href="/jobs?scope=current" aria-label={t("Toplam ilan listesini aç")} className="group block p-5 rounded-2xl bg-[#0e1524] border border-slate-800/80 transition hover:border-slate-500 hover:bg-slate-800/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">{t("Toplam İlan")}</span>
            <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
              <Briefcase className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-white mt-3">{currentFeedJobs.length}</div>
          <div className="text-xs text-slate-400 mt-1">{t("Apify kaynakları, RemoteOK ve Arbeitnow")}</div>
          <div className="mt-3 text-xs font-medium text-slate-300 opacity-70 group-hover:opacity-100">{t("İlanları görüntüle")} <ArrowRight className="inline h-3 w-3" /></div>
        </Link>

        <Link href="/jobs?scope=current&minMatch=70" aria-label={t("Yüksek tahmini profil uyumu olan ilanları aç")} className="group block p-5 rounded-2xl bg-[#0e1524] border border-slate-800/80 transition hover:border-emerald-500/40 hover:bg-slate-800/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">{t("Yüksek tahmini profil uyumu (%70+)")}</span>
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-emerald-400 mt-3">{highMatchCount}</div>
          <div className="text-xs text-emerald-500/80 mt-1">{t("Daha yüksek tahmini profil uyumu")}</div>
          <div className="mt-3 text-xs font-medium text-emerald-300 opacity-70 group-hover:opacity-100">{t("Eşleşen ilanları gör")} <ArrowRight className="inline h-3 w-3" /></div>
        </Link>

        <Link href="/jobs?scope=current&ghost=1" aria-label={t("Hayalet ilan risk listesini aç")} className="group block p-5 rounded-2xl bg-[#0e1524] border border-slate-800/80 transition hover:border-rose-500/40 hover:bg-slate-800/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">{t("Hayalet İlan Riski (Ghost)")}</span>
            <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400">
              <ShieldAlert className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-rose-400 mt-3">{ghostCount}</div>
          <div className="text-xs text-rose-500/80 mt-1">{t("Stagnant & Şüpheli İlan")}</div>
          <div className="mt-3 text-xs font-medium text-rose-300 opacity-70 group-hover:opacity-100">{t("Riskli ilanları incele")} <ArrowRight className="inline h-3 w-3" /></div>
        </Link>

        <button type="button" onClick={showInterviewResponses} disabled={responsesLoading} aria-label={t("Mülakat dönüşlerini görüntüle")} className="group block w-full text-left p-5 rounded-2xl bg-[#0e1524] border border-slate-800/80 transition hover:border-indigo-500/40 hover:bg-slate-800/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 disabled:opacity-70">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">{t("Mülakat Dönüş Oranı")}</span>
            <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-indigo-400 mt-3">{funnel.interview_rate || "—"}</div>
          <div className="text-xs text-indigo-400/80 mt-1">{t("Gerçek başvuru sonuçları")}</div>
          <div className="mt-3 text-xs font-medium text-indigo-300 opacity-70 group-hover:opacity-100">{responsesLoading ? t("Yükleniyor…") : t("Dönüş yapan işverenleri gör")} <ArrowRight className="inline h-3 w-3" /></div>
        </button>
      </div>

      {interviewResponses !== null && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setInterviewResponses(null); }}>
        <section role="dialog" aria-modal="true" aria-labelledby="interview-responses-title" className="max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-slate-700 bg-[#151719] p-5 shadow-2xl">
          <div className="flex items-start justify-between gap-3"><div><h2 id="interview-responses-title" className="text-lg font-semibold text-white">{t("Mülakat dönüşü alınan işverenler")}</h2><p className="mt-1 text-xs text-slate-400">{t("Yalnızca gönderimi doğrulanmış ve mülakat/teklif aşamasındaki başvurular.")}</p></div><button type="button" onClick={() => setInterviewResponses(null)} aria-label={t("Kapat")} className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white"><X size={18} /></button></div>
          {interviewResponses.length ? <ul className="mt-4 space-y-2">{interviewResponses.map((item) => <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/70 p-3"><div><p className="font-medium text-white">{item.company}</p><p className="mt-0.5 text-sm text-slate-300">{item.title}</p><p className="mt-1 text-xs text-slate-400">{item.platform} · {item.applied_at ? new Date(item.applied_at).toLocaleDateString() : ""}</p></div><span className="rounded-full bg-indigo-500/10 px-3 py-1 text-xs font-medium text-indigo-300">{item.status}</span></li>)}</ul> : <div className="mt-5 rounded-xl border border-slate-800 bg-slate-900/60 p-5 text-sm text-slate-300">{t("Henüz doğrulanmış bir mülakat/teklif dönüşü bulunmuyor.")}<p className="mt-2 text-xs text-slate-400">{t("Bir başvuruyu Mülakat olarak işaretlemek tek başına gerçek yanıt sayılmaz; başvurunun dış platforma gönderimi doğrulanmış olmalıdır.")}</p></div>}
        </section>
      </div>}

      {/* Platform Account Safety Bars */}
      <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-white">{t("Hesap Sağlığı ve Günlük Güvenlik Kotaları")}</h2>
            <p className="text-xs text-slate-400">{t("Shadowban koruması ve insan davranışı simülasyonu")}</p>
          </div>
          <Link href="/safety" className="text-xs text-blue-400 hover:underline">{t("Güvenlik ayrıntıları →")}</Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 2xl:grid-cols-4 gap-4">
          {Object.entries(health).map(([key, val]: any) => (
            <div key={key} className="min-w-0 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <span className="min-w-0 break-words text-sm font-semibold text-slate-200">{val.platform}</span>
                <span className={`inline-flex shrink-0 whitespace-nowrap rounded-full border px-2.5 py-1.5 font-mono text-xs leading-none ${val.is_safe ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400' : 'border-rose-500/20 bg-rose-500/10 text-rose-400'}`}>
                  {val.remaining} / {val.daily_limit} {t("Kalan")}</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800" role="progressbar" aria-label={`${val.platform} ${t("kalan günlük kota")}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.max(0, Math.min(100, Number(val.health_pct) || 0))}>
                <div
                  className={`h-full rounded-full transition-all ${val.is_safe ? 'bg-emerald-400' : 'bg-rose-400'}`}
                  style={{ width: `${Math.max(0, Math.min(100, Number(val.health_pct) || 0))}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Feed */}
      <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-sm font-semibold text-white">{t("Öne Çıkan Fırsatlar & Algoritmik Skorlar")}</h2>
            <p className="text-xs text-slate-400">{t("Tahmini profil uyumu, ilan riskleri ve kırmızı çizgiler")}</p>
          </div>
          <Link href="/jobs" className="text-xs text-blue-400 hover:underline">{t("Tüm İlanları Gör")} ({currentFeedJobs.length}) →</Link>
        </div>

        <div className="space-y-3">
          {currentFeedJobs.slice(0, 5).map((job) => (
            <div
              key={job.id}
              className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/80 hover:border-slate-700 transition flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="space-y-1.5 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-bold text-white hover:text-blue-400 transition">{job.title}</span>
                  <span className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded border border-slate-700">
                    {job.company}
                  </span>
                  <span className="text-xs bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded border border-blue-500/20 uppercase font-mono">
                    {job.platform}
                  </span>
                  {job.ghost_score >= 50 && (
                      <span className="text-xs bg-rose-500/10 text-rose-400 border border-rose-500/30 px-2 py-0.5 rounded font-semibold flex items-center gap-1">
                      <ShieldAlert className="w-3 h-3" /> {t("Hayalet İlan")} ({job.ghost_score}%)
                    </span>
                  )}
                </div>
                <div className="text-xs text-slate-400 flex flex-wrap gap-x-4 gap-y-1">
                  <span>{job.location}</span>
                  <span>{job.salary_range}</span>
                  <span>{job.posted_date}</span>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <div className="text-right">
                  <div className="text-xs font-bold text-emerald-400">≈ %{job.match_score ?? "—"} {t("Tahmini uyum")}</div>
                  <div className="text-xs text-slate-400">{job.match_tier || t("Skorlanmadı")}</div>
                </div>
                <Link
                  href={`/kanban`}
                  className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition"
                >
                  {t("Apply Paketi Hazırla")}
                </Link>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Realtime Agent Terminal Console (SSE / Log Streaming) */}
      <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-3">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <h2 className="text-sm font-semibold text-white font-mono">{t("Live Agent Execution Console (Streaming Logs)")}</h2>
          </div>
          <span className="text-xs text-slate-400 font-mono bg-slate-900 border border-slate-800 px-2 py-0.5 rounded">
            {t("FastAPI Streamer • Active")}
          </span>
        </div>

        <div className="p-4 rounded-xl bg-black/80 border border-slate-800 font-mono text-xs text-slate-300 space-y-1.5 h-44 overflow-y-auto">
          <div className="text-emerald-400">{t("[SYSTEM]")}{t("API bağlantısı")} {loading ? t("kontrol ediliyor") : t("aktif")}.</div>
          <div className="text-blue-400">{t("[SCRAPER]")}{t("Güncel ilan havuzu")}{t(":")}{currentFeedJobs.length} {t("kayıt")}.</div>
          <div className="text-indigo-400">{t("[RANKING]")}{t("Profil eşleşmesi")}{t(":")}{highMatchCount} {t("yüksek uyumlu kayıt")}.</div>
          <div className="text-amber-400">{t("[SOURCES]")}{Object.keys(health).length} {t("kaynak yapılandırması yüklendi")}.</div>
          {!jobs.length && <div className="text-slate-400">{t("[SCRAPER]")}{t("Henüz canlı tarama sonucu yok. Kaynak ayarlarından Apify bilgilerini ekleyin.")}</div>}
        </div>
      </div>
    </div>
  );
}
