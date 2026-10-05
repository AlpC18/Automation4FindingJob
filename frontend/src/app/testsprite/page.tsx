"use client";
import { useLanguage } from "@/lib/i18n";

import { useState } from "react";
import {
  Sparkles,
  CheckCircle2,
  XCircle,
  Play,
  RefreshCw,
  Cpu
} from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function TestSpritePage() {
  const { translate: t } = useLanguage();
  const [suiteResults, setSuiteResults] = useState<any>(null);
  const [running, setRunning] = useState(false);

  async function handleRunTests() {
    try {
      setRunning(true);
      const res = await fetchFromApi("/testsprite/run", { method: "POST" });
      setSuiteResults(res);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-blue-500" />
            {t("Test merkezi")}</h1>
          <p className="text-xs text-slate-400 mt-1">
            {t("Uçtan uca mimarinin (Anti-AI Humanizer, Ghost Job, X-Ray Dork, Form Memory, Rate Limiter) otomatik doğrulanması ve Auto-Fix onarımı.")}</p>
        </div>

        <button
          onClick={handleRunTests}
          disabled={running}
          className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold text-xs px-5 py-2.5 rounded-xl transition shadow-lg shadow-blue-600/20 disabled:opacity-50"
        >
          {running ? (
            <>
              <RefreshCw className="w-3.5 h-3.5 animate-spin" /> {t("Testler Koşuluyor...")}</>
          ) : (
            <>
              <Play className="w-3.5 h-3.5" /> {t("Tüm E2E Testleri Başlat")}</>
          )}
        </button>
      </div>

      {/* Overview Cards */}
      {suiteResults && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-2xl bg-[#0e1524] border border-slate-800">
            <div className="text-xs text-slate-400">{t("Genel Test Durumu")}</div>
            <div className={`text-xl font-bold mt-1 ${suiteResults.suite_status === 'PASSED' ? 'text-emerald-400' : 'text-rose-400'}`}>
              {suiteResults.suite_status === 'PASSED' ? t("✓ TÜMÜ GEÇTİ") : t("✗ BAŞARISIZ")}
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-[#0e1524] border border-slate-800">
            <div className="text-xs text-slate-400">{t("Başarılı Testler")}</div>
            <div className="text-xl font-bold text-emerald-400 mt-1">
              {suiteResults.passed_tests} / {suiteResults.total_tests}
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-[#0e1524] border border-slate-800">
            <div className="text-xs text-slate-400">{t("Hatalı Testler")}</div>
            <div className="text-xl font-bold text-slate-300 mt-1">
              {suiteResults.failed_tests}
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-[#0e1524] border border-slate-800">
            <div className="text-xs text-slate-400">{t("Otonom Düzeltme (Auto-Fix)")}</div>
            <div className="text-xl font-bold text-indigo-400 mt-1 flex items-center gap-1.5">
              <Cpu className="w-4 h-4" /> {t("Devrede")}</div>
          </div>
        </div>
      )}

      {/* Tests Results List */}
      <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
        <h2 className="text-sm font-semibold text-white">{t("Test Senaryoları & Doğrulama Ayrıntıları")}</h2>

        {!suiteResults ? (
          <div className="p-8 text-center text-xs text-slate-400 bg-slate-900/40 rounded-xl">
            {t("Yukarıdaki \"Tüm E2E Testleri Başlat\" butonuna tıklayarak TestSprite test paketini otonom olarak çalıştırabilirsiniz.")}</div>
        ) : (
          <div className="space-y-3">
            {suiteResults.results?.map((t: any, idx: number) => (
              <div
                key={idx}
                className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    {t.passed ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    ) : (
                      <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                    )}
                    <span className="font-bold text-white">{t.test_name}</span>
                  </div>
                  <div className="text-xs text-slate-400 pl-6 font-mono">
                    {t.details}
                  </div>
                </div>

                <span className={`text-xs px-2.5 py-1 rounded-full font-mono font-semibold self-start md:self-center ${t.passed ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}`}>
                  {t.passed ? "PASSED" : "FAILED"}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
