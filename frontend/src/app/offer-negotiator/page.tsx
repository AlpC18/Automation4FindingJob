"use client";
import { notify } from "@/lib/notify";
import { useLanguage } from "@/lib/i18n";
import { useState } from "react";
import { DollarSign, ShieldAlert, Award, TrendingUp, Copy, Check, Sparkles, RefreshCw, Layers } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function OfferNegotiatorPage() {
  const { translate: t } = useLanguage();
  const [activeTab, setActiveTab] = useState<"evaluate" | "counter" | "objection">("evaluate");
  const [loading, setLoading] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Evaluate Offer State
  const [evalForm, setEvalForm] = useState({
    company: "Shopify",
    title: "Staff Software Engineer",
    base_salary: 145000,
    currency: "USD",
    annual_bonus_pct: 10,
    equity_annual_value: 30000,
    signing_bonus: 15000,
    is_remote: true
  });
  const [evalResult, setEvalResult] = useState<any>(null);

  // Counter Offer State
  const [counterForm, setCounterForm] = useState({
    company: "Shopify",
    title: "Staff Software Engineer",
    offered_base: 145000,
    target_base: 165000,
    currency: "USD",
    primary_leverage: "skill_alignment",
    competing_offer_details: "Parallel discussion with another tech firm offering competitive terms."
  });
  const [counterResult, setCounterResult] = useState<any>(null);

  // Objection Playbook State
  const [selectedObjection, setSelectedObjection] = useState("no_budget");
  const [objectionData, setObjectionData] = useState<any>(null);

  async function handleEvaluate() {
    try {
      setLoading(true);
      const res = await fetchFromApi("/interview/offer/evaluate", {
        method: "POST",
        body: JSON.stringify(evalForm)
      });
      setEvalResult(res);
    } catch (e) {
      notify(t("Teklif değerlendirilemedi."));
    } finally {
      setLoading(false);
    }
  }

  async function handleCounterLetter() {
    try {
      setLoading(true);
      const res = await fetchFromApi("/interview/offer/counter_letter", {
        method: "POST",
        body: JSON.stringify(counterForm)
      });
      setCounterResult(res);
    } catch (e) {
      notify(t("Karşı teklif mektubu oluşturulamadı."));
    } finally {
      setLoading(false);
    }
  }

  async function loadObjection(type: string) {
    setSelectedObjection(type);
    try {
      const res = await fetchFromApi(`/interview/offer/objection_playbook?objection_type=${type}`);
      setObjectionData(res);
    } catch (e) {}
  }

  function copyText(text: string, id: string) {
    navigator.clipboard.writeText(text);
    setCopiedKey(id);
    setTimeout(() => setCopiedKey(null), 2000);
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <DollarSign className="w-7 h-7 text-emerald-400" /> {t("İş teklifi pazarlığı")}</h1>
        <p className="text-slate-400 mt-1">
          {t("Kariyerinizin en yüksek çarpanlı anı: Toplam Tazminat (TC) analizi yapın, profesyonel karşı teklif mektubu üretin ve işe alımcı itirazlarını ustalıkla yönetin.")}</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveTab("evaluate")}
          className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all ${
            activeTab === "evaluate"
              ? "bg-emerald-600/20 text-emerald-300 border border-emerald-500/40"
              : "text-slate-400 hover:text-white"
          }`}
        >
          <TrendingUp className="w-4 h-4 text-emerald-400" />
          {t("1. Teklif Değerlendirme & TC")}</button>
        <button
          onClick={() => setActiveTab("counter")}
          className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all ${
            activeTab === "counter"
              ? "bg-blue-600/20 text-blue-300 border border-blue-500/40"
              : "text-slate-400 hover:text-white"
          }`}
        >
          <Award className="w-4 h-4 text-blue-400" />
          {t("2. Karşı Teklif Mektubu (Counter Letter)")}</button>
        <button
          onClick={() => { setActiveTab("objection"); loadObjection("no_budget"); }}
          className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all ${
            activeTab === "objection"
              ? "bg-amber-600/20 text-amber-300 border border-amber-500/40"
              : "text-slate-400 hover:text-white"
          }`}
        >
          <ShieldAlert className="w-4 h-4 text-amber-400" />
          {t("3. İtiraz Senaryoları & Taktik Playbook")}</button>
      </div>

      {/* Tab 1: Evaluate */}
      {activeTab === "evaluate" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
            <div className="text-xs font-bold text-white">{t("Teklif Parametreleri")}</div>
            <div>
              <label className="text-xs text-slate-400 uppercase font-mono">{t("Şirket")}</label>
              <input
                value={evalForm.company}
                onChange={(e) => setEvalForm({ ...evalForm, company: e.target.value })}
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2 text-xs text-white"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 uppercase font-mono">{t("Baz Yıllık Maaş (Base)")}</label>
              <input
                type="number"
                value={evalForm.base_salary}
                onChange={(e) => setEvalForm({ ...evalForm, base_salary: Number(e.target.value) })}
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2 text-xs text-white"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-slate-400 uppercase font-mono">{t("Yıllık Prim (% Bonus)")}</label>
                <input
                  type="number"
                  value={evalForm.annual_bonus_pct}
                  onChange={(e) => setEvalForm({ ...evalForm, annual_bonus_pct: Number(e.target.value) })}
                  className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2 text-xs text-white"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 uppercase font-mono">{t("Hisse / Yıllık RSU ($)")}</label>
                <input
                  type="number"
                  value={evalForm.equity_annual_value}
                  onChange={(e) => setEvalForm({ ...evalForm, equity_annual_value: Number(e.target.value) })}
                  className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2 text-xs text-white"
                />
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-400 uppercase font-mono">{t("İmza Bonusu (Signing Bonus)")}</label>
              <input
                type="number"
                value={evalForm.signing_bonus}
                onChange={(e) => setEvalForm({ ...evalForm, signing_bonus: Number(e.target.value) })}
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2 text-xs text-white"
              />
            </div>

            <button
              onClick={handleEvaluate}
              disabled={loading}
              className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
            >
              {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <TrendingUp className="w-3.5 h-3.5" />}
              {t("Toplam Paketi Değerlendir")}</button>
          </div>

          <div className="lg:col-span-2 space-y-4">
            {evalResult ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
                    <div className="text-xs text-slate-400">{t("1. Yıl Toplam Paket (TC)")}</div>
                    <div className="text-xl font-bold text-emerald-400 mt-1">
                      {evalResult.currency} {evalResult.first_year_tc?.toLocaleString()}
                    </div>
                  </div>
                  <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
                    <div className="text-xs text-slate-400">{t("Sürekli Yıllık Gelir")}</div>
                    <div className="text-xl font-bold text-white mt-1">
                      {evalResult.currency} {evalResult.ongoing_annual_tc?.toLocaleString()}
                    </div>
                  </div>
                  <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
                    <div className="text-xs text-slate-400">{t("Pazarlık Kaldıraç Skoru")}</div>
                    <div className="text-xl font-bold text-blue-400 mt-1 font-mono">
                      %{evalResult.negotiation_leverage_score}
                    </div>
                  </div>
                </div>

                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-2">
                  <div className="text-xs font-bold text-slate-300">{t("Piyasa Kıyaslama Raporu:")}</div>
                  <div className="text-xs text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 p-3 rounded-xl font-medium">
                    ✓ {evalResult.comparison_verdict}
                  </div>
                  <div className="text-xs text-slate-400 pt-2">
                    <strong>{t("Önerilen Karşı Teklif Hedefi:")}</strong> {evalResult.currency} {evalResult.recommended_counter_target?.toLocaleString()} {t("(Standart %12 stratejik yükseltme)")}</div>
                </div>
              </div>
            ) : (
              <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-12 text-center text-slate-400">
                {t("Sol taraftaki teklif detaylarını girip değerlendirme butonuna basın.")}</div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Counter Offer Letter */}
      {activeTab === "counter" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
            <div className="text-xs font-bold text-white">{t("Karşı Teklif Parametreleri")}</div>
            <div>
              <label className="text-xs text-slate-400 uppercase font-mono">{t("Mevcut Teklif Edilen")}</label>
              <input
                type="number"
                value={counterForm.offered_base}
                onChange={(e) => setCounterForm({ ...counterForm, offered_base: Number(e.target.value) })}
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2 text-xs text-white"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 uppercase font-mono">{t("Talep Edilen Hedef")}</label>
              <input
                type="number"
                value={counterForm.target_base}
                onChange={(e) => setCounterForm({ ...counterForm, target_base: Number(e.target.value) })}
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2 text-xs text-white"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 uppercase font-mono">{t("Pazarlık Kaldıraç Dayanağı")}</label>
              <select
                value={counterForm.primary_leverage}
                onChange={(e) => setCounterForm({ ...counterForm, primary_leverage: e.target.value })}
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg p-2 text-xs text-white"
              >
                <option value="skill_alignment">{t("Doğrudan Kritik Yetenek Uyumu")}</option>
                <option value="competing_offer">{t("Paralel Yarışan Teklif (Competing Offer)")}</option>
                <option value="market_data">{t("Piyasa Benchmark Verileri")}</option>
              </select>
            </div>

            <button
              onClick={handleCounterLetter}
              disabled={loading}
              className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors shadow-lg shadow-blue-600/20"
            >
              {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              {t("Karşı Teklif Mektubu Yaz")}</button>
          </div>

          <div className="lg:col-span-2 space-y-4">
            {counterResult ? (
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-bold text-blue-400 uppercase tracking-wider">
                    {counterResult.email_subject}
                  </div>
                  <button
                    onClick={() => copyText(counterResult.counter_letter_body, "counter")}
                    className="text-xs text-slate-400 hover:text-white flex items-center gap-1"
                  >
                    {copiedKey === "counter" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    {t("Mektubu Kopyala")}</button>
                </div>

                <div className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl text-xs text-slate-200 whitespace-pre-wrap leading-relaxed font-sans">
                  {counterResult.counter_letter_body}
                </div>

                {counterResult.alternative_negotiation_points && (
                  <div className="bg-blue-500/5 border border-blue-500/20 rounded-xl p-4 space-y-2">
                    <div className="text-xs font-bold text-blue-300">
                      {t("Bütçe Katıysa İstenebilecek Alternatif Kozlar:")}</div>
                    {counterResult.alternative_negotiation_points.map((p: string, i: number) => (
                      <div key={i} className="text-xs text-slate-300">{t("•")}{p}</div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-12 text-center text-slate-400">
                {t("Parametreleri girip \"Karşı Teklif Mektubu Yaz\" butonuna basın.")}</div>
            )}
          </div>
        </div>
      )}

      {/* Tab 3: Objection Playbook */}
      {activeTab === "objection" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { id: "no_budget", label: "Bütçemiz Kesinlikle Yok" },
              { id: "internal_equity", label: "Ekip İçi Baremler / Adalet" },
              { id: "take_it_or_leave_it", label: "Nihai Karar (48 Saat)" }
            ].map((btn) => (
              <button
                key={btn.id}
                onClick={() => loadObjection(btn.id)}
                className={`p-3.5 rounded-xl border text-xs font-semibold transition-all text-left ${
                  selectedObjection === btn.id
                    ? "bg-amber-600/20 border-amber-500/40 text-amber-200"
                    : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-white"
                }`}
              >
                {t(btn.label)}
              </button>
            ))}
          </div>

          {objectionData && (
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
              <div className="bg-red-500/10 border border-red-500/20 p-4 rounded-xl text-xs text-red-300">
                <strong>{t("İşe Alımcı İtirazı:")}</strong> "{objectionData.recruiter_objection}"
              </div>
              <div className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl text-xs text-slate-200 leading-relaxed font-sans space-y-2">
                <div className="text-emerald-400 font-bold">{t("Önerilen Sakin & Etkili Yanıtınız:")}</div>
                <div className="italic">"{objectionData.candidate_response}"</div>
              </div>
              <div className="text-xs text-amber-400 bg-amber-500/10 p-3 rounded-lg border border-amber-500/20">
                <strong>{t("Hedef Alternatif Kazanım:")}</strong> {objectionData.alternative_ask}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
