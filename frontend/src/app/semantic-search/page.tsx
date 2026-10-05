"use client";
import { notify } from "@/lib/notify";
import { useLanguage } from "@/lib/i18n";
import { useEffect, useState } from "react";
import { Sparkles, Search, Database, TrendingUp, ArrowRight, RefreshCw, Layers } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function SemanticSearchPage() {
  const { translate: t } = useLanguage();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [trends, setTrends] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [indexStats, setIndexStats] = useState<any>(null);

  useEffect(() => {
    fetchFromApi("/rank/semantic/trends").then(setTrends).catch(() => {});
  }, []);

  async function handleIndex() {
    try {
      setIndexing(true);
      const res = await fetchFromApi("/rank/semantic/index", { method: "POST" });
      setIndexStats(res);
      notify(t("ChromaDB vector indexing complete: {count} job vectors added.", { count: res.indexed_count }));
    } catch (e) {
      notify(t("İndeksleme sırasında hata oluştu."));
    } finally {
      setIndexing(false);
    }
  }

  async function handleSearch(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    try {
      setLoading(true);
      const res = await fetchFromApi("/rank/semantic/search", {
        method: "POST",
        body: JSON.stringify({ query, limit: 12 })
      });
      setResults(res.results || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleFindSimilar(jobKey: string) {
    try {
      setLoading(true);
      const res = await fetchFromApi("/rank/semantic/similar", {
        method: "POST",
        body: JSON.stringify({ job_key: jobKey, limit: 6 })
      });
      setResults(res.results || []);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Sparkles className="w-7 h-7 text-indigo-400" /> {t("Anlamsal arama")}</h1>
          <p className="text-slate-400 mt-1">
            {t("ChromaDB Cosine Similarity ile doğal dilde arama yapın, \"buna benzer ilanları bul\" fonksiyonunu kullanın.")}</p>
        </div>
        <button
          onClick={handleIndex}
          disabled={indexing}
          className="px-4 py-2 bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 border border-indigo-500/40 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all disabled:opacity-50"
        >
          <Database className={`w-3.5 h-3.5 ${indexing ? "animate-spin" : ""}`} />
          {indexing ? t("Vektörler İndeksleniyor...") : t("ChromaDB İndeksini Güncelle")}
        </button>
      </div>

      {/* Natural Language Search Input */}
      <form onSubmit={handleSearch} className="relative">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("Örn: 'Avrupa saat diliminde, Docker ve Python kullanan, otonom agent projeleri geliştiren roller'...")}
          className="w-full bg-slate-900/80 border border-slate-700/80 rounded-2xl px-5 py-4 pl-12 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500/60 shadow-xl"
        />
        <Search className="w-5 h-5 text-slate-400 absolute left-4 top-1/2 -translate-y-1/2" />
        <button
          type="submit"
          disabled={loading}
          className="absolute right-3 top-1/2 -translate-y-1/2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold transition-colors disabled:opacity-50"
        >
          {loading ? t("Aranıyor...") : t("Vektör Ara")}
        </button>
      </form>

      {/* Market Trend Bar */}
      {trends && trends.top_in_demand_skills && (
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-indigo-300">
            <TrendingUp className="w-4 h-4" />
            <span>{t("Piyasa Talep Hızı (En Çok İstenen Teknolojiler):")}</span>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            {trends.top_in_demand_skills.map((item: any) => (
              <span
                key={item.skill}
                className="text-xs bg-slate-800/80 border border-slate-700 px-3 py-1 rounded-lg text-slate-300 flex items-center gap-2"
              >
                <span>{item.skill}</span>
                <span className="text-xs font-mono text-indigo-400 font-bold">%{item.percentage}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Results */}
      <div className="space-y-3">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          {results.length > 0 ? `Semantik Eşleşmeler (${results.length})` : t("Arama Yapın veya Trendlere Göz Atın")}
        </div>

        {results.map((res: any) => (
          <div
            key={res.job_key}
            className="bg-slate-900/60 border border-slate-800 hover:border-indigo-500/40 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 transition-all"
          >
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-white">{res.title}</span>
                {res.semantic_similarity && (
                  <span className="text-xs font-mono px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
                    %{res.semantic_similarity} {t("Benzerlik")}</span>
                )}
              </div>
              <div className="text-xs text-slate-400 mt-1">
                <strong className="text-blue-400">{res.company}</strong> {t("•")}{res.location || "Uzaktan"}
              </div>
            </div>

            <button
              onClick={() => handleFindSimilar(res.job_key)}
              className="text-xs text-slate-400 hover:text-indigo-300 flex items-center gap-1.5 transition-colors self-start md:self-auto"
            >
              <Layers className="w-3.5 h-3.5" />
              <span>{t("Buna Benzer İlanları Bul")}</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
