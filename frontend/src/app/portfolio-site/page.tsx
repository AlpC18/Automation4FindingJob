"use client";
import { useLanguage } from "@/lib/i18n";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, BriefcaseBusiness, CheckCircle2, Circle, Download, FolderOpen, Globe, Layers3, Monitor, Package, Plus, RefreshCw, Smartphone, Sparkles, Tablet } from "lucide-react";
import { fetchFromApi, requestFromApi } from "@/lib/api";
import { CareerEmpty, CareerHeading, CareerLinks, CareerMetric, CareerNotice, downloadText } from "@/components/CareerWorkspace";

type Profile = { full_name?: string; target_role?: string; summary?: string; raw_cv_text?: string; email?: string; skills?: string[]; experience?: unknown[] };
type Project = { id: string; title: string; content: string; metrics: string; tech_stack: string[] };
const previewModes = [{ id: "desktop", label: "Masaüstü", width: "100%", icon: Monitor }, { id: "tablet", label: "Tablet", width: "768px", icon: Tablet }, { id: "mobile", label: "Mobil", width: "375px", icon: Smartphone }];

export default function PortfolioSitePage() {
  const { translate: t } = useLanguage();
  const [profile, setProfile] = useState<Profile>({});
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [packaging, setPackaging] = useState(false);
  const [portfolio, setPortfolio] = useState<{ html_content: string; size_bytes: number } | null>(null);
  const [headline, setHeadline] = useState("");
  const [generatedHeadline, setGeneratedHeadline] = useState("");
  const [dirty, setDirty] = useState(false);
  const [previewMode, setPreviewMode] = useState("desktop");
  const [showProjectForm, setShowProjectForm] = useState(false);
  const [draft, setDraft] = useState({ title: "", content: "", tech_stack: "", metrics: "" });
  const [savingProject, setSavingProject] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [person, work] = await Promise.all([fetchFromApi<{ profile: Profile }>("/setup/profile"), fetchFromApi<{ projects: Project[] }>("/setup/rag_projects")]);
      setProfile(person.profile); setProjects(work.projects);
    } catch { setError(t("Portföy bilgileri yüklenemedi. Yenilemeyi deneyebilirsin.")); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const checks = [
    { label: "Ad ve hedef rol", complete: !!(profile.full_name && profile.target_role) },
    { label: "Kısa profesyonel özet", complete: !!(headline.trim() || profile.summary || profile.raw_cv_text) },
    { label: "Beceriler", complete: !!profile.skills?.length },
    { label: "İş deneyimi", complete: !!profile.experience?.length },
    { label: "En az bir proje", complete: projects.length > 0 },
    { label: "İletişim e-postası", complete: !!profile.email },
  ];
  const readiness = Math.round(checks.filter(check => check.complete).length / checks.length * 100);
  const canGenerate = !!(profile.full_name && profile.target_role) && !loading;
  const needsRefresh = dirty || generatedHeadline !== headline;
  const view = previewModes.find(mode => mode.id === previewMode)!;

  async function generate() {
    setGenerating(true); setError(""); setNotice("");
    const submittedHeadline = headline;
    try {
      setPortfolio(await fetchFromApi("/setup/portfolio/generate", { method: "POST", body: JSON.stringify({ custom_headline: submittedHeadline }) }));
      setGeneratedHeadline(submittedHeadline); setDirty(false); setNotice(t("Portföy önizlemen oluşturuldu. Farklı ekranlarda kontrol edip indirebilirsin."));
    } catch { setError(t("Portföy oluşturulamadı. Tekrar dene.")); }
    finally { setGenerating(false); }
  }

  async function downloadPackage() {
    setPackaging(true); setError("");
    try {
      const response = await requestFromApi("/setup/portfolio/package", { method: "POST", body: JSON.stringify({ custom_headline: generatedHeadline }) });
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a"); anchor.href = url; anchor.download = "portfolio-site.zip"; anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { setError("Site paketi indirilemedi. Tekrar dene."); }
    finally { setPackaging(false); }
  }

  async function saveProject(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSavingProject(true); setError("");
    try {
      const result = await fetchFromApi<{ project: Project }>("/setup/rag_projects", { method: "POST", body: JSON.stringify({ ...draft, title: draft.title.trim(), content: draft.content.trim(), tech_stack: draft.tech_stack.split(",").map(skill => skill.trim()).filter(Boolean) }) });
      setProjects(current => [...current, result.project]); setDraft({ title: "", content: "", tech_stack: "", metrics: "" });
      setShowProjectForm(false); setDirty(true); setNotice(t("Projen kaydedildi. Siteye eklemek için önizlemeyi yeniden oluştur."));
    } catch { setError("Proje kaydedilemedi. Formdaki bilgiler korunuyor; tekrar deneyebilirsin."); }
    finally { setSavingProject(false); }
  }

  return <div className="mx-auto max-w-6xl space-y-6">
    <CareerHeading eyebrow={t("KARİYERİNİ ŞEKİLLENDİR / 03")} title={t("Çalışmaların senin adına konuşsun.")} description={t("Deneyimini, becerilerini ve projelerini tek bir portföyde topla. Önizle, düzenle ve paylaşmaya hazır site dosyanı indir.")} action={<button onClick={generate} disabled={!canGenerate || generating || savingProject || packaging} className="career-action primary-button"><Sparkles className={`h-4 w-4 ${generating ? "animate-pulse" : ""}`} />{generating ? t("Oluşturuluyor…") : portfolio ? t("Önizlemeyi güncelle") : t("Önizleme oluştur")}</button>} />
    {error && <CareerNotice error>{error} <button onClick={load} disabled={loading} className="ml-2 underline">{t("Yenile")}</button></CareerNotice>}{notice && <CareerNotice>{notice}</CareerNotice>}
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <CareerMetric label={t("İçerik hazırlığı")} value={loading ? "…" : `%${readiness}`} detail={t("Altı içerik alanının doluluk oranı")} icon={CheckCircle2} />
      <CareerMetric label={t("Proje vitrini")} value={loading ? "…" : projects.length} detail={t("Profilinde kayıtlı çalışmalar")} icon={FolderOpen} />
      <CareerMetric label={t("Beceri etiketleri")} value={loading ? "…" : profile.skills?.length || 0} detail={t("Portföyde görünür olacak beceriler")} icon={Layers3} />
      <CareerMetric label={t("Deneyimler")} value={loading ? "…" : profile.experience?.length || 0} detail={t("Deneyim zaman çizelgesindeki kayıtlar")} icon={BriefcaseBusiness} />
    </div>
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
      <section className="career-card space-y-5"><div className="career-card-header"><h3 className="career-card-title">{t("İlk izlenimini tasarla")}</h3><span className="career-pill">{t("Profilinden beslenir")}</span></div><div className="career-feature"><p className="text-xl font-semibold">{profile.full_name || t("Adını profiline ekle")}</p><p className="muted mt-2 text-sm">{profile.target_role || t("Hedef rolünü belirle")}</p><div className="mt-4 flex flex-wrap gap-2">{profile.skills?.slice(0, 8).map(skill => <span key={skill} className="career-pill">{skill}</span>)}</div></div>
        <div><label htmlFor="portfolio-headline" className="mb-2 block text-xs font-medium">{t("Portföy giriş metni")}</label><textarea id="portfolio-headline" rows={3} value={headline} disabled={generating || packaging} onChange={e => setHeadline(e.target.value)} placeholder={profile.summary || t("Kimin için, hangi problemi, nasıl çözdüğünü anlat.")} className="field-input w-full rounded-xl border p-3 text-sm" /><p className="muted mt-2 text-xs leading-5">{t("Boş bırakırsan profilindeki özet veya özgeçmiş metni kullanılır.")}</p></div><Link href="/setup" className="career-action secondary-button border">{t("Profil bilgilerini düzenle")}<ArrowUpRight className="h-4 w-4" /></Link>
      </section>
      <section className="career-card"><h3 className="career-card-title">{t("Yayına hazırlık")}</h3><div className="mt-4 career-meter"><span style={{ width: `${readiness}%` }} /></div><ul className="mt-5 space-y-4">{checks.map(check => <li key={check.label} className="flex items-center gap-2 text-xs">{check.complete ? <CheckCircle2 className="h-4 w-4 shrink-0 text-[var(--accent)]" /> : <Circle className="h-4 w-4 shrink-0 muted" />}<span className={check.complete ? "" : "muted"}>{t(check.label)}</span></li>)}</ul><p className="muted mt-5 text-xs leading-6">{t("Yalnızca sana ait ve paylaşmak istediğin bilgileri ekle. İndirdiğin dosya bu içerikleri içerir.")}</p></section>
    </div>
    <section className="space-y-4" id="project-showcase"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-lg font-semibold">{t("Proje vitrinin")}</h3><p className="muted mt-1 text-xs">{t("Çalışmanı, kullandığın araçları ve elde ettiğin sonucu anlat.")}</p></div><button onClick={() => setShowProjectForm(current => !current)} disabled={loading || generating || packaging || savingProject} className="career-action secondary-button border"><Plus className="h-4 w-4" />{showProjectForm ? "Formu kapat" : "Proje ekle"}</button></div>
      {showProjectForm && <form onSubmit={saveProject} className="career-card grid gap-4 sm:grid-cols-2"><label className="space-y-2 text-xs"><span>{t("Proje adı *")}</span><input required maxLength={160} value={draft.title} onChange={e => setDraft(current => ({ ...current, title: e.target.value }))} className="field-input w-full rounded-xl border p-3" /></label><label className="space-y-2 text-xs"><span>{t("Teknolojiler (virgülle ayır)")}</span><input value={draft.tech_stack} onChange={e => setDraft(current => ({ ...current, tech_stack: e.target.value }))} className="field-input w-full rounded-xl border p-3" /></label><label className="space-y-2 text-xs sm:col-span-2"><span>{t("Problem, katkın ve çözümün *")}</span><textarea required rows={3} value={draft.content} onChange={e => setDraft(current => ({ ...current, content: e.target.value }))} className="field-input w-full rounded-xl border p-3" /></label><label className="space-y-2 text-xs sm:col-span-2"><span>{t("Somut sonuç (varsa)")}</span><input value={draft.metrics} onChange={e => setDraft(current => ({ ...current, metrics: e.target.value }))} placeholder={t("Örn. rapor hazırlama süresi 2 saatten 20 dakikaya indi")} className="field-input w-full rounded-xl border p-3" /></label><button type="submit" disabled={savingProject || !draft.title.trim() || !draft.content.trim()} className="career-action primary-button sm:justify-self-start">{savingProject ? "Kaydediliyor…" : "Projeyi kaydet"}</button></form>}
      {projects.length ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{projects.map(project => <article key={project.id} className="career-card flex flex-col gap-4"><FolderOpen className="h-5 w-5 text-[var(--accent-strong)]" /><h4 className="break-words text-sm font-semibold">{project.title}</h4><p className="muted flex-1 whitespace-pre-wrap break-words text-xs leading-6">{project.content}</p>{project.metrics && <div className="help-card rounded-xl p-3 text-xs leading-5">{project.metrics}</div>}<div className="flex flex-wrap gap-1.5">{project.tech_stack?.map(skill => <span key={skill} className="career-pill">{skill}</span>)}</div></article>)}</div> : <CareerEmpty title={loading ? t("Projelerin yükleniyor") : t("İlk çalışmanı vitrine ekle")}>{t("Proje ekle düğmesiyle çalışmalarını kaydet. Eklediğin projeler profilinde saklanır ve oluşturduğun portföye dahil edilir.")}</CareerEmpty>}
    </section>
    <section className="career-card overflow-hidden !p-0" aria-label={t("Portföy önizlemesi")}><div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] p-4"><div className="flex items-center gap-2 text-sm font-semibold"><Globe className="h-4 w-4 muted" />{t("Site önizlemesi")}</div><div className="career-tabs">{previewModes.map(({ id, label, icon: Icon }) => <button key={id} aria-pressed={previewMode === id} onClick={() => setPreviewMode(id)} className="inline-flex items-center gap-2"><Icon className="h-3.5 w-3.5" />{t(label)}</button>)}</div></div>
      {portfolio && needsRefresh && <p className="notice-card border-b px-4 py-3 text-xs">{t("İçerik değişti. İndirmeden önce önizlemeyi güncelle.")}</p>}
      <div className="bg-[var(--surface-muted)] p-2 sm:p-5">{portfolio ? <iframe srcDoc={portfolio.html_content} style={{ width: view.width, maxWidth: "100%" }} className="mx-auto block h-[620px] rounded-xl border border-[var(--border)] bg-[var(--background)]" title={`${view.label} portföy önizlemesi`} sandbox="allow-scripts" /> : <div className="py-14"><CareerEmpty title={t("Portföyünü oluşturmaya hazırsın")} href={!canGenerate && !loading ? "/setup" : undefined} action="Profilimi tamamla">{canGenerate ? t("Önizleme oluştur düğmesine bas. Masaüstü, tablet ve mobil boyutları arasında geçiş yaparak sayfanı kontrol et.") : t("Önizleme oluşturmak için profiline adını ve hedef rolünü ekle.")}</CareerEmpty></div>}</div>
    </section>
    <div className="grid gap-4 md:grid-cols-2"><section className="career-card"><Download className="mb-4 h-5 w-5 muted" /><h3 className="career-card-title">{t("Tek dosya olarak indir")}</h3><p className="muted my-3 text-xs leading-6">{t("Önizlediğin portföyün HTML dosyasını al. Dosyayı açarak sayfanı görüntüleyebilirsin.")}</p><button disabled={!portfolio || needsRefresh || generating || packaging} onClick={() => portfolio && downloadText(portfolio.html_content, "index.html", "text/html;charset=utf-8")} className="career-action secondary-button border"><Download className="h-4 w-4" />{t("HTML indir")}</button></section><section className="career-card"><Package className="mb-4 h-5 w-5 muted" /><h3 className="career-card-title">{t("Yayın paketi hazırla")}</h3><p className="muted my-3 text-xs leading-6">{t("Site dosyası ve kurulum yönergesini ZIP olarak indir. İndirmek siteni otomatik olarak yayımlamaz.")}</p><button onClick={downloadPackage} disabled={!portfolio || needsRefresh || generating || packaging || savingProject} className="career-action primary-button"><Package className="h-4 w-4" />{packaging ? t("Paket hazırlanıyor…") : "ZIP paketi indir"}</button></section></div>
    <CareerLinks current="portfolio" />
  </div>;
}
