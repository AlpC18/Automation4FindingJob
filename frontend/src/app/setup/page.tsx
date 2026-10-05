"use client";

import { useEffect, useState } from "react";
import {
  UserCheck,
  FileText,
  Brain,
  Database,
  CheckCircle,
  HelpCircle,
  Plus,
  Sparkles,
  Eye
} from "lucide-react";
import { buildApiUrl, fetchFromApi, requestFromApi } from "@/lib/api";
import PdfJsPreview from "@/components/PdfJsPreview";
import { useLanguage } from "@/lib/i18n";
import CvImportReview, { type CvAiAnalysis, type CvProfileFields, type CvQualityReport } from "@/components/CvImportReview";

export default function SetupPage() {
  const { translate: t } = useLanguage();
  const [profileData, setProfileData] = useState<any>(null);
  const [ragProjects, setRagProjects] = useState<any[]>([]);
  const [writingSample, setWritingSample] = useState("");
  const [stylometryResult, setStylometryResult] = useState<any>(null);
  const [analyzingStyle, setAnalyzingStyle] = useState(false);
  const [loading, setLoading] = useState(true);
  const [pdfTheme, setPdfTheme] = useState("navy");
  const [showPdfPreview, setShowPdfPreview] = useState(false);
  const [cvText, setCvText] = useState("");
  const [cvBusy, setCvBusy] = useState(false);
  const [cvMessage, setCvMessage] = useState("");
  const [cvSuggestions, setCvSuggestions] = useState<{ fields: CvProfileFields; text: string; ai_used: boolean; quality?: CvQualityReport; analysis?: CvAiAnalysis | null; optimized_cv_text?: string; ai_warning?: string | null } | null>(null);
  const [useAiCvExtraction, setUseAiCvExtraction] = useState(false);

  // New Project Form
  const [newTitle, setNewTitle] = useState("");
  const [newStack, setNewStack] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newMetrics, setNewMetrics] = useState("");
  const [addingProj, setAddingProj] = useState(false);

  async function loadSetupData() {
    try {
      setLoading(true);
      const [pRes, rRes] = await Promise.all([
        fetchFromApi("/setup/profile").catch(() => ({ profile: null, missing_data_interview_questions: [] })),
        fetchFromApi("/setup/rag_projects").catch(() => ({ projects: [] }))
      ]);
      setProfileData(pRes);
      setCvText(pRes.profile?.raw_cv_text || "");
      setRagProjects(rRes.projects || []);
      if (pRes.profile?.style_profile?.style_tone) {
        setStylometryResult(pRes.profile.style_profile);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSetupData();
  }, []);

  async function importCv(file?: File) {
    if (!file) return;
    setCvMessage("");
    try {
      if (!/\.(pdf|docx)$/i.test(file.name)) throw new Error(t("Lütfen PDF veya DOCX biçiminde bir CV seç."));
      setCvBusy(true);
      const uploadData = new FormData();
      uploadData.append("file", file);
      uploadData.append("use_ai", String(useAiCvExtraction));
      const response = await requestFromApi("/setup/parse_cv", { method: "POST", body: uploadData });
      const parsed = await response.json();
      if (!response.ok) throw new Error(parsed.detail || t("CV dosyası okunamadı."));
      setCvText(parsed.text || "");
      setCvSuggestions({ fields: parsed.fields || {}, text: parsed.text || "", ai_used: Boolean(parsed.ai_used), quality: parsed.quality, analysis: parsed.analysis, optimized_cv_text: parsed.optimized_cv_text || "", ai_warning: parsed.ai_warning });
      setCvMessage(`${t("CV içeriği çıkarıldı")}: ${parsed.character_count || 0} ${t("karakter")}. ${t("Aşağıdaki alanları kontrol edip seç.")}`);
    } catch (error: any) {
      setCvMessage(error.message || t("CV dosyası okunamadı."));
    } finally {
      setCvBusy(false);
    }
  }

  async function applyCvFields(fields: CvProfileFields) {
    const current = profileData?.profile || {};
    const updated: Record<string, any> = { ...current };
    for (const [key, value] of Object.entries(fields)) {
      if (key !== "confidence") updated[key] = value;
    }
    setCvBusy(true);
    setCvMessage("");
    try {
      await fetchFromApi("/setup/update_profile", {
        method: "POST",
        body: JSON.stringify({
          full_name: updated.full_name || "", email: updated.email || "", phone: updated.phone || "",
          target_role: updated.target_role || "", years_of_experience: Number(updated.years_of_experience) || 0,
          skills: Array.isArray(updated.skills) ? updated.skills : [],
          languages: Array.isArray(updated.languages) ? updated.languages : [],
          experience: Array.isArray(updated.experience) ? updated.experience : [],
          education: Array.isArray(updated.education) ? updated.education : [],
          target_categories: Array.isArray(updated.target_categories) ? updated.target_categories : [],
          target_roles: Array.isArray(updated.target_roles) ? updated.target_roles : [],
          raw_cv_text: cvSuggestions?.text || cvText, location: updated.location || "",
          work_preference: updated.work_preference || "", github_url: updated.github_url || "",
          summary: updated.summary || "", work_style: updated.work_style || "", writing_tone: updated.writing_tone || "",
        }),
      });
      setCvSuggestions(null);
      setCvMessage(t("Seçilen CV bilgileri profiline kaydedildi."));
      await loadSetupData();
    } catch (error: any) {
      setCvMessage(error.message || t("CV bilgileri kaydedilemedi."));
    } finally {
      setCvBusy(false);
    }
  }

  async function saveCvText() {
    const profile = profileData?.profile || {};
    setCvBusy(true);
    setCvMessage("");
    try {
      await fetchFromApi("/setup/update_profile", {
        method: "POST",
        body: JSON.stringify({
          full_name: profile.full_name || "", email: profile.email || "", target_role: profile.target_role || "",
          years_of_experience: Number(profile.years_of_experience) || 0,
          skills: Array.isArray(profile.skills) ? profile.skills : [],
          languages: Array.isArray(profile.languages) ? profile.languages : [],
          experience: Array.isArray(profile.experience) ? profile.experience : [],
          education: Array.isArray(profile.education) ? profile.education : [],
          target_categories: Array.isArray(profile.target_categories) ? profile.target_categories : [],
          target_roles: Array.isArray(profile.target_roles) ? profile.target_roles : [],
          raw_cv_text: cvText, phone: profile.phone || "", location: profile.location || "",
          work_preference: profile.work_preference || "", github_url: profile.github_url || "",
          summary: profile.summary || "", work_style: profile.work_style || "", writing_tone: profile.writing_tone || "",
        }),
      });
      setCvMessage(t("CV metni profilinle birlikte kaydedildi."));
      await loadSetupData();
    } catch (error: any) {
      setCvMessage(error.message || t("CV metni kaydedilemedi."));
    } finally {
      setCvBusy(false);
    }
  }

  async function handleAnalyzeStylometry() {
    if (!writingSample.trim()) return;
    try {
      setAnalyzingStyle(true);
      const res = await fetchFromApi("/setup/stylometry", {
        method: "POST",
        body: JSON.stringify({ writing_samples: [writingSample] })
      });
      setStylometryResult(res.style_profile);
    } finally {
      setAnalyzingStyle(false);
    }
  }

  async function handleAddProject() {
    if (!newTitle.trim() || !newContent.trim()) return;
    try {
      setAddingProj(true);
      const stackList = newStack.split(",").map(s => s.trim()).filter(Boolean);
      await fetchFromApi("/setup/rag_projects", {
        method: "POST",
        body: JSON.stringify({
          title: newTitle,
          tech_stack: stackList,
          content: newContent,
          metrics: newMetrics
        })
      });
      setNewTitle("");
      setNewStack("");
      setNewContent("");
      setNewMetrics("");
      await loadSetupData();
    } finally {
      setAddingProj(false);
    }
  }

  if (loading) {
    return <div className="p-8 text-center text-slate-400">{t("Yükleniyor...")}</div>;
  }

  const profile = profileData?.profile || {};
  const questions = profileData?.missing_data_interview_questions || [];

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <UserCheck className="w-6 h-6 text-blue-500" />
          {t("Profilim")}</h1>
        <p className="text-xs text-slate-400 mt-1">
          {t("CV'ni, yazım tarzını ve projelerini buraya ekle; başvurular bu bilgilerle hazırlanır.")}</p>
      </div>

      {/* Grid: 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* Left Column: ATS CV & Dynamic Interview */}
        <div className="space-y-6">
          {/* Dynamic Interview Questions for Missing Data */}
          <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
            <div className="flex items-center gap-2">
              <HelpCircle className="w-5 h-5 text-amber-400" />
              <h2 className="text-sm font-semibold text-white">{t("Dinamik Mülakat Akışı (Eksik Veri Tespiti)")}</h2>
            </div>
            <p className="text-xs text-slate-400">
              {t("Yapay zeka, özgeçmişinizdeki eksik ve yüksek etkili alanları tespit ederek sorular üretir:")}</p>

            <div className="space-y-3">
              {questions.length === 0 ? (
                <div className="text-xs text-emerald-400 flex items-center gap-2 p-3 bg-emerald-500/10 rounded-xl border border-emerald-500/20">
                  <CheckCircle className="w-4 h-4" /> {t("Özgeçmişinizde kritik veri eksikliği bulunmuyor.")}</div>
              ) : (
                questions.map((q: any, i: number) => (
                  <div key={i} className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-amber-400 font-mono uppercase bg-amber-400/10 px-2 py-0.5 rounded">
                        {t("Kategori:")}{q.category}
                      </span>
                    </div>
                    <p className="text-xs text-slate-200">{q.question}</p>
                    <input
                      type="text"
                      placeholder={t("Cevabınızı girin (örn. %35 performans artışı sağlandı)...")}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500"
                    />
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Clean ATS Standard View & PDF Motor */}
          <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-blue-400" />
                <h2 className="text-sm font-semibold text-white">{t("ATS PDF İndirme & Önizleme Motoru")}</h2>
              </div>
              <span className="text-xs bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded-full font-mono w-fit">
                {t("%100 ATS Uyumlu Tek Kolon")}</span>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              {t("ReportLab ile üretilen, ATS tarayıcılarına %100 uyumlu, seçilebilir metinli, sağa hizalı tarihli ve tipografik hiyerarşiye sahip standart PDF.")}</p>

            <div className="space-y-2 rounded-xl border border-slate-800 bg-slate-900/50 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <label htmlFor="profile-cv-text" className="text-xs font-semibold text-slate-200">{t("CV metni / PDF içe aktar")}</label>
                <label className="cursor-pointer rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-200">
                  {cvBusy ? t("CV okunuyor…") : t("PDF / DOCX yükle")}
                  <input type="file" accept=".pdf,.docx" className="hidden" disabled={cvBusy} onChange={async (event) => { const input = event.currentTarget; await importCv(input.files?.[0]); input.value = ""; }} />
                </label>
              </div>
              <label className="flex items-start gap-2 text-xs leading-relaxed text-slate-400">
                <input type="checkbox" checked={useAiCvExtraction} onChange={(event) => setUseAiCvExtraction(event.target.checked)} className="mt-0.5" />
                <span>{t("AI ile çıkarım seçilirse CV metni Ayarlar'da seçili AI sağlayıcısında işlenir; bulut sağlayıcısıysa metin cihazından çıkar. Kapalıysa yalnızca yerel çıkarım kullanılır.")}</span>
              </label>
              <textarea id="profile-cv-text" rows={5} value={cvText} onChange={(event) => setCvText(event.target.value)} placeholder={t("CV metnini buraya yapıştır veya PDF dosyası yükle.")} className="w-full rounded-lg border border-slate-700 bg-slate-950 p-3 text-xs text-slate-200" />
              {cvMessage && <p role="status" className="text-xs text-slate-400">{cvMessage}</p>}
              {cvSuggestions && <CvImportReview fields={cvSuggestions.fields} originalText={cvSuggestions.text} quality={cvSuggestions.quality} analysis={cvSuggestions.analysis} optimizedCvText={cvSuggestions.optimized_cv_text} aiWarning={cvSuggestions.ai_warning} aiUsed={cvSuggestions.ai_used} applying={cvBusy} onApply={applyCvFields} onCancel={() => setCvSuggestions(null)} />}
              <button type="button" onClick={saveCvText} disabled={cvBusy} className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">{t("CV metnini profile kaydet")}</button>
            </div>

            {/* Theme Picker */}
            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-wrap items-center justify-between gap-2 text-xs">
              <span className="text-slate-400 text-xs font-medium">{t("Tema / Renk Paleti:")}</span>
              <div className="flex items-center gap-1.5">
                {[
                  { id: "navy", label: "Navy Executive", color: "bg-blue-600" },
                  { id: "charcoal", label: "Charcoal Dark", color: "bg-slate-700" },
                  { id: "slate", label: "Slate Minimal", color: "bg-slate-500" },
                  { id: "emerald", label: "Emerald Clean", color: "bg-emerald-600" }
                ].map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setPdfTheme(t.id)}
                    className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1.5 transition ${
                      pdfTheme === t.id
                        ? "bg-slate-800 text-white border border-blue-500/50"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    <span className={`w-2 h-2 rounded-full ${t.color}`} />
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2">
              <a
                href={buildApiUrl(`/setup/preview_ats_cv?theme=${pdfTheme}`)}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold py-2 px-3 rounded-xl transition flex items-center justify-center gap-1.5 border border-slate-700"
              >
                <Eye className="w-3.5 h-3.5 text-blue-400" /> {t("Tarayıcıda Önizle")}</a>
              <button
                type="button"
                onClick={() => setShowPdfPreview((visible) => !visible)}
                className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold py-2 px-3 rounded-xl transition flex items-center justify-center gap-1.5 border border-slate-700"
              >
                <Eye className="w-3.5 h-3.5 text-emerald-400" />
                {showPdfPreview ? t("Önizlemeyi Kapat") : t("Sayfada Görüntüle")}
              </button>
              <a
                href={buildApiUrl(`/setup/download_ats_cv?theme=${pdfTheme}`)}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold py-2 px-3 rounded-xl transition flex items-center justify-center gap-1.5 shadow-lg shadow-blue-600/20"
              >
                <FileText className="w-3.5 h-3.5" /> {t("ATS PDF İndir")}</a>
            </div>

            {showPdfPreview && <PdfJsPreview src={buildApiUrl(`/setup/preview_ats_cv?theme=${pdfTheme}`)} />}

            <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 h-52 overflow-y-auto whitespace-pre-wrap">
              {profile.clean_ats_cv_text || t("ATS Metni oluşturuluyor...")}
            </pre>
          </div>
        </div>

        {/* Right Column: Stylometry & RAG Memory */}
        <div className="space-y-6">
          {/* Human Stylometry Profiler */}
          <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
            <div className="flex items-center gap-2">
              <Brain className="w-5 h-5 text-indigo-400" />
              <h2 className="text-sm font-semibold text-white">{t("Yazım Üslubu (Human Stylometry) Profilleme")}</h2>
            </div>
            <p className="text-xs text-slate-400">
              {t("Daha önce yazdığınız gerçek e-posta veya metinleri yapıştırın. Sistem burstiness (ritim) ve söz dağarcığınızı çıkararak Kişisel Ses Profilinizi oluştursun.")}</p>

            <textarea
              value={writingSample}
              onChange={(e) => setWritingSample(e.target.value)}
              placeholder={t("Örnek: 'Geçtiğimiz çeyrekte ekiple beraber mikroservis mimarisine geçiş yaptık. Bazı gecikme sorunları yaşadık ancak Redis önbellekleme ve sorgu optimizasyonu ile latency'yi 120ms altına düşürdük...'")}
              className="w-full h-24 bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
            ></textarea>

            <button
              onClick={handleAnalyzeStylometry}
              disabled={analyzingStyle || !writingSample.trim()}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-4 py-2 rounded-xl transition disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {analyzingStyle ? "Analiz Ediliyor..." : t("Stilometrik Ses Profilini Çıkar")}
            </button>

            {stylometryResult && (
              <div className="p-4 rounded-xl bg-indigo-950/20 border border-indigo-500/20 space-y-3">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-semibold text-indigo-300">{t("Ses Tonu:")}</span>
                  <span className="text-white font-mono bg-indigo-500/20 px-2 py-0.5 rounded">{stylometryResult.style_tone}</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="p-2 rounded bg-slate-900 border border-slate-800">
                    <div className="text-xs text-slate-400">{t("Burstiness")}</div>
                    <div className="text-xs font-bold text-white">{stylometryResult.burstiness_index || "0.68"}</div>
                  </div>
                  <div className="p-2 rounded bg-slate-900 border border-slate-800">
                    <div className="text-xs text-slate-400">{t("Söz Dağarcığı")}</div>
                    <div className="text-xs font-bold text-white">{stylometryResult.lexical_diversity || "0.74"}</div>
                  </div>
                  <div className="p-2 rounded bg-slate-900 border border-slate-800">
                    <div className="text-xs text-slate-400">{t("Resmiyet")}</div>
                    <div className="text-xs font-bold text-white">%{stylometryResult.formality_score || "75"}</div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* RAG & Vector Memory */}
          <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Database className="w-5 h-5 text-emerald-400" />
                <h2 className="text-sm font-semibold text-white">{t("Kayıtlı projeler (")}{ragProjects.length} {t("Proje)")}</h2>
              </div>
            </div>
            <p className="text-xs text-slate-400">
              {t("İlana en uygun gerçek proje deneyimlerini otomatik seçip başvuru metnine zerk eden semantik hafıza.")}</p>

            <div className="space-y-3 max-h-56 overflow-y-auto">
              {ragProjects.map((p) => (
                <div key={p.id} className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
                  <div className="flex justify-between items-center">
                    <span className="text-xs font-semibold text-white">{p.title}</span>
                    <span className="text-xs text-emerald-400 font-mono bg-emerald-500/10 px-2 py-0.5 rounded">
                      {p.metrics || "Metrikli"}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 line-clamp-2">{p.content}</p>
                  <div className="text-xs text-slate-400 font-mono">
                    {t("Stack:")}{p.tech_stack?.join(", ")}
                  </div>
                </div>
              ))}
            </div>

            {/* Add Project to RAG */}
            <div className="pt-2 border-t border-slate-800 space-y-2">
              <div className="text-xs font-semibold text-slate-300">{t("Yeni Proje / Başarı Hikayesi Ekle:")}</div>
              <input
                type="text"
                placeholder={t("Proje Başlığı (Örn: Real-time Event Streaming)")}
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white"
              />
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  placeholder={t("Tech Stack (Virgülle ayırın)")}
                  value={newStack}
                  onChange={(e) => setNewStack(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white"
                />
                <input
                  type="text"
                  placeholder={t("Ölçülebilir Metrik (%30 Hızlanma)")}
                  value={newMetrics}
                  onChange={(e) => setNewMetrics(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white"
                />
              </div>
              <textarea
                placeholder={t("Projenin mimari detayları ve çözülen problem...")}
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
                className="w-full h-16 bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-white"
              ></textarea>
              <button
                onClick={handleAddProject}
                disabled={addingProj || !newTitle || !newContent}
                className="w-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold py-2 rounded-xl transition flex items-center justify-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" /> {t("Projeyi kaydet")}</button>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
