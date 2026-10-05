"use client";
import { useLanguage } from "@/lib/i18n";
import { useEffect, useState } from "react";
import { Layers, CheckCircle2, XCircle } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function CVHeatmapPage() {
  const { translate: t } = useLanguage();
  const [profile, setProfile] = useState<any>(null);
  const [, setLoading] = useState(true);

  // Target job input for comparison
  const [jobText, setJobText] = useState("");

  useEffect(() => {
    fetchFromApi("/setup/profile")
      .then((res) => setProfile(res.profile || {}))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const candidateSkills = (profile?.skills || []).map((s: string) => s.toLowerCase());

  const jobKeywords = Array.from(new Set(
    jobText.toLowerCase().match(/[a-z][a-z+#.-]{2,}/g) || []
  )).filter((keyword) => !new Set(["the", "and", "with", "for", "from", "are", "you", "this", "that", "required", "experience", "seeking"]).has(keyword)).slice(0, 30);

  const matched = jobKeywords.filter(k => candidateSkills.some((s: string) => s.includes(k) || k.includes(s)));
  const missing = jobKeywords.filter(k => !matched.includes(k));
  const densityScore = Math.round((matched.length / jobKeywords.length) * 100);
  const cvText = profile?.clean_ats_cv_text || profile?.raw_cv_text || "CV metni henüz oluşturulmadı.";
  const cvParagraphs = cvText.split(/\n+/).map((paragraph: string) => paragraph.trim()).filter(Boolean);
  const getParagraphMatches = (paragraph: string) =>
    matched.filter((keyword) => paragraph.toLowerCase().includes(keyword.toLowerCase())).length;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Layers className="w-7 h-7 text-emerald-400" /> {t("CV analiz haritası")}</h1>
        <p className="text-slate-400 mt-1">
          {t("CV'nizin hedef ilandaki ATS anahtar kelimelerini karşılama yoğunluğunu ve eksik kritik terimleri ısı haritası üzerinde görselleştirin.")}</p>
      </div>

      {/* Grid: Job Description Input vs Heatmap Results */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Target Job Description Text */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
          <div className="text-xs font-bold text-white">{t("Hedef İlan Metni / Gereksinimler")}</div>
          <textarea
            rows={8}
            value={jobText}
            onChange={(e) => setJobText(e.target.value)}
            className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl p-3 text-xs text-white leading-relaxed font-sans"
          />
          <div className="text-xs text-slate-400">
            {t("Farklı bir ilanı yapıştırarak CV uyum yoğunluğunun nasıl değiştiğini anlık gözlemleyebilirsiniz.")}</div>
        </div>

        {/* Right: Heatmap Diagnostics */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="text-xs font-bold text-white">{t("ATS Yoğunluk Skoru")}</div>
            <span className="text-xl font-bold font-mono text-emerald-400">%{densityScore}</span>
          </div>

          <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
            <div
              className="bg-emerald-500 h-full rounded-full transition-all duration-500"
              style={{ width: `${densityScore}%` }}
            />
          </div>

          {/* Matched Keywords (Heatmap High Intensity) */}
          <div className="space-y-2">
            <div className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{t("Güçlü Eşleşen Anahtar Kelimeler (")}{matched.length})</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {matched.map(k => (
                <span
                  key={k}
                  className="px-2.5 py-1 bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 rounded-lg text-xs font-mono font-medium"
                >
                  ✓ {k}
                </span>
              ))}
            </div>
          </div>

          {/* Missing Keywords (Heatmap Zero Intensity) */}
          <div className="space-y-2 pt-2 border-t border-slate-800">
            <div className="text-xs font-semibold text-rose-400 flex items-center gap-1.5">
              <XCircle className="w-3.5 h-3.5" />
              <span>{t("CV'de Eksik Kalan Kritik Terimler (")}{missing.length})</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {missing.map(k => (
                <span
                  key={k}
                  className="px-2.5 py-1 bg-rose-500/10 text-rose-300 border border-rose-500/30 rounded-lg text-xs font-mono font-medium"
                >
                  ✕ {k}
                </span>
              ))}
            </div>
            <div className="text-xs text-slate-400 pt-1">
              <strong>{t("Tavsiye:")}</strong> {t("Yukarıdaki eksik kelimeleri 'Deneyim' veya 'Projeler' bölümündeki madde işaretlerine doğal bir şekilde serpiştirin.")}</div>
          </div>

          <div className="space-y-2 pt-2 border-t border-slate-800">
            <div className="text-xs font-semibold text-indigo-300">{t("CV paragraf yoğunluğu")}</div>
            <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
              {cvParagraphs.map((paragraph: string, index: number) => {
                const matches = getParagraphMatches(paragraph);
                const tone = matches >= 3
                  ? "border-emerald-500/50 bg-emerald-500/10"
                  : matches > 0
                    ? "border-amber-500/40 bg-amber-500/10"
                    : "border-slate-700 bg-slate-950/60";
                return (
                  <div key={`${index}-${paragraph.slice(0, 20)}`} className={`rounded-lg border p-2.5 text-xs text-slate-300 leading-relaxed ${tone}`}>
                    <div className="mb-1 text-xs uppercase tracking-wide text-slate-400">
                      {matches} {t("eşleşme")}</div>
                    {paragraph}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
