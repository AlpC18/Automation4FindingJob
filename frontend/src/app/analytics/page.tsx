"use client";
import { notify } from "@/lib/notify";

import { useEffect, useState } from "react";
import {
  BarChart3,
  TrendingUp,
  Clock,
  Layers,
  Calendar,
  Sparkles,
  History
} from "lucide-react";
import Link from "next/link";
import { fetchFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

export default function AnalyticsPage() {
  const { translate: t } = useLanguage();
  const [analytics, setAnalytics] = useState<any>(null);
  const [followUps, setFollowUps] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [revisions, setRevisions] = useState<any[]>([]);
  const [revisionCompare, setRevisionCompare] = useState<any>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [aRes, fRes, rRes] = await Promise.all([
          fetchFromApi("/outcome/analytics").catch(() => { notify(t("Veriler yüklenemedi. Sayfayı yenileyip tekrar dene.")); return null; }),
          fetchFromApi("/outcome/follow_ups").catch(() => ({ follow_ups: [] })),
          fetchFromApi("/setup/profile/revisions?limit=8").catch(() => ({ revisions: [] }))
        ]);
        setAnalytics(aRes);
        setFollowUps(fRes.follow_ups || []);
        const loadedRevisions = rRes.revisions || [];
        setRevisions(loadedRevisions);
        if (loadedRevisions.length >= 2) {
          setRevisionCompare(await fetchFromApi(`/setup/profile/revisions/compare?from_version=${loadedRevisions[1].version}&to_version=${loadedRevisions[0].version}`).catch(() => null));
        }
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return <div className="p-8 text-center text-slate-400">{t("Analitik yükleniyor...")}</div>;
  }

  const stages = analytics?.funnel_stages || [];
  const platforms = analytics?.platform_performance || [];
  const rolePerformance = analytics?.role_performance || [];
  const profilePerformance = analytics?.profile_version_performance || [];
  const observedInsights = analytics?.observed_insights || {};

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <BarChart3 className="w-6 h-6 text-blue-500" />
          {t("Gerçek başvuru analitiği")}
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          {t("Kaynak, hedef rol ve CV/profil sürümüne göre ölçülen başvuru sonuçları.")}
        </p>
      </div>

      {/* Top Conversion Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-5 rounded-2xl bg-[#0e1524] border border-slate-800">
          <div className="text-xs text-slate-400">{t("Doğrulanmış toplam başvuru")}</div>
          <div className="text-2xl font-bold text-white mt-1">{analytics?.applied_count ?? 0}</div>
          <div className="text-xs text-emerald-400 mt-1">{t("Yalnızca dış gönderimi doğrulanmış")}</div>
        </div>

        <div className="p-5 rounded-2xl bg-[#0e1524] border border-slate-800">
          <div className="text-xs text-slate-400">{t("Mülakat aşamasına geçenler")}</div>
          <div className="text-2xl font-bold text-indigo-400 mt-1">{analytics?.interview_count ?? 0}</div>
          <div className="text-xs text-indigo-400/80 mt-1">{t("Mülakat oranı:")} {analytics?.interview_rate ?? "0%"} · {analytics?.rejected_count ?? 0} {t("ret")} · {analytics?.awaiting_response_count ?? 0} {t("yanıt bekliyor")}</div>
        </div>

        <div className="p-5 rounded-2xl bg-[#0e1524] border border-slate-800">
          <div className="text-xs text-slate-400">{t("Bekleyen takip hatırlatmaları")}</div>
          <div className="text-2xl font-bold text-amber-400 mt-1">{followUps.length}</div>
          <div className="text-xs text-amber-400/80 mt-1">{t("7. ve 14. gün otomasyon kuyruğu")}</div>
        </div>
      </div>

      {/* Funnel Visualizer */}
      <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
        <h2 className="text-sm font-semibold text-white flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-blue-400" /> {t("Başvuru dönüşüm hunisi")}
        </h2>
        <div className="space-y-3">
          {stages.map((stage: any) => (
            <div key={stage.stage} className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="font-semibold text-slate-200">{t(stage.stage)}</span>
                <span className="text-slate-400 font-mono">{stage.count} {t("İlan (")}{stage.percentage_of_total}%)</span>
              </div>
              <div className="w-full h-2.5 bg-slate-900 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-600 to-indigo-500 rounded-full transition-all duration-500"
                  style={{ width: `${Math.max(5, stage.percentage_of_total)}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Platform and role outcome grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Platform Breakdown */}
        <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Layers className="w-4 h-4 text-emerald-400" /> {t("Platform sonuçları")}
          </h2>
          <div className="space-y-3">
            {platforms.map((p: any) => (
              <div key={p.platform} className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 flex justify-between items-center text-xs">
                <div>
                  <div className="font-bold text-white">{p.platform}</div>
                  <div className="text-xs text-slate-400">
                    {p.total_scraped} {t("bulunan ilan ·")} {p.applied} {t("doğrulanmış başvuru ·")} {p.interviews} {t("mülakat")} · {p.rejected ?? 0} {t("ret")} · {p.awaiting_response ?? 0} {t("yanıt bekliyor")}</div>
                </div>
                <div className="text-right">
                  <div className="font-bold text-emerald-400 font-mono">{p.applied > 0 ? `%${p.conversion_rate}` : "—"}</div>
                  <div className="text-xs text-slate-400">{p.insight_eligible ? t("mülakat / doğrulanmış başvuru") : t("Örneklem küçük; performans yorumu yapılmıyor.")}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Actual role attribution; no fabricated sample experiment values. */}
        <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-400" /> {t("Role göre gerçek başvuru sonuçları")}
          </h2>
          {rolePerformance.length === 0 ? <p className="text-xs text-slate-400">{t("Başvurularına taslak hazırla ve sonuçlarını güncelle; rol bazlı dönüşler burada birikecek.")}</p> : <div className="space-y-2">{rolePerformance.map((item: any) => <div key={item.target_role} className="rounded-xl border border-slate-800 bg-slate-900/60 p-3 text-xs"><div className="font-semibold text-white">{item.target_role}</div><div className="mt-1 flex justify-between text-slate-400"><span>{item.applications} {t("doğrulanmış başvuru ·")} {item.interviews} {t("mülakat ·")} {item.offers} {t("teklif")} · {item.rejected ?? 0} {t("ret")} · {item.awaiting_response ?? 0} {t("yanıt bekliyor")}</span><span className="font-mono text-indigo-300">%{item.interview_rate}</span></div><div className="mt-1 text-xs text-slate-400">{item.insight_eligible ? t("Karşılaştırmaya dahil (en az 3 doğrulanmış başvuru).") : t("Örneklem küçük; performans yorumu yapılmıyor.")}</div></div>)}</div>}
        </div>

      </div>

      <section className="rounded-2xl border border-indigo-500/20 bg-indigo-500/[0.04] p-5">
        <h2 className="text-sm font-semibold text-white">{t("Gerçek veriden gözlenen içgörü")}</h2>
        <p className="mt-1 text-xs text-slate-400">{t("Hangi rol ve kaynak daha çok geri dönüş sağlıyor? Sonuçları Kanban panelinde Başvuruldu, Mülakat, Teklif veya Ret olarak işaretledikçe burası güncellenir.")} <Link href="/kanban" className="font-semibold text-indigo-300 hover:text-white">{t("Sonuç kaydet")} →</Link></p>
        {observedInsights.best_observed_role || observedInsights.best_observed_source ? <div className="mt-2 space-y-1 text-xs text-slate-300">{observedInsights.best_observed_role && <p>{t("Bu hesaptaki gözlenen en yüksek rol dönüşü:")} <strong>{observedInsights.best_observed_role.target_role}</strong> · %{observedInsights.best_observed_role.interview_rate} ({observedInsights.best_observed_role.applications} {t("doğrulanmış başvuru")}).</p>}{observedInsights.best_observed_source && <p>{t("Kaynak bazında gözlenen en yüksek dönüş:")} <strong>{observedInsights.best_observed_source.platform}</strong> · %{observedInsights.best_observed_source.conversion_rate} ({observedInsights.best_observed_source.verified_application_sample} {t("doğrulanmış başvuru")}).</p>}</div> : observedInsights.has_verified_interviews ? <p className="mt-2 text-xs text-slate-400">{t("Henüz hiçbir rol/kaynak grubunda en az 3 başvuru ve en az bir doğrulanmış dönüş koşulu sağlanmadı.")}</p> : (analytics?.applied_count || 0) > 0 ? <p className="mt-2 text-xs text-slate-400">{t("Şu ana kadar doğrulanmış başvurulardan kaydedilmiş mülakat veya teklif dönüşü yok.")}</p> : <p className="mt-2 text-xs text-slate-400">{t("Henüz karşılaştırma için yeterli gerçek başvuru yok. Her rol/kaynak için en az 3 dış gönderimi doğrulanmış başvuru gerekir.")}</p>}
        <p className="mt-2 text-xs text-slate-400">{t("Yalnızca dış gönderimi doğrulanmış başvuru ve kaydedilmiş sonuçlar kullanılır. Bu geçmişe dayalı betimleyici karşılaştırmadır; gelecek sonucu tahmin etmez.")}</p>
      </section>

      <section className="rounded-2xl border border-slate-800 bg-[#0e1524] p-6">
        <h2 className="text-sm font-semibold text-white">{t("CV/profil sürümünün etkisi")}</h2>
        <p className="mt-1 text-xs text-slate-400">{t("Başvuru taslağı hazırlanırken kullanılan profil sürümüne göre gerçek mülakat sonuçları.")}</p>
        {profilePerformance.length === 0 ? <p className="mt-4 text-xs text-slate-400">{t("Henüz sürüm bazlı başvuru verisi yok.")}</p> : <div className="mt-4 grid gap-3 md:grid-cols-2">{profilePerformance.map((item: any) => <div key={item.version} className="rounded-xl border border-slate-800 bg-slate-900/60 p-3 text-xs"><div className="font-semibold text-white">{t("Profil v")}{item.version} · {item.target_role || t("Rol belirtilmemiş")}</div><div className="mt-1 text-slate-400">{item.applications} {t("başvuru ·")} {item.interviews || 0} {t("mülakat")}</div></div>)}</div>}
        <p className="mt-4 text-xs text-slate-400">{analytics?.analytics_note ? t(analytics.analytics_note) : null}</p>
      </section>

      <section className="rounded-2xl border border-slate-800 bg-[#0e1524] p-6">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-white"><History className="h-4 w-4 text-emerald-300" />{t("Profil sürüm geçmişi")}</h2>
        <p className="mt-1 text-xs text-slate-400">{t("CV veya profilini onayladıkça başvurularda kullanılan sürümleri karşılaştırabilirsin.")}</p>
        {revisions.length === 0 ? <p className="mt-4 text-xs text-slate-400">{t("Henüz profil sürümü oluşmadı.")}</p> : <div className="mt-4 grid gap-2 md:grid-cols-3">{revisions.slice(0, 6).map((revision) => <div key={revision.version} className="rounded-xl border border-slate-800 bg-slate-900/60 p-3 text-xs"><div className="font-semibold text-white">{t("Profil v")}{revision.version}</div><div className="mt-1 text-slate-400">{revision.target_role || t("Rol belirtilmemiş")}</div><div className="mt-1 text-xs text-slate-400">{revision.created_at || ""}</div></div>)}</div>}
        {revisionCompare && <div className="mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.04] p-4"><div className="text-xs font-semibold text-emerald-300">{t("Son iki sürüm arasındaki değişiklikler")}: {revisionCompare.changed_count}</div><div className="mt-3 space-y-2">{(revisionCompare.changes || []).filter((item: any) => item.changed).map((item: any) => <div key={item.field} className="grid gap-1 text-xs md:grid-cols-[150px_1fr_1fr]"><strong className="text-slate-200">{item.field}</strong><span className="text-rose-300">{formatRevisionValue(item.before)}</span><span className="text-emerald-300">{formatRevisionValue(item.after)}</span></div>)}</div></div>}
      </section>

      {/* Follow-up Queue */}
      <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
        <h2 className="text-sm font-semibold text-white flex items-center gap-2">
          <Clock className="w-4 h-4 text-amber-400" /> {t("Zamanlanmış Takip Otomasyonu (Day 7 / Day 14 Follow-ups)")}</h2>
        {followUps.length === 0 ? (
          <div className="p-6 text-center text-xs text-slate-400 bg-slate-900/40 rounded-xl">
            {t("Henüz bekleyen takip hatırlatıcısı yok. Bir ilana başvuru onaylandığında otomatik olarak 7. ve 14. gün kuyruğuna eklenir.")}</div>
        ) : (
          <div className="space-y-3">
            {followUps.map((f: any) => (
              <div key={f.id} className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col md:flex-row justify-between items-start md:items-center gap-3 text-xs">
                <div className="space-y-1">
                  <div className="font-bold text-white flex items-center gap-2">
                    <span>{f.title} @ {f.company}</span>
                    <span className="text-xs bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded font-mono">
                      {t("Gün")}{f.due_day} {t("Hatırlatması")}</span>
                  </div>
                  <div className="text-xs text-slate-400 flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5" /> {t("Planlanan Tarih:")}{f.scheduled_date}
                  </div>
                </div>
                <details className="max-w-xl text-xs">
                  <summary className="cursor-pointer rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 font-medium text-slate-200">{t("Taslağı İncele")}</summary>
                  <pre className="mt-2 whitespace-pre-wrap rounded-lg border border-slate-800 bg-slate-900/60 p-3 font-sans leading-relaxed text-slate-300">{f.draft_email}</pre>
                </details>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function formatRevisionValue(value: unknown): string {
  if (value === undefined || value === null || value === "") return "—";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
