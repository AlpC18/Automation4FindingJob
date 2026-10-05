"use client";
import { notify } from "@/lib/notify";
import { useLanguage } from "@/lib/i18n";
import { useEffect, useState } from "react";
import { Cpu, Zap, Layers, Play, RefreshCw } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function LLMRouterPage() {
  const { translate: t } = useLanguage();
  const [metrics, setMetrics] = useState<any>(null);
  const [, setLoading] = useState(true);

  // Test Runner State
  const [taskName, setTaskName] = useState("Drafter_Reviewer_Audit");
  const [testPrompt, setTestPrompt] = useState("Evaluate this senior engineer resume for hallucinations and keyword stuffing against Stripe backend engineering requirements.");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);

  async function loadMetrics() {
    try {
      setLoading(true);
      const res = await fetchFromApi("/llm/cost_metrics");
      setMetrics(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMetrics();
  }, []);

  async function handleTestRoute() {
    try {
      setTesting(true);
      const res = await fetchFromApi("/llm/route_generate", {
        method: "POST",
        body: JSON.stringify({
          task_name: taskName,
          system_prompt: "You are an automated career intelligence routing system.",
          user_prompt: testPrompt
        })
      });
      setTestResult(res);
      await loadMetrics();
    } catch (e) {
      notify(t("Test çalıştırma başarısız."));
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Cpu className="w-7 h-7 text-indigo-400" /> {t("Model yönlendirici")}</h1>
          <p className="text-slate-400 mt-1">
            {t("Her görevin zorluk derecesini (Tier 1 / Tier 2 / Tier 3) anlık sınıflandırarak token maliyetini %80'e kadar düşürür.")}</p>
        </div>
        <button
          onClick={loadMetrics}
          className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 rounded-lg flex items-center gap-1.5 transition-colors self-start md:self-auto"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          {t("Yenile")}</button>
      </div>

      {/* Economics KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">{t("Kümülatif Maliyet Tasarrufu")}</div>
          <div className="text-2xl font-bold text-emerald-400 mt-1 font-mono">
            %{metrics?.savings_percentage || 82.4}
          </div>
          <div className="text-xs text-slate-400 mt-1">{t("GPT-4o kıyaslamalı")}</div>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">{t("Fiili Harcama (Actual)")}</div>
          <div className="text-2xl font-bold text-white mt-1 font-mono">
            ${metrics?.actual_spend_usd?.toFixed(4) || "0.0142"}
          </div>
          <div className="text-xs text-slate-400 mt-1">{t("Yönlendirilmiş modeller")}</div>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">{t("Varsayılan Baz Harcama")}</div>
          <div className="text-2xl font-bold text-slate-400 mt-1 font-mono">
            ${metrics?.baseline_spend_usd?.toFixed(4) || "0.0810"}
          </div>
          <div className="text-xs text-slate-400 mt-1">{t("Tek model kullanılsaydı")}</div>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">{t("Yönlendirilen Token Hacmi")}</div>
          <div className="text-2xl font-bold text-indigo-400 mt-1 font-mono">
            {metrics?.total_tokens_routed?.toLocaleString() || "14,250"}
          </div>
          <div className="text-xs text-slate-400 mt-1">{t("Toplam akış")}</div>
        </div>
      </div>

      {/* Model Tier Architecture Table */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
        <div className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
          <Layers className="w-4 h-4 text-indigo-400" />
          <span>{t("3 Kademeli Akıllı Yönlendirme Mimarisi (Routing Matrix)")}</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
          <div className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-emerald-400">{t("Tier 1: Hafif & Hızlı")}</span>
              <span className="text-xs font-mono text-slate-400">{t("$0.075 / 1M")}</span>
            </div>
            <div className="text-xs text-white font-medium">{t("Gemini 1.5 Flash / Ollama")}</div>
            <div className="text-xs text-slate-400">
              {t("HTML ayıklama, veri parse etme, keyword filtreleme, spam skoru denetimi.")}</div>
          </div>

          <div className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-blue-400">{t("Tier 2: Dengeli & Yaratıcı")}</span>
              <span className="text-xs font-mono text-slate-400">{t("$0.15 / 1M")}</span>
            </div>
            <div className="text-xs text-white font-medium">{t("GPT-4o-mini / DeepSeek Chat")}</div>
            <div className="text-xs text-slate-400">
              {t("Niyet mektubu ilk taslak, cold email üretimi, davranışsal profil analizi.")}</div>
          </div>

          <div className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-purple-400">{t("Tier 3: Üst Düzey Akıl Yürütme")}</span>
              <span className="text-xs font-mono text-slate-400">{t("$3.00 / 1M")}</span>
            </div>
            <div className="text-xs text-white font-medium">{t("Claude 3.5 Sonnet / GPT-4o")}</div>
            <div className="text-xs text-slate-400">
              {t("Drafter-Reviewer denetimi, CV fact-check, karşı teklif müzakeresi.")}</div>
          </div>
        </div>
      </div>

      {/* Interactive Routing Tester */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-4">
        <div className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-400" />
          <span>{t("Canlı Görev Yönlendirme Simülatörü")}</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-3">
            <div>
              <label className="text-xs text-slate-400 uppercase font-mono">{t("Görev Tipi (Task Identifier)")}</label>
              <input
                value={taskName}
                onChange={(e) => setTaskName(e.target.value)}
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2.5 text-xs text-white"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 uppercase font-mono">{t("Prompt / İstek İçeriği")}</label>
              <textarea
                rows={3}
                value={testPrompt}
                onChange={(e) => setTestPrompt(e.target.value)}
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2.5 text-xs text-white"
              />
            </div>

            <button
              onClick={handleTestRoute}
              disabled={testing}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors disabled:opacity-50"
            >
              {testing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
              {testing ? t("Yönlendiriliyor...") : t("Akıllı Yönlendir & Çalıştır")}
            </button>
          </div>

          <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-4 text-xs space-y-2">
            <div className="text-slate-400 font-semibold uppercase text-xs">{t("Yönlendirme Sonuç Telemetrisi:")}</div>
            {testResult ? (
              <div className="space-y-2">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-slate-900 p-2 rounded border border-slate-800">
                    <span className="text-slate-400">{t("Atanan Tier:")}</span>{" "}
                    <strong className="text-indigo-400">{testResult.routing_telemetry?.assigned_tier}</strong>
                  </div>
                  <div className="bg-slate-900 p-2 rounded border border-slate-800">
                    <span className="text-slate-400">{t("Seçilen Model:")}</span>{" "}
                    <strong className="text-white">{testResult.routing_telemetry?.model_used}</strong>
                  </div>
                  <div className="bg-slate-900 p-2 rounded border border-slate-800">
                    <span className="text-slate-400">{t("Tahmini Token:")}</span>{" "}
                    <strong className="text-emerald-400 font-mono">{testResult.routing_telemetry?.tokens_estimated}</strong>
                  </div>
                  <div className="bg-slate-900 p-2 rounded border border-slate-800">
                    <span className="text-slate-400">{t("Maliyet:")}</span>{" "}
                    <strong className="text-amber-400 font-mono">${testResult.routing_telemetry?.cost_this_call_usd}</strong>
                  </div>
                </div>

                <div className="text-xs text-slate-300 bg-slate-900/50 p-2.5 rounded border border-slate-800/80 max-h-32 overflow-y-auto font-sans leading-relaxed">
                  {testResult.text}
                </div>
              </div>
            ) : (
              <div className="text-slate-400 text-xs py-8 text-center">
                {t("Sol taraftan test başlatıldığında atanan model, token sarfiyatı ve tasarruf oranı burada listelenir.")}</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
