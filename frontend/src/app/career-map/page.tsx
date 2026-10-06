"use client";
import { useLanguage } from "@/lib/i18n";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, Check, Compass, Copy, Download, Layers3, RefreshCw, Rocket, Shuffle, Target, Zap } from "lucide-react";
import { fetchFromApi } from "@/lib/api";
import { CareerEmpty, CareerHeading, CareerLinks, CareerMetric, CareerNotice, downloadText } from "@/components/CareerWorkspace";

type Track = { title: string; track_type: string; match_reason: string; readiness_score: number };
type Discovery = { candidate_current_role: string; detected_competency_domains: string[]; core_progression: Track[]; lateral_pivots: Track[]; emerging_frontiers: Track[]; recommended_search_queries: string[] };
const tracks = [
  { id: "all", label: "Tüm yollar", icon: Compass },
  { id: "core_progression", label: "Mevcut alanda ilerle", icon: Rocket },
  { id: "lateral_pivot", label: "Yeni alana geç", icon: Shuffle },
  { id: "emerging_frontier", label: "Yeni uzmanlıklar", icon: Zap },
];
const domains: Record<string, string> = { backend_engineering: "Backend geliştirme", machine_learning: "Yapay zekâ ve makine öğrenmesi", fullstack: "Fullstack geliştirme", automation_devops: "Bulut ve DevOps" };

export default function CareerMapPage() {
  const { translate: t } = useLanguage();
  const [data, setData] = useState<Discovery | null>(null);
  const [profile, setProfile] = useState<{ target_role?: string; skills?: string[]; years_of_experience?: number }>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("recommended");
  const [compare, setCompare] = useState<string[]>([]);
  const [roadmap, setRoadmap] = useState<{ pivot_role: string; action_plan_markdown: string } | null>(null);
  const [planning, setPlanning] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const result = await fetchFromApi("/setup/profile");
      setProfile(result.profile);
      if (result.profile.target_role && result.profile.skills?.length) {
        setData(await fetchFromApi("/setup/career_discovery", { method: "POST" }));
      } else { setData(null); }
      setCompare([]);
    } catch { setError(t("Kariyer bilgileri yüklenemedi. Yenile düğmesiyle tekrar deneyebilirsin.")); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const allTracks = useMemo(() => [...(data?.core_progression || []), ...(data?.lateral_pivots || []), ...(data?.emerging_frontiers || [])], [data]);
  const visibleTracks = useMemo(() => allTracks.filter(item => filter === "all" || item.track_type === filter).sort((a, b) => sort === "name" ? a.title.localeCompare(b.title, "tr") : b.readiness_score - a.readiness_score), [allTracks, filter, sort]);
  const selected = allTracks.filter(item => compare.includes(item.title));

  async function generateRoadmap(title: string) {
    setPlanning(title); setError(""); setRoadmap(null);
    try { setRoadmap(await fetchFromApi("/setup/career_discovery/roadmap", { method: "POST", body: JSON.stringify({ target_pivot: title }) })); }
    catch { setError(t("Geçiş planı alınamadı. Yapay zekâ ayarlarını kontrol edip tekrar dene.")); }
    finally { setPlanning(""); }
  }

  async function copyQuery(query: string) {
    try { await navigator.clipboard.writeText(query); setNotice(t("Search query copied: {query}", { query })); }
    catch { setError(t("Panoya erişilemedi. Arama ifadesini seçerek kopyalayabilirsin.")); }
  }

  return <div className="mx-auto max-w-6xl space-y-6">
    <CareerHeading eyebrow={t("KARİYERİNİ ŞEKİLLENDİR / 01")} title={t("Bir sonraki adımın.")} description={t("Mevcut becerilerini farklı kariyer yollarıyla buluştur. Seçeneklerini karşılaştır, odaklanacağın rol için bir geçiş planı çıkar.")} action={<button className="career-action secondary-button border" disabled={loading || !!planning} onClick={load}><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />{t("Yenile")}</button>} />
    {error && <CareerNotice error>{error}</CareerNotice>}
    {notice && <CareerNotice>{notice}</CareerNotice>}
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <CareerMetric label={t("Keşfedilen yollar")} value={loading ? "…" : allTracks.length} detail={t("Profiline göre oluşturulan seçenekler")} icon={Compass} />
      <CareerMetric label={t("Yetkinlik alanları")} value={loading ? "…" : data?.detected_competency_domains.length || 0} detail={t("Kayıtlı becerilerinden tespit edilir")} icon={Layers3} />
      <CareerMetric label={t("Kayıtlı beceriler")} value={loading ? "…" : profile.skills?.length || 0} detail={t("Kariyer keşfinin başlangıç noktası")} icon={Zap} />
      <CareerMetric label={t("Deneyim")} value={loading ? "…" : `${profile.years_of_experience || 0} yıl`} detail={t("Profilinde belirttiğin deneyim süresi")} icon={Target} />
    </div>
    {loading ? <CareerEmpty title={t("Kariyer haritan hazırlanıyor")}>{t("Profil ve beceri bilgilerin okunuyor.")}</CareerEmpty> : !data ? <CareerEmpty title={t("Önce yönünü belirleyelim")} href="/setup" action="Profilimi tamamla">{t("Hedef rolünü ve becerilerini profiline eklediğinde burada kariyer seçeneklerini görebilirsin.")}</CareerEmpty> : <>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
        <section className="career-card">
          <div className="career-card-header"><h3 className="career-card-title">{t("Başlangıç noktan")}</h3><Link href="/preferences" className="muted text-xs underline underline-offset-4">{t("Tercihleri düzenle")}</Link></div>
          <p className="text-xl font-semibold">{data.candidate_current_role}</p>
          <div className="mt-4 flex flex-wrap gap-2">{profile.skills?.map(skill => <span key={skill} className="career-pill">{skill}</span>)}</div>
          <div className="mt-5 flex flex-wrap gap-2">{data.detected_competency_domains.map(domain => <span key={domain} className="summary-tag rounded-lg px-3 py-2 text-xs">{t(domains[domain] || domain)}</span>)}</div>
        </section>
        <section className="career-card"><div className="brand-mark mb-4 inline-flex rounded-xl p-2.5"><Target className="h-5 w-5" /></div><h3 className="career-card-title">{t("İki yolu yan yana gör")}</h3><p className="muted mt-2 text-xs leading-6">{t("Kartlardaki karşılaştır düğmesiyle en fazla iki rol seç. Gerekçelerini ve öneri puanlarını birlikte değerlendir.")}</p><p className="mt-4 text-xs font-semibold">{compare.length} {t("/ 2 rol seçildi")}</p></section>
      </div>
      <section className="space-y-4" aria-label={t("Kariyer seçenekleri")}>
        <div className="flex flex-wrap items-center justify-between gap-4"><h3 className="text-lg font-semibold">{t("Keşfedilecek yollar")}</h3><label className="muted flex items-center gap-2 text-xs">{t("Sıralama")}<select className="field-input rounded-lg border p-2" value={sort} onChange={e => setSort(e.target.value)}><option value="recommended">{t("Önerilen sıra")}</option><option value="name">{t("Rol adı")}</option></select></label></div>
        <div className="career-tabs">{tracks.map(({ id, label, icon: Icon }) => <button key={id} aria-pressed={filter === id} onClick={() => setFilter(id)} className="inline-flex items-center gap-2"><Icon className="h-3.5 w-3.5" />{t(label)}</button>)}</div>
        <p className="muted text-xs leading-5">{t("Puanlar mevcut kural tabanlı motorun önerileridir; işe alınma olasılığı veya doğrulanmış yetkinlik ölçümü değildir.")}</p>
        <div className="grid gap-4 md:grid-cols-2">{visibleTracks.map(track => {
          const type = tracks.find(item => item.id === track.track_type) || tracks[0];
          const Icon = type.icon;
          const picked = compare.includes(track.title);
          return <article key={track.title} className="career-card flex flex-col gap-4">
            <div className="flex items-center justify-between gap-3"><span className="brand-mark rounded-xl p-2.5"><Icon className="h-5 w-5" /></span><span className="career-pill">{t(type.label)}</span></div>
            <div className="flex-1"><h4 className="text-base font-semibold">{track.title}</h4><p className="muted mt-2 text-xs leading-6">{track.match_reason}</p></div>
            
            <div className="flex flex-wrap gap-2"><button onClick={() => generateRoadmap(track.title)} disabled={!!planning} className="career-action primary-button">{planning === track.title ? t("Plan hazırlanıyor…") : t("60 günlük plan")}<ArrowRight className="h-3.5 w-3.5" /></button><button aria-pressed={picked} disabled={!picked && compare.length >= 2} onClick={() => setCompare(current => picked ? current.filter(title => title !== track.title) : [...current, track.title])} className="career-action secondary-button border">{picked && <Check className="h-3.5 w-3.5" />}{picked ? t("Seçildi") : t("Karşılaştır")}</button></div>
          </article>;
        })}</div>
        {!visibleTracks.length && <CareerEmpty title={t("Bu türde öneri yok")}>{t("Diğer yolları inceleyebilir veya profilindeki becerileri güncelleyebilirsin.")}</CareerEmpty>}
      </section>
      {selected.length > 0 && <section className="career-card" aria-label={t("Rol karşılaştırması")}><div className="career-card-header"><h3 className="career-card-title">{t("Rol karşılaştırması")}</h3><button onClick={() => setCompare([])} className="muted text-xs underline">{t("Seçimi temizle")}</button></div><div className="grid gap-4 sm:grid-cols-2">{selected.map(track => <div className="career-feature" key={track.title}><h4 className="text-sm font-semibold">{track.title}</h4><p className="muted text-xs leading-6">{track.match_reason}</p></div>)}</div></section>}
      <section className="career-card" aria-live="polite"><div className="career-card-header"><h3 className="career-card-title">{t("Geçiş planın")}</h3>{roadmap && <button onClick={() => downloadText(roadmap.action_plan_markdown, "kariyer-plani.md")} className="career-action secondary-button border"><Download className="h-4 w-4" />{t("İndir")}</button>}</div>{planning ? <p className="muted text-sm">{planning} {t("için plan hazırlanıyor…")}</p> : roadmap ? <><p className="mb-4 font-semibold">{roadmap.pivot_role}</p><div className="whitespace-pre-wrap break-words text-sm leading-7 muted">{roadmap.action_plan_markdown}</div><Link href="/upskill" className="career-action primary-button mt-5">{t("Öğrenme planına geç")}<ArrowRight className="h-4 w-4" /></Link></> : <p className="muted text-sm leading-6">{t("Bir rolün “60 günlük plan” düğmesine basarak güçlü yönlerini, öğrenmen gereken becerileri ve proje önerilerini burada incele.")}</p>}</section>
      <section className="career-card"><div className="career-card-header"><h3 className="career-card-title">{t("İlan aramalarına taşı")}</h3><Link className="text-xs underline underline-offset-4" href="/jobs">{t("İlanlara git")}</Link></div><div className="grid gap-2 sm:grid-cols-2">{data.recommended_search_queries.map(query => <button key={query} onClick={() => copyQuery(query)} className="career-feature flex items-center justify-between gap-3 text-left text-xs"><span>{query}</span><Copy className="h-3.5 w-3.5 shrink-0 muted" /></button>)}</div><p className="muted mt-3 text-xs">{t("Bir ifadeye tıkla, kopyala ve ilan aramasında kullan.")}</p></section>
    </>}
    <CareerLinks current="map" />
  </div>;
}
