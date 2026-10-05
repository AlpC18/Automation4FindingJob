"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, FileSearch, X } from "lucide-react";
import { useLanguage } from "@/lib/i18n";

export type CvProfileFields = {
  full_name?: string;
  email?: string;
  phone?: string;
  location?: string;
  target_role?: string;
  years_of_experience?: number;
  skills?: string[];
  languages?: string[];
  github_url?: string;
  summary?: string;
  experience?: { title?: string; company?: string; period?: string; bullets?: string[] | string }[];
  education?: { degree?: string; school?: string; year?: string }[];
  confidence?: Record<string, number>;
};

export type CvQualityReport = {
  score: number;
  grade: "strong" | "good" | "needs_improvement" | "weak";
  criteria: { id: string; score: number; max_score: number }[];
  recommendation_ids: string[];
  signals?: { skill_count?: number; experience_records?: number; quantified_achievement_bullets?: number; page_count?: number | null };
};

export type CvAiAnalysis = {
  strengths?: string[];
  gaps?: string[];
  improvements?: string[];
  potential_issues?: { severity: "low" | "medium" | "high"; finding: string; evidence?: string; recommendation?: string }[];
};

type Props = {
  fields: CvProfileFields;
  originalText?: string;
  quality?: CvQualityReport | null;
  analysis?: CvAiAnalysis | null;
  optimizedCvText?: string;
  aiWarning?: string | null;
  onApply: (fields: CvProfileFields) => void;
  onCancel: () => void;
  applying?: boolean;
  aiUsed?: boolean;
};

const FIELD_LABELS: Record<string, string> = {
  full_name: "Ad soyad",
  email: "E-posta",
  phone: "Telefon",
  location: "Konum",
  target_role: "Hedef pozisyon",
  years_of_experience: "Deneyim yılı",
  skills: "Yetenekler",
  languages: "Diller",
  github_url: "GitHub / Portfolyo",
  summary: "Profesyonel özet",
  experience: "İş deneyimi",
  education: "Eğitim",
};

const FIELD_ORDER = Object.keys(FIELD_LABELS);

function hasValue(value: unknown): boolean {
  if (typeof value === "string") return Boolean(value.trim());
  if (typeof value === "number") return value > 0;
  return Array.isArray(value) && value.length > 0;
}

export default function CvImportReview({ fields, originalText = "", quality, analysis, optimizedCvText = "", aiWarning, onApply, onCancel, applying = false, aiUsed = false }: Props) {
  const { translate: t } = useLanguage();
  const [edited, setEdited] = useState<CvProfileFields>(fields);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [revisedText, setRevisedText] = useState(optimizedCvText);

  useEffect(() => {
    setEdited(fields);
    setSelected(Object.fromEntries(FIELD_ORDER.map((key) => [key, hasValue(fields[key as keyof CvProfileFields])])));
  }, [fields]);

  useEffect(() => {
    setRevisedText(optimizedCvText);
  }, [optimizedCvText]);

  const visibleFields = useMemo(() => FIELD_ORDER.filter((key) => hasValue(edited[key as keyof CvProfileFields])), [edited]);

  const setScalar = (key: keyof CvProfileFields, value: string | number) => setEdited((current) => ({ ...current, [key]: value }));
  const toggle = (key: string) => setSelected((current) => ({ ...current, [key]: !current[key] }));

  function submit() {
    const picked: CvProfileFields = {};
    for (const key of visibleFields) {
      if (selected[key]) (picked as Record<string, unknown>)[key] = edited[key as keyof CvProfileFields];
    }
    onApply(picked);
  }

  function downloadOptimizedCv() {
    if (!revisedText.trim()) return;
    const url = URL.createObjectURL(new Blob([revisedText], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "improved-resume.txt";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="space-y-4 rounded-xl border border-emerald-500/25 bg-emerald-500/[0.04] p-4" aria-label={t("CV alanlarını incele")}>
      <div className="flex items-start gap-3">
        <FileSearch className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" />
        <div>
          <h3 className="text-sm font-semibold text-white">{t("CV alanlarını incele")}</h3>
          <p className="mt-1 text-xs text-slate-400">{t("Uygulamak istediğin alanları seç, değerleri kontrol et ve sonra onayla.")}</p>
          {aiUsed && <p className="mt-1 text-xs text-amber-300">{t("CV metni isteğinle yapılandırılmış AI sağlayıcısında işlendi. Bilgileri kaydetmeden önce doğrula.")}</p>}
          {aiWarning && <p role="status" className="mt-1 text-xs text-amber-300">{t(aiWarning)}</p>}
        </div>
      </div>

      {quality && <div className="space-y-3 rounded-lg border border-slate-700/80 bg-slate-950/50 p-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h4 className="text-xs font-semibold text-white">{t("CV kalite puanı")}</h4>
            <p className="text-xs text-slate-400">{t("Puan CV belgesinin hazırlık düzeyini değerlendirir; kişiyi veya bilgilerin doğruluğunu ölçmez.")}</p>
          </div>
          <div className="shrink-0 text-right"><div className="text-xl font-bold text-white">{quality.score}<span className="text-xs text-slate-400">/100</span></div><div className="text-xs font-semibold text-emerald-300">{t(`CV notu: ${quality.grade}`)}</div></div>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {quality.criteria.map((criterion) => <div key={criterion.id} className="rounded-md bg-slate-900/70 p-2">
            <div className="mb-1 flex justify-between gap-2 text-xs text-slate-300"><span>{t(`CV ölçütü: ${criterion.id}`)}</span><span>{criterion.score}/{criterion.max_score}</span></div>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-700"><div className="h-full rounded-full bg-emerald-500" style={{ width: `${Math.round(criterion.score / criterion.max_score * 100)}%` }} /></div>
          </div>)}
        </div>
        {quality.recommendation_ids.length > 0 && <div><p className="mb-1 text-xs font-semibold text-slate-300">{t("Öncelikli iyileştirmeler")}</p><ul className="space-y-1 text-xs text-slate-400">{quality.recommendation_ids.map((id) => <li key={id}>• {t(`CV önerisi: ${id}`)}</li>)}</ul></div>}
      </div>}

      {analysis && (analysis.strengths?.length || analysis.gaps?.length || analysis.potential_issues?.length || analysis.improvements?.length) ? (
        <div className="space-y-3 rounded-lg border border-sky-500/20 bg-sky-500/[0.04] p-3">
          <h4 className="text-xs font-semibold text-sky-200">{t("AI CV analizi")}</h4>
          {analysis.strengths?.length ? <div><p className="mb-1 text-xs font-semibold text-emerald-300">{t("Güçlü yönler")}</p><ul className="list-disc space-y-1 pl-4 text-xs text-slate-300">{analysis.strengths.map((item, index) => <li key={`strength-${index}`}>{item}</li>)}</ul></div> : null}
          {analysis.gaps?.length ? <div><p className="mb-1 text-xs font-semibold text-amber-300">{t("Eksik bilgiler")}</p><ul className="list-disc space-y-1 pl-4 text-xs text-slate-300">{analysis.gaps.map((item, index) => <li key={`gap-${index}`}>{item}</li>)}</ul></div> : null}
          {analysis.potential_issues?.length ? <div><p className="mb-1 text-xs font-semibold text-rose-300">{t("Olası sorunlar")}</p><ul className="space-y-2">{analysis.potential_issues.map((item, index) => <li key={`issue-${index}`} className="rounded-md bg-slate-950/60 p-2 text-xs text-slate-300"><span className="font-semibold uppercase text-rose-300">{t(item.severity)}</span> · {item.finding}{item.evidence && <p className="mt-1 text-slate-400">{t("Kanıt")}: “{item.evidence}”</p>}{item.recommendation && <p className="mt-1">{t("Öneri")}: {item.recommendation}</p>}</li>)}</ul></div> : null}
          {analysis.improvements?.length ? <div><p className="mb-1 text-xs font-semibold text-sky-200">{t("İyileştirme önerileri")}</p><ul className="list-disc space-y-1 pl-4 text-xs text-slate-300">{analysis.improvements.map((item, index) => <li key={`improve-${index}`}>{item}</li>)}</ul></div> : null}
          <p className="text-xs text-slate-400">{t("AI geri bildirimi öneridir; olası sorunları CV'nin yanlış olduğu kanıtı olarak değerlendirme.")}</p>
        </div>
      ) : null}

      {optimizedCvText && <details open className="rounded-lg border border-emerald-500/25 bg-slate-950/50 p-3">
        <summary className="cursor-pointer text-xs font-semibold text-emerald-200">{t("Otomatik düzenlenmiş CV önizlemesi")}</summary>
        <p className="mt-2 text-xs text-slate-400">{t("Bu öneri orijinal dosyanın üzerine yazmaz. Yeni metni incele, düzelt ve istersen indir.")}</p>
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <div><h5 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">{t("Orijinal CV")}</h5><pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md border border-slate-800 bg-slate-900 p-3 text-xs leading-relaxed text-slate-300">{originalText}</pre></div>
          <div><h5 className="mb-1 text-xs font-semibold uppercase tracking-wide text-emerald-300">{t("Düzenlenmiş taslak")}</h5><textarea aria-label={t("Düzenlenmiş taslak")} rows={18} value={revisedText} onChange={(event) => setRevisedText(event.target.value)} className="max-h-80 min-h-72 w-full overflow-auto whitespace-pre-wrap rounded-md border border-emerald-500/20 bg-slate-900 p-3 text-xs leading-relaxed text-slate-100" /></div>
        </div>
        <button type="button" onClick={downloadOptimizedCv} className="mt-3 rounded-lg border border-emerald-500/30 px-3 py-2 text-xs font-semibold text-emerald-200">{t("Düzenlenmiş CV metnini indir")}</button>
      </details>}

      <div className="grid gap-3 sm:grid-cols-2">
        {!visibleFields.length && <p className="sm:col-span-2 rounded-lg bg-amber-500/5 p-3 text-xs text-amber-200">{t("CV metninden profil alanı otomatik çıkarılamadı. Metni kontrol edip bilgileri profilinde elle tamamlayabilirsin.")}</p>}
        {visibleFields.map((key) => {
          const confidence = edited.confidence?.[key];
          return (
            <label key={key} className="block min-w-0 rounded-lg border border-slate-700/80 bg-slate-950/50 p-3">
              <span className="mb-2 flex items-center gap-2 text-xs font-medium text-slate-300">
                <input type="checkbox" checked={Boolean(selected[key])} onChange={() => toggle(key)} aria-label={`${t("Uygula")}: ${t(FIELD_LABELS[key])}`} />
                {t(FIELD_LABELS[key])}
                {typeof confidence === "number" && <span className="ml-auto text-xs text-slate-400">{Math.round(confidence * 100)}%</span>}
              </span>

              {key === "skills" || key === "languages" ? (
                <textarea rows={2} value={(edited[key as "skills" | "languages"] || []).join(", ")} onChange={(event) => setEdited((current) => ({ ...current, [key]: event.target.value.split(/[,\n]/).map((value) => value.trim()).filter(Boolean) }))} className="w-full rounded-md border border-slate-700 bg-slate-900 px-2.5 py-2 text-xs text-white" />
              ) : key === "summary" ? (
                <textarea rows={3} value={String(edited.summary || "")} onChange={(event) => setScalar("summary", event.target.value)} className="w-full rounded-md border border-slate-700 bg-slate-900 px-2.5 py-2 text-xs text-white" />
              ) : key === "experience" ? (
                <div className="space-y-3">
                  {(edited.experience || []).map((item, index) => (
                    <div key={index} className="space-y-2 border-t border-slate-700 pt-2 first:border-0 first:pt-0">
                      <input aria-label={t("Pozisyon") } value={item.title || ""} placeholder={t("Pozisyon")} onChange={(event) => setEdited((current) => ({ ...current, experience: current.experience?.map((row, i) => i === index ? { ...row, title: event.target.value } : row) }))} className="w-full rounded-md border border-slate-700 bg-slate-900 px-2.5 py-2 text-xs text-white" />
                      <div className="grid grid-cols-2 gap-2">
                        <input aria-label={t("Şirket")} value={item.company || ""} placeholder={t("Şirket")} onChange={(event) => setEdited((current) => ({ ...current, experience: current.experience?.map((row, i) => i === index ? { ...row, company: event.target.value } : row) }))} className="min-w-0 rounded-md border border-slate-700 bg-slate-900 px-2 py-2 text-xs text-white" />
                        <input aria-label={t("Dönem")} value={item.period || ""} placeholder={t("Dönem")} onChange={(event) => setEdited((current) => ({ ...current, experience: current.experience?.map((row, i) => i === index ? { ...row, period: event.target.value } : row) }))} className="min-w-0 rounded-md border border-slate-700 bg-slate-900 px-2 py-2 text-xs text-white" />
                      </div>
                      <textarea aria-label={t("Başarılar (her satıra bir madde)")} rows={2} value={Array.isArray(item.bullets) ? item.bullets.join("\n") : item.bullets || ""} placeholder={t("Başarılar (her satıra bir madde)")} onChange={(event) => setEdited((current) => ({ ...current, experience: current.experience?.map((row, i) => i === index ? { ...row, bullets: event.target.value.split("\n").filter(Boolean) } : row) }))} className="w-full rounded-md border border-slate-700 bg-slate-900 px-2.5 py-2 text-xs text-white" />
                    </div>
                  ))}
                </div>
              ) : key === "education" ? (
                <div className="space-y-2">
                  {(edited.education || []).map((item, index) => (
                    <div key={index} className="space-y-2 border-t border-slate-700 pt-2 first:border-0 first:pt-0">
                      <input aria-label={t("Derece / Program")} value={item.degree || ""} placeholder={t("Derece / Program")} onChange={(event) => setEdited((current) => ({ ...current, education: current.education?.map((row, i) => i === index ? { ...row, degree: event.target.value } : row) }))} className="w-full rounded-md border border-slate-700 bg-slate-900 px-2.5 py-2 text-xs text-white" />
                      <div className="grid grid-cols-2 gap-2">
                        <input aria-label={t("Kurum")} value={item.school || ""} placeholder={t("Kurum")} onChange={(event) => setEdited((current) => ({ ...current, education: current.education?.map((row, i) => i === index ? { ...row, school: event.target.value } : row) }))} className="min-w-0 rounded-md border border-slate-700 bg-slate-900 px-2 py-2 text-xs text-white" />
                        <input aria-label={t("Yıl")} value={item.year || ""} placeholder={t("Yıl")} onChange={(event) => setEdited((current) => ({ ...current, education: current.education?.map((row, i) => i === index ? { ...row, year: event.target.value } : row) }))} className="min-w-0 rounded-md border border-slate-700 bg-slate-900 px-2 py-2 text-xs text-white" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : key === "years_of_experience" ? (
                <input type="number" min={0} max={60} value={Number(edited.years_of_experience) || 0} onChange={(event) => setScalar("years_of_experience", Number(event.target.value))} className="w-full rounded-md border border-slate-700 bg-slate-900 px-2.5 py-2 text-xs text-white" />
              ) : (
                <input value={String(edited[key as keyof CvProfileFields] || "")} onChange={(event) => setScalar(key as keyof CvProfileFields, event.target.value)} className="w-full rounded-md border border-slate-700 bg-slate-900 px-2.5 py-2 text-xs text-white" />
              )}
            </label>
          );
        })}
      </div>

      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" onClick={onCancel} disabled={applying} className="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 disabled:opacity-50"><X className="h-3.5 w-3.5" />{t("İptal")}</button>
        <button type="button" onClick={submit} disabled={applying || !visibleFields.some((key) => selected[key])} className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"><Check className="h-3.5 w-3.5" />{applying ? t("Kaydediliyor…") : t("Seçilen alanları uygula")}</button>
      </div>
    </section>
  );
}
