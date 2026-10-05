"use client";

import dynamic from "next/dynamic";
import PageTabs from "@/components/PageTabs";
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Clock3, FileSearch, ShieldCheck, Sparkles, WandSparkles } from "lucide-react";
import { requestFromApi, fetchFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import CvImportReview, { type CvAiAnalysis, type CvProfileFields, type CvQualityReport } from "@/components/CvImportReview";

type CvAnalysisResult = {
  fields: CvProfileFields;
  text: string;
  ai_used: boolean;
  quality?: CvQualityReport;
  analysis?: CvAiAnalysis | null;
  optimized_cv_text?: string;
  ai_warning?: string | null;
};

type CvAnalysisHistory = {
  id: string;
  filename: string;
  page_count?: number | null;
  character_count: number;
  ai_requested: boolean;
  ai_used: boolean;
  ai_provider?: string | null;
  quality?: { score?: number; grade?: string };
  created_at?: string;
};

function CvAnalysisPage() {
  const { translate: t } = useLanguage();
  const [result, setResult] = useState<CvAnalysisResult | null>(null);
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [showAutoDraft, setShowAutoDraft] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState<CvAnalysisHistory[]>([]);

  const refreshHistory = useCallback(async () => {
    try {
      const response = await fetchFromApi<{ runs?: CvAnalysisHistory[] }>("/setup/cv-analysis/history?limit=12");
      setHistory(response.runs || []);
    } catch {
      // History is supplementary; an unavailable history store must not block analysis.
    }
  }, []);

  useEffect(() => {
    void refreshHistory();
  }, [refreshHistory]);

  async function analyzeCv(file?: File) {
    if (!file) return;
    setMessage("");
    if (!/\.(pdf|docx)$/i.test(file.name)) {
      setMessage(t("Lütfen PDF veya DOCX biçiminde bir CV seç."));
      return;
    }
    setSourceFile(file);
    setShowAutoDraft(false);
    setBusy(true);
    try {
      const parsed = await requestCv(file, false);
      setResult(parsed);
      await refreshHistory();
      setMessage(`${t("CV içeriği çıkarıldı")}: ${parsed.character_count || 0} ${t("karakter")}.`);
    } catch (error: any) {
      setMessage(error.message || t("CV dosyası okunamadı."));
    } finally {
      setBusy(false);
    }
  }

  async function requestCv(file: File, withAi: boolean): Promise<CvAnalysisResult & { character_count?: number }> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("use_ai", String(withAi));
    const response = await requestFromApi("/setup/parse_cv", { method: "POST", body: formData });
    const parsed = await response.json();
    if (!response.ok) throw new Error(parsed.detail || t("CV dosyası okunamadı."));
    return {
      fields: parsed.fields || {},
      text: parsed.text || "",
      ai_used: Boolean(parsed.ai_used),
      quality: parsed.quality,
      analysis: parsed.analysis,
      optimized_cv_text: parsed.optimized_cv_text || "",
      ai_warning: parsed.ai_warning,
      character_count: parsed.character_count,
    };
  }

  async function runAiCheck() {
    if (!sourceFile) return;
    setBusy(true);
    setMessage("");
    try {
      const parsed = await requestCv(sourceFile, true);
      setResult(parsed);
      await refreshHistory();
      setShowAutoDraft(false);
      setMessage(parsed.ai_used ? t("AI CV kontrolü tamamlandı.") : t("AI sonucu alınamadı; yerel analiz gösteriliyor."));
    } catch (error: any) {
      setMessage(error.message || t("AI CV kontrolü başarısız oldu."));
    } finally {
      setBusy(false);
    }
  }

  function showAutomaticDraft() {
    if (!result?.optimized_cv_text) {
      setMessage(t("Otomatik düzenleme için kullanılabilir bir CV taslağı oluşturulamadı."));
      return;
    }
    setShowAutoDraft(true);
    setMessage(t("Otomatik düzenlenmiş CV taslağı hazır. Taslağı kontrol edip indirebilirsin."));
  }

  async function applyFields(fields: CvProfileFields) {
    setBusy(true);
    setMessage("");
    try {
      const currentResponse = await fetchFromApi("/setup/profile");
      const current = currentResponse.profile || {};
      const updated: Record<string, any> = { ...current, ...fields };
      await fetchFromApi("/setup/update_profile", {
        method: "POST",
        body: JSON.stringify({
          full_name: updated.full_name || "",
          email: updated.email || "",
          phone: updated.phone || "",
          location: updated.location || "",
          target_role: updated.target_role || "",
          years_of_experience: Number(updated.years_of_experience) || 0,
          skills: Array.isArray(updated.skills) ? updated.skills : [],
          languages: Array.isArray(updated.languages) ? updated.languages : [],
          experience: Array.isArray(updated.experience) ? updated.experience : [],
          education: Array.isArray(updated.education) ? updated.education : [],
          target_categories: Array.isArray(updated.target_categories) ? updated.target_categories : [],
          target_roles: Array.isArray(updated.target_roles) ? updated.target_roles : [],
          raw_cv_text: result?.text || updated.raw_cv_text || "",
          work_preference: updated.work_preference || "",
          github_url: updated.github_url || "",
          summary: updated.summary || "",
          work_style: updated.work_style || "",
          writing_tone: updated.writing_tone || "",
        }),
      });
      setResult(null);
      setMessage(t("Seçilen CV bilgileri profiline kaydedildi."));
    } catch (error: any) {
      setMessage(error.message || t("CV bilgileri kaydedilemedi."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <header className="space-y-2">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-300">
          <FileSearch className="h-4 w-4" /> {t("CV analiz merkezi")}
        </div>
        <h1 className="text-2xl font-bold text-white sm:text-3xl">{t("CV'ni analiz et ve geliştir")}</h1>
        <p className="max-w-3xl text-sm leading-relaxed text-slate-400">{t("CV'ni yükle; sistem eksik alanları, ATS hazırlığını ve olası sorunları gösterir. Ardından yalnızca bulunan gerçek bilgilerle düzenlenmiş bir taslak oluşturur.")}</p>
      </header>

      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"><FileSearch className="mb-3 h-5 w-5 text-emerald-300" /><h2 className="text-sm font-semibold text-white">{t("Kural tabanlı analiz")}</h2><p className="mt-1 text-xs leading-relaxed text-slate-400">{t("İletişim, bölümler, hedefleme, okunabilirlik ve ölçülebilir başarı sinyalleri kontrol edilir.")}</p></div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"><Sparkles className="mb-3 h-5 w-5 text-sky-300" /><h2 className="text-sm font-semibold text-white">{t("Otomatik düzenleme")}</h2><p className="mt-1 text-xs leading-relaxed text-slate-400">{t("ATS uyumlu taslak ayrı gösterilir; orijinal CV hiçbir zaman üzerine yazılmaz.")}</p></div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"><ShieldCheck className="mb-3 h-5 w-5 text-amber-300" /><h2 className="text-sm font-semibold text-white">{t("Kontrol sende")}</h2><p className="mt-1 text-xs leading-relaxed text-slate-400">{t("Profiline aktarmadan önce alanları seçebilir, düzenleyebilir ve onaylayabilirsin.")}</p></div>
      </div>

      <section className="rounded-2xl border border-emerald-500/25 bg-emerald-500/[0.04] p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white">{t("CV dosyanı analiz etmeye başla")}</h2>
            <p className="mt-1 text-xs text-slate-400">{t("Metin içeren PDF veya DOCX dosyası yükleyebilirsin. Taranmış PDF için OCR henüz desteklenmiyor.")}</p>
          </div>
          <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-emerald-500">
            <FileSearch className="h-4 w-4" /> {busy ? t("CV okunuyor…") : t("CV yükle ve analiz et")}
            <input type="file" accept=".pdf,.docx" className="hidden" disabled={busy} onChange={async (event) => { const input = event.currentTarget; await analyzeCv(input.files?.[0]); input.value = ""; }} />
          </label>
        </div>
        {message && <p role="status" className="mt-3 flex items-center gap-2 text-xs text-slate-300"><CheckCircle2 className="h-4 w-4 text-emerald-400" />{message}</p>}
      </section>

      {result && <>
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-white">{t("CV üzerinde sonraki adım")}</h2>
              <p className="mt-1 text-xs text-slate-400">{t("AI kontrolü açık bir kullanıcı seçimiyle çalışır. Otomatik düzenleme ise bulunan bilgileri ATS uyumlu taslağa dönüştürür.")}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={runAiCheck} disabled={busy || !sourceFile} className="inline-flex items-center justify-center gap-2 rounded-lg border border-sky-400/30 px-3 py-2 text-xs font-semibold text-sky-200 transition hover:bg-sky-500/10 disabled:opacity-50"><Sparkles className="h-3.5 w-3.5" />{busy ? t("Kontrol ediliyor…") : t("AI ile kontrol et")}</button>
              <button type="button" onClick={showAutomaticDraft} disabled={busy || !result.optimized_cv_text} className="inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-emerald-500 disabled:opacity-50"><WandSparkles className="h-3.5 w-3.5" />{t("CV'yi otomatik düzenle")}</button>
            </div>
          </div>
          <p className="mt-3 text-xs text-slate-400">{t("AI ile kontrol et düğmesine basıldığında CV metni Ayarlar'da seçili AI sağlayıcısına gönderilebilir. AI kullanılmazsa yerel analiz devam eder.")}</p>
        </section>
        <CvImportReview fields={result.fields} originalText={result.text} quality={result.quality} analysis={result.analysis} optimizedCvText={showAutoDraft ? result.optimized_cv_text : ""} aiWarning={result.ai_warning} aiUsed={result.ai_used} applying={busy} onApply={applyFields} onCancel={() => setResult(null)} />
      </>}

      <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="flex items-center gap-2">
          <Clock3 className="h-4 w-4 text-emerald-300" />
          <h2 className="text-sm font-semibold text-white">{t("Son CV analizleri")}</h2>
        </div>
        <p className="mt-1 text-xs text-slate-400">{t("Dosyanın kendisi saklanmaz; yalnızca analiz özeti ve kalite skoru tutulur.")}</p>
        {history.length === 0 ? (
          <p className="mt-4 text-xs text-slate-400">{t("Henüz kaydedilmiş bir CV analizi yok.")}</p>
        ) : (
          <div className="mt-4 space-y-2">
            {history.map((run) => (
              <div key={run.id} className="flex flex-col gap-2 rounded-xl border border-slate-800/80 bg-slate-950/30 px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="truncate text-xs font-semibold text-slate-200">{run.filename || t("Adsız CV")}</p>
                  <p className="mt-1 text-xs text-slate-400">{run.character_count} {t("karakter")} · {run.ai_used ? `AI: ${run.ai_provider || "provider"}` : t("Yerel analiz")}</p>
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-400">
                  <span>{t("Skor")}: <strong className="text-emerald-300">{run.quality?.score ?? 0}/100</strong></span>
                  {run.created_at && <span>{new Date(run.created_at).toLocaleDateString()}</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

// Loaded only when their tab is opened, so this page stays as light as before.
const CVHeatmapPage = dynamic(() => import("../cv-heatmap/page"));
const ProfileOptimizerPage = dynamic(() => import("../profile-optimizer/page"));

// Related screens live here as tabs so the menu stays short; each still has its own route.
const TABS = [
    { label: "CV'yi analiz et", Component: CvAnalysisPage },
    { label: "CV analiz haritası", Component: CVHeatmapPage },
    { label: "Profil optimizasyonu", Component: ProfileOptimizerPage },
];

export default function CvAnalysisPageWithTabs() {
  return <PageTabs tabs={TABS} />;
}
