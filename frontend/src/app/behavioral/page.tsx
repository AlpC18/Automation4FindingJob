"use client";
import { useLanguage } from "@/lib/i18n";
import { useState } from "react";
import { Brain, ChevronRight, CheckCircle2, ArrowRight } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

const DIMENSIONS = [
  {
    id: "communication", name: "İletişim Tarzı",
    options: [
      { value: "direct", label: "Doğrudan ve açık" },
      { value: "diplomatic", label: "Diplomatik ve uzlaşmacı" },
      { value: "analytical", label: "Analitik ve veri odaklı" },
      { value: "collaborative", label: "İş birliğine dayalı" },
    ],
  },
  {
    id: "work_style", name: "Çalışma Tarzı",
    options: [
      { value: "autonomous", label: "Bağımsız, minimal denetimle" },
      { value: "structured", label: "Yapılandırılmış süreçler" },
      { value: "agile", label: "Esnek, hızlı iterasyon" },
      { value: "methodical", label: "Metodik, detaylı planlama" },
    ],
  },
  {
    id: "motivation", name: "Motivasyon Kaynağı",
    options: [
      { value: "impact", label: "Somut etki yaratmak" },
      { value: "learning", label: "Sürekli öğrenme ve gelişme" },
      { value: "mastery", label: "Teknik ustalık" },
      { value: "leadership", label: "Liderlik ve mentorluk" },
    ],
  },
  {
    id: "conflict_resolution", name: "Çatışma Yönetimi",
    options: [
      { value: "assertive", label: "Kararlı, pozisyon savunma" },
      { value: "compromise", label: "Uzlaşma arayışı" },
      { value: "avoidant", label: "Kaçınma, zaman tanıma" },
      { value: "collaborative", label: "Ortak çözüm arayışı" },
    ],
  },
  {
    id: "energy_source", name: "Enerji Kaynağı",
    options: [
      { value: "extrovert", label: "Takım çalışması ve sosyal etkileşim" },
      { value: "introvert", label: "Derin odaklanma ve bireysel çalışma" },
      { value: "ambivert", label: "Dengeleyici — duruma göre değişir" },
    ],
  },
];

export default function BehavioralProfilePage() {
  const { translate: t } = useLanguage();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [profile, setProfile] = useState<any>(null);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);

  const currentDim = DIMENSIONS[step];
  const isComplete = step >= DIMENSIONS.length;

  async function handleBuild() {
    setLoading(true);
    try {
      const res = await fetchFromApi("/setup/behavioral/build", {
        method: "POST",
        body: JSON.stringify({ answers }),
      });
      setProfile(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  function selectOption(value: string) {
    setAnswers({ ...answers, [currentDim.id]: value });
    if (step < DIMENSIONS.length - 1) {
      setStep(step + 1);
    } else {
      setStep(DIMENSIONS.length);
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Brain className="w-7 h-7 text-purple-400" /> {t("Davranışsal Profil Değerlendirmesi")}</h1>
        <p className="text-slate-400 mt-1">{t("İş eşleştirme ve kültürel uyum skorlaması için kişilik profilinizi oluşturun.")}</p>
      </div>

      {/* Progress bar */}
      <div className="flex gap-2">
        {DIMENSIONS.map((d, i) => (
          <div key={d.id} className={`h-1.5 flex-1 rounded-full transition-colors ${i < step ? "bg-purple-500" : i === step ? "bg-purple-400/60" : "bg-slate-700"}`} />
        ))}
      </div>

      {!isComplete && currentDim && (
        <div className="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-8">
          <div className="text-xs text-purple-400 font-mono mb-2">{t("SORU")}{step + 1} / {DIMENSIONS.length}</div>
          <h2 className="text-xl font-semibold text-white mb-6">{t(currentDim.name)}</h2>
          <div className="space-y-3">
            {currentDim.options.map((opt) => (
              <button
                key={opt.value}
                onClick={() => selectOption(opt.value)}
                className={`w-full text-left px-5 py-4 rounded-xl border transition-all flex items-center justify-between group
                  ${answers[currentDim.id] === opt.value
                    ? "bg-purple-600/20 border-purple-500/50 text-purple-200"
                    : "bg-slate-800/40 border-slate-700/40 text-slate-300 hover:border-purple-500/30 hover:bg-slate-800/80"
                  }`}
              >
                <span className="font-medium">{t(opt.label)}</span>
                <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-purple-400 transition-colors" />
              </button>
            ))}
          </div>
          {step > 0 && (
            <button onClick={() => setStep(step - 1)} className="mt-4 text-sm text-slate-500 hover:text-slate-300">
              {t("← Geri")}</button>
          )}
        </div>
      )}

      {isComplete && !profile && (
        <div className="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-8 text-center">
          <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-white mb-2">{t("Değerlendirme Tamamlandı!")}</h2>
          <p className="text-slate-400 mb-6">{t("Profilinizi oluşturmak için aşağıya tıklayın.")}</p>
          <button
            onClick={handleBuild}
            disabled={loading}
            className="px-6 py-3 bg-purple-600 hover:bg-purple-500 text-white font-medium rounded-xl transition-colors disabled:opacity-50 flex items-center gap-2 mx-auto"
          >
            {loading ? t("Oluşturuluyor...") : t("Profili Oluştur")} <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {profile && (
        <div className="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-8 space-y-6">
          <h2 className="text-xl font-semibold text-white">{t("📊 Davranışsal Profiliniz")}</h2>
          <p className="text-sm text-slate-400 bg-slate-900/60 rounded-lg p-3 font-mono">{profile.summary}</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(profile.dimensions || {}).map(([key, val]: [string, any]) => (
              <div key={key} className="bg-slate-900/50 rounded-xl p-4 border border-slate-700/40">
                <div className="text-xs text-purple-400 font-mono uppercase mb-1">{key.replace("_", " ")}</div>
                <div className="text-sm text-white font-medium">{val.label}</div>
              </div>
            ))}
          </div>
          <button onClick={() => { setProfile(null); setStep(0); setAnswers({}); }}
            className="text-sm text-slate-500 hover:text-slate-300">{t("Tekrar Başla")}</button>
        </div>
      )}
    </div>
  );
}
