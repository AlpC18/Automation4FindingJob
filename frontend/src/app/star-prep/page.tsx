"use client";
import { useLanguage } from "@/lib/i18n";
import { useEffect, useState } from "react";
import { Target, CheckCircle2 } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function STARPrepPage() {
  const { translate: t } = useLanguage();
  const [categories, setCategories] = useState<any>({});
  const [stubs, setStubs] = useState<any[]>([]);
  const [selectedCat, setSelectedCat] = useState<string | null>(null);
  const [answer, setAnswer] = useState({ situation: "", task: "", action: "", result: "" });
  const [scoreResult, setScoreResult] = useState<any>(null);
  const [, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [cats, st] = await Promise.all([
          fetchFromApi("/interview/star/categories").catch(() => ({})),
          fetchFromApi("/interview/star/extract", { method: "POST" }).catch(() => ({ stubs: [] })),
        ]);
        setCategories(cats);
        setStubs(st.stubs || []);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleScore() {
    const res = await fetchFromApi("/interview/star/score", {
      method: "POST",
      body: JSON.stringify(answer),
    });
    setScoreResult(res);
  }

  const catEntries = Object.entries(categories);

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Target className="w-7 h-7 text-orange-400" /> {t("STAR Mülakat Hazırlığı")}</h1>
        <p className="text-slate-400 mt-1">{t("Davranışsal mülakat sorularına yapılandırılmış STAR cevapları hazırlayın.")}</p>
      </div>

      {/* Categories */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-3">{t("Soru Kategorileri")}</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {catEntries.map(([key, val]: [string, any]) => (
            <button key={key} onClick={() => setSelectedCat(selectedCat === key ? null : key)}
              className={`text-left p-4 rounded-xl border transition-all ${selectedCat === key
                ? "bg-orange-600/15 border-orange-500/40 text-orange-200"
                : "bg-slate-800/50 border-slate-700/40 text-slate-300 hover:border-orange-500/20"}`}>
              <div className="text-sm font-medium">{val.name}</div>
              <div className="text-xs text-slate-400 mt-1">{val.questions?.length || 0} {t("soru")}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Questions for selected category */}
      {selectedCat && categories[selectedCat] && (
        <div className="bg-slate-800/50 border border-slate-700/40 rounded-2xl p-6 space-y-3">
          <h3 className="text-md font-semibold text-orange-300">{categories[selectedCat].name}</h3>
          {categories[selectedCat].questions?.map((q: string, i: number) => (
            <div key={i} className="p-3 bg-slate-900/50 rounded-lg text-sm text-slate-300 border border-slate-700/30">
              {i + 1}. {q}
            </div>
          ))}
        </div>
      )}

      {/* STAR Stubs from CV */}
      {stubs.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-white mb-3">{t("CV'nizden Çıkarılan STAR Adayları")}</h2>
          <div className="space-y-2">
            {stubs.map((stub: any, i: number) => (
              <div key={i} className="bg-slate-800/50 border border-slate-700/40 rounded-xl p-4">
                <div className="text-sm font-medium text-white">{stub.title}</div>
                <div className="text-xs text-slate-400 mt-0.5">{stub.source}</div>
                <div className="flex gap-1 mt-2">
                  {stub.suggested_categories?.map((cat: string) => (
                    <span key={cat} className="text-xs bg-orange-500/10 text-orange-400 px-2 py-0.5 rounded-full">{cat}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* STAR Answer Practice */}
      <div className="bg-slate-800/60 border border-slate-700/40 rounded-2xl p-6 space-y-4">
        <h2 className="text-lg font-semibold text-white">{t("STAR Cevap Pratik Alanı")}</h2>
        {(["situation", "task", "action", "result"] as const).map((field) => (
          <div key={field}>
            <label className="text-xs font-mono text-orange-400 uppercase mb-1 block">{field}</label>
            <textarea
              value={answer[field]}
              onChange={(e) => setAnswer({ ...answer, [field]: e.target.value })}
              rows={3}
              placeholder={field === "situation" ? t("Durumu açıklayın...") : field === "task" ? t("Göreviniz neydi?") : field === "action" ? t("Ne yaptınız?") : t("Sonuç ne oldu? (metrik ekleyin!)")}
              className="w-full bg-slate-900/60 border border-slate-700/40 rounded-lg p-3 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-orange-500/50"
            />
          </div>
        ))}
        <button onClick={handleScore}
          className="px-5 py-2.5 bg-orange-600 hover:bg-orange-500 text-white font-medium rounded-xl transition-colors text-sm">
          {t("Cevabı Skorla")}</button>

        {scoreResult && (
          <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-5 space-y-3 mt-4">
            <div className="flex items-center gap-3">
              <div className={`text-3xl font-bold ${scoreResult.overall_score >= 70 ? "text-emerald-400" : scoreResult.overall_score >= 40 ? "text-amber-400" : "text-red-400"}`}>
                {scoreResult.overall_score?.toFixed(0)}
              </div>
              <div className="text-sm text-slate-400">{t("/ 100 puan")}</div>
              {scoreResult.is_complete && <CheckCircle2 className="w-5 h-5 text-emerald-400" />}
            </div>
            <div className="space-y-1">
              {scoreResult.feedback?.map((fb: string, i: number) => (
                <div key={i} className="text-sm text-slate-300">{fb}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
