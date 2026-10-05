"use client";
import { useLanguage } from "@/lib/i18n";

import { useCallback, useEffect, useState } from "react";
import { BookOpen, CalendarDays, CheckCircle2, Clock, Download, ExternalLink, GraduationCap, Plus, RefreshCw, Save } from "lucide-react";
import { fetchFromApi } from "@/lib/api";
import { CareerEmpty, CareerHeading, CareerLinks, CareerMetric, CareerNotice, downloadText } from "@/components/CareerWorkspace";

type Status = "not_started" | "in_progress" | "completed" | "skipped";
type Item = { skill: string; name: string; difficulty: string; estimated_hours: number; status: Status; has_related_foundation: boolean; resources: { title: string; url: string; type: string }[]; portfolio_project: string };
type Plan = { path: Item[]; total_estimated_hours: number; weeks_at_current_pace: number; hours_per_week: number };
type Progress = { details: Record<string, { status: Status; notes: string }> };
const statusNames: Record<Status, string> = { not_started: "Başlanmadı", in_progress: "Devam ediyor", completed: "Tamamlandı", skipped: "Daha sonra" };
const difficultyNames: Record<string, string> = { beginner: "Başlangıç", intermediate: "Orta seviye", advanced: "İleri seviye", unknown: "Seviye belirlenmedi" };

export default function UpskillPage() {
  const { translate: t } = useLanguage();
  const [skills, setSkills] = useState("");
  const [hours, setHours] = useState(10);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [progress, setProgress] = useState<Progress>({ details: {} });
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [gaps, setGaps] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState("");
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [saved, tracked] = await Promise.all([fetchFromApi<{ plan: Plan | null }>("/upskill/plan"), fetchFromApi<Progress>("/upskill/progress")]);
      setPlan(saved.plan); setProgress(tracked);
      setNotes(Object.fromEntries(Object.entries(tracked.details).map(([key, value]) => [key, value.notes || ""])));
      if (saved.plan) { setSkills(saved.plan.path.map(item => item.skill).join(", ")); setHours(saved.plan.hours_per_week); }
    } catch { setError(t("Öğrenme planı yüklenemedi. Yenile düğmesiyle tekrar dene.")); }
    finally { setLoading(false); }
    try {
      const jobs = await fetchFromApi("/scrape/jobs");
      const found: string[] = (jobs.jobs || []).flatMap((job: { skill_gaps?: unknown[] }) => (job.skill_gaps || []).filter((gap): gap is string => typeof gap === "string"));
      setGaps([...new Set(found)].slice(0, 10));
    } catch { /* Skill suggestions are optional; saved learning data stays available. */ }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const getStatus = (item: Item): Status => progress.details[item.skill.toLowerCase()]?.status || item.status;
  const items = plan?.path || [];
  const completed = items.filter(item => getStatus(item) === "completed").length;
  const remainingHours = items.filter(item => !["completed", "skipped"].includes(getStatus(item))).reduce((sum, item) => sum + item.estimated_hours, 0);
  const donePercent = items.length ? Math.round(completed / items.length * 100) : 0;
  const visible = items.filter(item => filter === "all" || getStatus(item) === filter);
  const nextItem = items.find(item => ["not_started", "in_progress"].includes(getStatus(item)));

  async function generatePath() {
    const missing = [...new Set(skills.split(",").map(skill => skill.trim()).filter(Boolean))];
    if (!missing.length) return;
    if (missing.length > 30) { setError("Bir planda en fazla 30 beceri ekleyebilirsin."); return; }
    setGenerating(true); setError(""); setNotice("");
    try {
      setPlan(await fetchFromApi<Plan>("/upskill/generate_path", { method: "POST", body: JSON.stringify({ missing_skills: missing, max_hours_per_week: hours }) }));
      setFilter("all"); setNotice(t("Öğrenme planın kaydedildi. Sayfaya döndüğünde kaldığın yerden devam edebilirsin."));
    } catch { setError(t("Plan oluşturulamadı. Bağlantını kontrol edip tekrar dene.")); }
    finally { setGenerating(false); }
  }

  async function saveProgress(item: Item, status: Status) {
    setSaving(item.skill); setError("");
    try {
      await fetchFromApi("/upskill/progress", { method: "POST", body: JSON.stringify({ skill: item.skill, status, notes: notes[item.skill.toLowerCase()] || "" }) });
      setProgress(await fetchFromApi<Progress>("/upskill/progress"));
      setNotice(t("{skill}: progress and notes saved.", { skill: item.skill }));
    } catch { setError(t("İlerleme kaydedilemedi. Tekrar dene.")); }
    finally { setSaving(""); }
  }

  function addGap(gap: string) {
    const current = skills.split(",").map(skill => skill.trim()).filter(Boolean);
    if (!current.some(skill => skill.toLowerCase() === gap.toLowerCase())) setSkills([...current, gap].join(", "));
  }

  function exportPlan() {
    if (!plan) return;
    downloadText(`# ${t("Öğrenme planı")}\n\n${t("Haftalık süre")}: ${plan.hours_per_week} ${t("saat")}\n\n` + items.map(item => `## ${item.name}\n${t("Durum:")} ${t(statusNames[getStatus(item)])}\n${t("Tahmini süre:")} ${item.estimated_hours} ${t("saat")}\n\n${item.resources.map(resource => `- ${resource.title}: ${resource.url}`).join("\n")}\n\n${t("Proje:")} ${item.portfolio_project}\n${t("Notlar:")} ${notes[item.skill.toLowerCase()] || ""}`).join("\n\n"), "ogrenme-plani.md");
  }

  return <div className="mx-auto max-w-6xl space-y-6">
    <CareerHeading eyebrow={t("KARİYERİNİ ŞEKİLLENDİR / 02")} title={t("Her hafta bir adım ileri.")} description={t("Öğrenmek istediğin becerileri seç, ayırabileceğin süreyi belirle. Kaynaklarını, proje fikirlerini ve ilerlemeni tek yerden takip et.")} action={<><button onClick={load} disabled={loading || generating || !!saving} className="career-action secondary-button border" aria-label={t("Öğrenme planını yenile")}><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /></button><button onClick={exportPlan} disabled={!plan} className="career-action secondary-button border"><Download className="h-4 w-4" />{t("Planı indir")}</button></>} />
    {error && <CareerNotice error>{error}</CareerNotice>}{notice && <CareerNotice>{notice}</CareerNotice>}
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <CareerMetric label={t("Plandaki beceriler")} value={loading ? "…" : items.length} detail={t("Öğrenme hedeflerin")} icon={GraduationCap} />
      <CareerMetric label={t("Tamamlanan")} value={loading ? "…" : `${completed} / ${items.length}`} detail={t("Kendi ilerleme bildirimlerine göre")} icon={CheckCircle2} />
      <CareerMetric label={t("Kalan tahmini süre")} value={loading ? "…" : `${remainingHours} sa`} detail={t("Tamamlanan ve ertelenenler hariç")} icon={Clock} />
      <CareerMetric label={t("Haftalık tempo")} value={`${hours} sa`} detail={plan ? `Bu tempoyla yaklaşık ${Math.ceil(remainingHours / hours)} hafta kaldı` : t("Planını kendi takvimine göre ayarla")} icon={CalendarDays} />
    </div>
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
      <section className="career-card space-y-5"><div><h3 className="career-card-title">{t("Öğrenme hedeflerini belirle")}</h3><p className="muted mt-2 text-xs leading-5">{t("Becerileri virgülle ayır. Oluşturduğun son plan ve ilerlemen hesabında saklanır.")}</p></div><label className="block text-xs font-medium" htmlFor="learning-skills">{t("Hedef beceriler")}</label><textarea id="learning-skills" value={skills} onChange={e => setSkills(e.target.value)} placeholder={t("Örn. Docker, SQL, veri görselleştirme")} rows={3} className="field-input w-full resize-y rounded-xl border p-3 text-sm" />
        <div><label htmlFor="weekly-hours" className="mb-3 flex justify-between text-xs"><span>{t("Haftalık ayırabileceğin süre")}</span><strong>{hours} {t("saat")}</strong></label><input id="weekly-hours" type="range" min={1} max={40} value={hours} onChange={e => setHours(Number(e.target.value))} className="w-full accent-[var(--accent)]" /><div className="career-tabs mt-3">{[3, 5, 10, 15].map(value => <button key={value} aria-pressed={hours === value} onClick={() => setHours(value)}>{value} {t("sa / hafta")}</button>)}</div></div>
        <button onClick={generatePath} disabled={loading || generating || !!saving || !skills.trim()} className="career-action primary-button"><GraduationCap className="h-4 w-4" />{generating ? t("Plan hazırlanıyor…") : plan ? t("Planı güncelle ve kaydet") : t("Planımı oluştur")}</button>
      </section>
      <div className="space-y-4"><section className="career-card"><h3 className="career-card-title">{t("İlerleme özeti")}</h3><p className="my-4 text-4xl font-semibold tracking-tight">%{donePercent}</p><div className="career-meter" role="progressbar" aria-label={t("Öğrenme ilerlemesi")} aria-valuenow={donePercent} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${donePercent}%` }} /></div><p className="muted mt-3 text-xs leading-6">{nextItem ? `Sıradaki odak: ${nextItem.name}` : items.length && completed === items.length ? t("Plandaki tüm becerileri tamamladın.") : t("İlk planını oluştur ve küçük adımlarla başla.")}</p></section>
        <section className="career-card"><BookOpen className="mb-3 h-5 w-5 muted" /><h3 className="career-card-title">{t("Öğren → uygula → göster")}</h3><p className="muted mt-2 text-xs leading-6">{t("Her becerinin proje fikrini tamamladığında portföyüne ekle. Böylece gelişimini somut bir çalışmayla gösterebilirsin.")}</p></section></div>
    </div>
    {gaps.length > 0 && <section className="career-card"><div className="career-card-header"><h3 className="career-card-title">{t("Kayıtlı ilanlardaki beceri eksikleri")}</h3><span className="career-pill">{t("İlan analizlerinden")}</span></div><div className="flex flex-wrap gap-2">{gaps.map(gap => <button key={gap} onClick={() => addGap(gap)} className="choice-chip flex items-center gap-2 rounded-xl border px-3 py-2 text-xs"><Plus className="h-3 w-3" />{gap}</button>)}</div><p className="muted mt-3 text-xs">{t("Bir beceriyi hedeflerine eklemek için tıkla; ardından planı güncelle.")}</p></section>}
    {loading ? <CareerEmpty title={t("Planın yükleniyor")}>{t("Kaydedilmiş öğrenme adımların ve notların alınıyor.")}</CareerEmpty> : !plan ? <CareerEmpty title={t("Öğrenme yolun burada başlayacak")}>{t("İlk becerilerini eklediğinde kaynak, süre tahmini ve uygulama projesi içeren kartlarını burada göreceksin.")}</CareerEmpty> : <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="text-lg font-semibold">{t("Öğrenme adımların")}</h3><span className="muted text-xs">{plan.total_estimated_hours} {t("saat ·")} {plan.hours_per_week} {t("sa/hafta ile")} {plan.weeks_at_current_pace} {t("hafta")}</span></div>
      <div className="career-tabs">{["all", "not_started", "in_progress", "completed", "skipped"].map(status => <button key={status} aria-pressed={filter === status} onClick={() => setFilter(status)}>{status === "all" ? t("Tümü") : t(statusNames[status as Status])}</button>)}</div>
      <div className="grid gap-4 xl:grid-cols-2">{visible.map(item => <article key={item.skill} className="career-card space-y-5">
        <div className="flex items-start justify-between gap-3"><div><h4 className="font-semibold">{item.name}</h4><div className="mt-2 flex flex-wrap gap-2"><span className="career-pill">{t(difficultyNames[item.difficulty] || item.difficulty)}</span><span className="career-pill"><Clock className="h-3 w-3" />{item.estimated_hours} {t("sa")}</span></div></div><CheckCircle2 className={`h-5 w-5 shrink-0 ${getStatus(item) === "completed" ? "text-[var(--accent)]" : "muted"}`} /></div>
        {item.has_related_foundation && <p className="text-xs text-[var(--accent-strong)]">{t("Profilinde bu konuyla ilişkili bir temel var; süre tahmini buna göre ayarlandı.")}</p>}
        <div className="space-y-2">{item.resources.map(resource => /^https?:\/\//i.test(resource.url) && <a key={resource.url} href={resource.url} target="_blank" rel="noopener noreferrer" className="career-feature flex items-center gap-3 text-xs"><BookOpen className="h-4 w-4 shrink-0 muted" /><span className="min-w-0 flex-1 break-words">{resource.title}</span><ExternalLink className="h-3 w-3 shrink-0 muted" /></a>)}</div>
        <div className="help-card rounded-xl p-4"><p className="mb-2 text-xs font-semibold">{t("Uygulama projesi")}</p><p className="muted text-xs leading-6">{item.portfolio_project}</p></div>
        <label className="flex items-center justify-between gap-3 text-xs">{t("İlerleme durumu")}<select aria-label={`${item.skill} ilerleme durumu`} value={getStatus(item)} disabled={!!saving || generating} onChange={e => saveProgress(item, e.target.value as Status)} className="field-input rounded-lg border p-2">{Object.entries(statusNames).map(([status, name]) => <option key={status} value={status}>{name}</option>)}</select></label>
        <div><label htmlFor={`note-${item.skill}`} className="mb-2 block text-xs">{t("Çalışma notların")}</label><textarea id={`note-${item.skill}`} rows={2} value={notes[item.skill.toLowerCase()] || ""} onChange={e => setNotes(current => ({ ...current, [item.skill.toLowerCase()]: e.target.value }))} placeholder={t("Kaynak, öğrendiklerin veya sonraki adım…")} className="field-input w-full rounded-xl border p-3 text-xs" /><button onClick={() => saveProgress(item, getStatus(item))} disabled={!!saving || generating} className="career-action secondary-button mt-2 border"><Save className="h-3.5 w-3.5" />{saving === item.skill ? "Kaydediliyor…" : t("Notları kaydet")}</button></div>
      </article>)}</div>
      {!visible.length && <CareerEmpty title={t("Bu durumda adım yok")}>{t("Diğer durumları seçerek öğrenme adımlarını görebilirsin.")}</CareerEmpty>}
    </section>}
    <CareerLinks current="learn" />
  </div>;
}
