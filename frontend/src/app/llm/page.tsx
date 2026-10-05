"use client";
import dynamic from "next/dynamic";
import PageTabs from "@/components/PageTabs";
import { useLanguage } from "@/lib/i18n";

import { useEffect, useState } from "react";
import {
  Cpu,
  CheckCircle2,
  AlertCircle,
  Zap,
  RefreshCw,
  Sparkles,
  ShieldCheck,
  Server,
  Key,
  Layers,
  ArrowRight
} from "lucide-react";
import { fetchFromApi } from "@/lib/api";

function LLMHubPage() {
  const { translate: t } = useLanguage();
  const [providersData, setProvidersData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeProvider, setActiveProvider] = useState<string>("auto");
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, any>>({});
  const [switching, setSwitching] = useState(false);
  const [credentialStatus, setCredentialStatus] = useState<Record<string, any>>({});
  const [credentialInputs, setCredentialInputs] = useState<Record<string, string>>({});
  const [credentialBusy, setCredentialBusy] = useState<string | null>(null);
  const [credentialMessage, setCredentialMessage] = useState<Record<string, string>>({});

  // Playground state
  const [promptText, setPromptText] = useState(
    "Write a concise opening paragraph for a Senior AI Systems Engineer role applying to a fast-growing tech startup."
  );
  const [playgroundProvider, setPlaygroundProvider] = useState("auto");
  const [generating, setGenerating] = useState(false);
  const [generatedResult, setGeneratedResult] = useState<any>(null);

  async function loadProviders() {
    try {
      setLoading(true);
      const res = await fetchFromApi("/llm/providers");
      setProvidersData(res);
      setActiveProvider(res.active_provider || "auto");
      const credentials = await fetchFromApi("/llm/credentials");
      setCredentialStatus(Object.fromEntries((credentials.providers || []).map((item: any) => [item.provider, item])));
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function saveCredential(provider: string) {
    const apiKey = credentialInputs[provider]?.trim();
    if (!apiKey) {
      setCredentialMessage((current) => ({ ...current, [provider]: "Önce API anahtarını gir." }));
      return;
    }
    try {
      setCredentialBusy(provider);
      setCredentialMessage((current) => ({ ...current, [provider]: "" }));
      await fetchFromApi("/llm/credentials", {
        method: "PUT",
        body: JSON.stringify({ provider, api_key: apiKey }),
      });
      setCredentialInputs((current) => ({ ...current, [provider]: "" }));
      setCredentialMessage((current) => ({ ...current, [provider]: "Anahtar şifreli kaydedildi." }));
      await loadProviders();
    } catch (error: any) {
      setCredentialMessage((current) => ({ ...current, [provider]: error.message || "Anahtar kaydedilemedi." }));
    } finally {
      setCredentialBusy(null);
    }
  }

  async function deleteCredential(provider: string) {
    try {
      setCredentialBusy(provider);
      await fetchFromApi(`/llm/credentials/${provider}`, { method: "DELETE" });
      setCredentialMessage((current) => ({ ...current, [provider]: "Kayıtlı anahtar silindi." }));
      await loadProviders();
    } catch (error: any) {
      setCredentialMessage((current) => ({ ...current, [provider]: error.message || "Anahtar silinemedi." }));
    } finally {
      setCredentialBusy(null);
    }
  }

  useEffect(() => {
    loadProviders();
  }, []);

  async function handleTestConnection(providerId: string) {
    try {
      setTestingId(providerId);
      const res = await fetchFromApi("/llm/test_connection", {
        method: "POST",
        body: JSON.stringify({ provider: providerId })
      });
      setTestResults((prev) => ({ ...prev, [providerId]: res }));
    } catch (e: any) {
      setTestResults((prev) => ({
        ...prev,
        [providerId]: { status: "ERROR", message: e.message || "Bağlantı hatası", latency_ms: 0 }
      }));
    } finally {
      setTestingId(null);
    }
  }

  async function handleSelectActiveProvider(providerId: string, modelName?: string) {
    try {
      setSwitching(true);
      await fetchFromApi("/llm/set_provider", {
        method: "POST",
        body: JSON.stringify({ provider: providerId, model: modelName })
      });
      setActiveProvider(providerId);
      if (modelName) setSelectedModel(modelName);
      await loadProviders();
    } finally {
      setSwitching(false);
    }
  }

  async function handleTestGenerate() {
    if (!promptText.trim()) return;
    try {
      setGenerating(true);
      const res = await fetchFromApi("/llm/generate", {
        method: "POST",
        body: JSON.stringify({
          system_prompt: "You are an expert career consultant and high-precision technical writer.",
          user_prompt: promptText,
          provider: playgroundProvider
        })
      });
      setGeneratedResult(res);
    } finally {
      setGenerating(false);
    }
  }

  const providers = providersData?.providers || [];

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Cpu className="w-6 h-6 text-blue-500" />
            {t("Yapay zekâ ve API anahtarları")}</h1>
          <p className="text-xs text-slate-400 mt-1">
            {t("Sağlayıcı anahtarlarını güvenle kaydedin; modelleri deneyin, bağlantıyı test edin ve aktif sağlayıcıyı seçin.")}</p>
        </div>

        <button
          onClick={loadProviders}
          disabled={loading}
          className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold px-4 py-2 rounded-xl transition border border-slate-700 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          {t("Durumu Yenile")}</button>
      </div>

      {/* Active Provider Banner */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-blue-950/40 via-indigo-950/20 to-slate-900 border border-blue-500/20 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
            <Zap className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase tracking-wider font-semibold">{t("Aktif Üretim Modeli")}</div>
            <div className="text-sm font-bold text-white flex items-center gap-2">
              <span className="capitalize">{activeProvider === "auto" ? "Otomatik Tespit (Auto)" : activeProvider}</span>
              <span className="text-xs bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-500/20 font-mono">
                {providersData?.effective_provider?.toUpperCase()}
              </span>
            </div>
          </div>
        </div>

        <div className="text-xs text-slate-400 flex items-center gap-2">
          <span>{t("Anti-AI Humanizer Filtresi:")}</span>
          <span className="text-emerald-400 font-semibold flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5" /> {t("7/24 Aktif & Otomatik")}</span>
        </div>
      </div>

      {/* Providers Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {providers.map((p: any) => {
          const isSelected = activeProvider.toLowerCase() === p.id.toLowerCase();
          const testRes = testResults[p.id];
          const isTesting = testingId === p.id;

          return (
            <div
              key={p.id}
              className={`p-5 rounded-2xl bg-[#0e1524] border transition flex flex-col justify-between space-y-4 ${
                isSelected
                  ? "border-blue-500/80 shadow-lg shadow-blue-500/10"
                  : "border-slate-800/80 hover:border-slate-700"
              }`}
            >
              <div>
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                      {p.name}
                      {isSelected && (
                        <span className="text-xs bg-blue-600 text-white px-2 py-0.5 rounded-full font-sans uppercase font-semibold">
                          {t("Aktif")}</span>
                      )}
                    </h3>
                    <div className="text-xs text-slate-400 font-mono mt-0.5">{p.type}</div>
                  </div>

                  {p.is_configured ? (
                    <span className="text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full font-mono flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> {t("Hazır")}</span>
                  ) : (
                    <span className="text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded-full font-mono flex items-center gap-1">
                      <Key className="w-3 h-3" /> {t("Key Eksik")}</span>
                  )}
                </div>

                {/* Model Selector / Display */}
                <div className="mt-3 p-2.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1.5">
                  <div className="text-xs text-slate-400 font-semibold uppercase">{t("Varsayılan Model:")}</div>
                  <div className="text-xs font-mono text-blue-400 font-semibold">{p.model}</div>
                  {p.available_models && p.available_models.length > 1 && (
                    <div className="flex flex-wrap gap-1 pt-1">
                      {p.available_models.map((m: string) => (
                        <button
                          key={m}
                          onClick={() => handleSelectActiveProvider(p.id, m)}
                          className={`text-xs px-1.5 py-0.5 rounded transition font-mono ${
                            p.model === m
                              ? "bg-blue-600 text-white"
                              : "bg-slate-800 text-slate-300 hover:text-white"
                          }`}
                        >
                          {m}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {["openai", "gemini", "anthropic", "deepseek", "custom"].includes(p.id) && (
                  <div className="mt-3 rounded-xl border border-slate-800 bg-slate-900/40 p-3 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <label htmlFor={`api-key-${p.id}`} className="text-xs font-semibold text-slate-200">{t("API anahtarı")}</label>
                      <span className="text-xs text-slate-400">
                        {credentialStatus[p.id]?.has_saved_key ? t("Şifreli kayıtlı") : credentialStatus[p.id]?.managed_by_environment ? t(".env üzerinden") : t("Henüz eklenmedi")}
                      </span>
                    </div>
                    <input
                      id={`api-key-${p.id}`}
                      type="password"
                      autoComplete="new-password"
                      value={credentialInputs[p.id] || ""}
                      onChange={(event) => setCredentialInputs((current) => ({ ...current, [p.id]: event.target.value }))}
                      placeholder={credentialStatus[p.id]?.is_configured ? t("Değiştirmek için yeni anahtar gir") : `${p.name} API anahtarını yapıştır`}
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100 outline-none focus:border-blue-500"
                    />
                    <div className="flex items-center gap-2">
                      <button type="button" onClick={() => saveCredential(p.id)} disabled={credentialBusy === p.id} className="flex-1 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-blue-500 disabled:opacity-50">
                        {credentialBusy === p.id ? "Kaydediliyor…" : t("Anahtarı güvenle kaydet")}
                      </button>
                      {credentialStatus[p.id]?.has_saved_key && (
                        <button type="button" onClick={() => deleteCredential(p.id)} disabled={credentialBusy === p.id} className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800 disabled:opacity-50">{t("Sil")}</button>
                      )}
                    </div>
                    {credentialMessage[p.id] && <p role="status" className="text-xs text-slate-300">{credentialMessage[p.id]}</p>}
                  </div>
                )}

                {/* Connection Ping Feedback */}
                {testRes && (
                  <div
                    className={`mt-3 p-2.5 rounded-xl text-xs border flex items-center justify-between ${
                      testRes.status === "SUCCESS"
                        ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                        : "bg-rose-500/10 border-rose-500/20 text-rose-300"
                    }`}
                  >
                    <span>{testRes.message}</span>
                    {testRes.latency_ms > 0 && (
                      <span className="font-mono font-bold text-xs">{testRes.latency_ms}ms</span>
                    )}
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 pt-2 border-t border-slate-800/80">
                <button
                  type="button"
                  onClick={() => handleTestConnection(p.id)}
                  disabled={isTesting}
                  className="flex-1 bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white text-xs font-medium py-1.5 px-3 rounded-lg border border-slate-700/80 transition flex items-center justify-center gap-1 disabled:opacity-50"
                >
                  <Zap className={`w-3 h-3 ${isTesting ? "animate-spin text-amber-400" : "text-amber-400"}`} />
                  {isTesting ? "Ping..." : t("Bağlantıyı Test Et")}
                </button>

                <button
                  type="button"
                  onClick={() => handleSelectActiveProvider(p.id)}
                  disabled={isSelected || switching}
                  className={`text-xs font-semibold py-1.5 px-3 rounded-lg transition ${
                    isSelected
                      ? "bg-slate-800 text-slate-400 cursor-default"
                      : "bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-600/20"
                  }`}
                >
                  {isSelected ? t("Seçili") : "Aktif Yap"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Live AI Playground with Anti-AI Texture Analyzer */}
      <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-indigo-400" />
              {t("Canlı LLM & Anti-AI Test Laboratuvarı (Playground)")}</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              {t("Seçtiğiniz modelden anlık metin üretin; sistem yasaklı kelimeleri ve insansı dokuyu (human texture) otomatik ölçsün.")}</p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400 font-medium">{t("Test Sağlayıcısı:")}</span>
            <select
              value={playgroundProvider}
              onChange={(e) => setPlaygroundProvider(e.target.value)}
              className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
            >
              <option value="auto">{t("Auto (Varsayılan)")}</option>
              <option value="openai">{t("OpenAI (gpt-4o)")}</option>
              <option value="gemini">{t("Google Gemini (1.5-flash)")}</option>
              <option value="anthropic">{t("Anthropic Claude (3.5 Sonnet)")}</option>
              <option value="deepseek">{t("DeepSeek (chat)")}</option>
              <option value="ollama">{t("Yerel Ollama (llama3)")}</option>
              <option value="local_fallback">{t("Fallback Hibrit Motor")}</option>
            </select>
          </div>
        </div>

        <textarea
          value={promptText}
          onChange={(e) => setPromptText(e.target.value)}
          placeholder={t("İstediğiniz test promptunu yazın...")}
          className="w-full h-24 bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 leading-relaxed focus:outline-none focus:border-indigo-500"
        />

        <div className="flex justify-end">
          <button
            onClick={handleTestGenerate}
            disabled={generating || !promptText.trim()}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-5 py-2.5 rounded-xl transition shadow-lg shadow-indigo-600/20 disabled:opacity-50"
          >
            <Sparkles className={`w-4 h-4 ${generating ? "animate-spin" : ""}`} />
            {generating ? t("Model Üretiyor & Humanize Ediliyor...") : t("Metin Üret & İnsansılaştır")}
          </button>
        </div>

        {/* Playground Result Display */}
        {generatedResult && (
          <div className="mt-4 p-5 rounded-xl bg-slate-950 border border-slate-800 space-y-4">
            {/* Texture Metrics Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-center">
                <div className="text-xs text-slate-400">{t("Kullanılan Motor")}</div>
                <div className="text-xs font-bold text-white truncate mt-0.5">
                  {generatedResult.provider_used}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-center">
                <div className="text-xs text-slate-400">{t("İnsansı Doku Puanı")}</div>
                <div className="text-sm font-bold text-emerald-400 font-mono mt-0.5">
                  %{generatedResult.human_texture_score}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-center">
                <div className="text-xs text-slate-400">{t("Burstiness (Ritim)")}</div>
                <div className="text-sm font-bold text-indigo-400 font-mono mt-0.5">
                  {generatedResult.burstiness}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-center">
                <div className="text-xs text-slate-400">{t("Doğrulama Durumu")}</div>
                <div className="text-xs font-bold text-emerald-400 mt-0.5 flex items-center justify-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> {t("İnsan Seviyesi")}</div>
              </div>
            </div>

            {/* Clean Output */}
            <div className="space-y-1.5">
              <div className="text-xs font-semibold text-slate-300">{t("Temizlenmiş & İnsansılaştırılmış Çıktı:")}</div>
              <pre className="p-4 rounded-xl bg-[#090d16] border border-slate-800 text-xs font-sans text-slate-200 whitespace-pre-wrap leading-relaxed">
                {generatedResult.text}
              </pre>
            </div>
          </div>
        )}
      </div>

      {/* Credential security note */}
      <div className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 text-xs text-slate-400 space-y-2">
        <div className="font-semibold text-white flex items-center gap-1.5">
          <Key className="w-4 h-4 text-blue-400" />
          {t("API anahtarı güvenliği")}</div>
        <p>{t("Bu sayfadan eklenen anahtarlar veritabanına şifreli kaydedilir; daha sonra arayüzden tekrar okunmaz. Yerel geliştirmede şifreleme anahtarı uygulama tarafından özel izinli dosyada oluşturulur. Üretimde")}<code className="font-mono">APP_ENCRYPTION_KEY</code> {t("değerini sunucu ortamında tanımlayın.")}</p>
        <p className="text-xs text-slate-400">{t("Anahtar eklemeden de yerel kural motorunu kullanabilirsiniz. Bulut sağlayıcısı kullanımı kendi sağlayıcınızın ücret ve kullanım koşullarına tabidir.")}</p>
      </div>
    </div>
  );
}

// Loaded only when their tab is opened, so this page stays as light as before.
const LLMRouterPage = dynamic(() => import("../llm-router/page"));

// Related screens live here as tabs so the menu stays short; each still has its own route.
const TABS = [
    { label: "Yapay zekâ / API anahtarları", Component: LLMHubPage },
    { label: "Model yönlendirici", Component: LLMRouterPage },
];

export default function LLMHubPageWithTabs() {
  return <PageTabs tabs={TABS} />;
}
