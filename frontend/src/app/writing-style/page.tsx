"use client";
import { useLanguage } from "@/lib/i18n";
import { useState } from "react";
import { PenLine, CheckCircle2, AlertTriangle, Wand2 } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

const PRESETS = [
  { key: "technical", name: "Teknik", desc: "Özlü, metrik odaklı, jargon-ok" },
  { key: "professional_conversational", name: "Profesyonel Sıcak", desc: "Doğal ama profesyonel" },
  { key: "formal", name: "Resmi", desc: "Kurumsal, geleneksel" },
  { key: "startup_casual", name: "Startup Rahat", desc: "Direkt, sonuç odaklı" },
];

export default function WritingStylePage() {
  const { translate: t } = useLanguage();
  const [selectedTone, setSelectedTone] = useState("professional_conversational");
  const [guide, setGuide] = useState<any>(null);
  const [testText, setTestText] = useState("");
  const [compliance, setCompliance] = useState<any>(null);
  const [fixedText, setFixedText] = useState("");

  async function buildGuide() {
    const res = await fetchFromApi("/setup/writing_style/build", {
      method: "POST",
      body: JSON.stringify({ tone: selectedTone }),
    });
    setGuide(res);
  }

  async function checkCompliance() {
    if (!testText || !guide) return;
    const res = await fetchFromApi("/setup/writing_style/check", {
      method: "POST",
      body: JSON.stringify({ text: testText, style_guide: guide }),
    });
    setCompliance(res);
  }

  async function autoFix() {
    if (!testText || !guide) return;
    const res = await fetchFromApi("/setup/writing_style/auto_fix", {
      method: "POST",
      body: JSON.stringify({ text: testText, style_guide: guide }),
    });
    setFixedText(res.fixed_text || "");
    setCompliance(res.compliance);
  }

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <PenLine className="w-7 h-7 text-pink-400" /> {t("Yazım Stili Rehberi")}</h1>
        <p className="text-slate-400 mt-1">{t("Ton ayarlama, yasaklı kelime kontrolü ve otomatik düzeltme")}</p>
      </div>

      {/* Tone Presets */}
      <div>
        <h2 className="text-sm font-semibold text-white mb-3">{t("Ton Seçimi")}</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {PRESETS.map((p) => (
            <button key={p.key} onClick={() => setSelectedTone(p.key)}
              className={`text-left p-4 rounded-xl border transition-all ${selectedTone === p.key
                ? "bg-pink-600/15 border-pink-500/40" : "bg-slate-800/50 border-slate-700/40 hover:border-pink-500/20"}`}>
              <div className="text-sm font-medium text-white">{t(p.name)}</div>
              <div className="text-xs text-slate-400 mt-0.5">{t(p.desc)}</div>
            </button>
          ))}
        </div>
        <button onClick={buildGuide} className="mt-3 px-5 py-2 bg-pink-600 hover:bg-pink-500 text-white rounded-xl text-sm font-medium">
          {t("Rehber Oluştur")}</button>
      </div>

      {guide && (
        <>
          {/* Rules */}
          <div className="bg-slate-800/60 border border-slate-700/40 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-2">{t("📏 Kurallar (")}{guide.tone_description})</h3>
            <div className="space-y-1">
              {guide.tone_rules?.map((r: string, i: number) => (
                <div key={i} className="text-xs text-slate-300 bg-slate-900/50 px-3 py-1.5 rounded-lg">{t("•")}{r}</div>
              ))}
            </div>
          </div>

          {/* Test Area */}
          <div className="bg-slate-800/60 border border-slate-700/40 rounded-2xl p-6 space-y-4">
            <h3 className="text-sm font-semibold text-white">{t("✍️ Metin Test Alanı")}</h3>
            <textarea value={testText} onChange={(e) => setTestText(e.target.value)} rows={6}
              placeholder={t("Cover letter veya başka bir metin yapıştırın...")}
              className="w-full bg-slate-900/60 border border-slate-700/40 rounded-lg p-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-pink-500/40" />
            <div className="flex gap-3">
              <button onClick={checkCompliance} className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm">
                <CheckCircle2 className="w-3 h-3 inline mr-1" /> {t("Kontrol Et")}</button>
              <button onClick={autoFix} className="px-4 py-2 bg-pink-600/80 hover:bg-pink-600 text-white rounded-lg text-sm">
                <Wand2 className="w-3 h-3 inline mr-1" /> {t("Otomatik Düzelt")}</button>
            </div>
          </div>

          {/* Compliance Result */}
          {compliance && (
            <div className={`border rounded-xl p-5 ${compliance.is_compliant ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5"}`}>
              <div className="flex items-center gap-3 mb-3">
                <div className={`text-2xl font-bold ${compliance.compliance_score >= 70 ? "text-emerald-400" : "text-amber-400"}`}>
                  {compliance.compliance_score}
                </div>
                <div className="text-sm text-slate-400">{t("/ 100 uyumluluk skoru")}</div>
              </div>
              {compliance.violations?.length > 0 && (
                <div className="space-y-1 mb-2">
                  {compliance.violations.map((v: any, i: number) => (
                    <div key={i} className="text-xs text-red-300 bg-red-500/10 px-3 py-1.5 rounded-lg">
                      ❌ <strong>"{v.phrase}"</strong> → {v.suggestion}
                    </div>
                  ))}
                </div>
              )}
              {compliance.suggestions?.length > 0 && (
                <div className="space-y-1">
                  {compliance.suggestions.map((s: string, i: number) => (
                    <div key={i} className="text-xs text-amber-300 bg-amber-500/10 px-3 py-1.5 rounded-lg">💡 {s}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Fixed Text */}
          {fixedText && (
            <div className="bg-slate-800/60 border border-emerald-500/20 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-emerald-400 mb-2">{t("✅ Düzeltilmiş Metin")}</h3>
              <div className="text-sm text-slate-300 whitespace-pre-wrap">{fixedText}</div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
