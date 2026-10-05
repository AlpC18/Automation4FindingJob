"use client";
import { notify } from "@/lib/notify";
import { useLanguage } from "@/lib/i18n";
import { useState } from "react";
import { UserCheck, Github, Linkedin, Copy, Check, Sparkles, RefreshCw } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function ProfileOptimizerPage() {
  const { translate: t } = useLanguage();
  const [activeTab, setActiveTab] = useState<"linkedin" | "github">("linkedin");
  const [loading, setLoading] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState<string | null>(null);

  // LinkedIn State
  const [targetRole, setTargetRole] = useState("");
  const [linkedinData, setLinkedinData] = useState<any>(null);

  // GitHub State
  const [githubUsername, setGithubUsername] = useState("alperencihan");
  const [githubData, setGithubData] = useState<any>(null);

  async function handleOptimizeLinkedIn() {
    try {
      setLoading(true);
      const res = await fetchFromApi("/setup/optimize/linkedin", {
        method: "POST",
        body: JSON.stringify({ target_role: targetRole || undefined })
      });
      setLinkedinData(res);
    } catch (e) {
      notify(t("LinkedIn optimizasyonu sırasında hata oluştu."));
    } finally {
      setLoading(false);
    }
  }

  async function handleAuditGitHub() {
    try {
      setLoading(true);
      const res = await fetchFromApi("/setup/optimize/github", {
        method: "POST",
        body: JSON.stringify({ github_username: githubUsername })
      });
      setGithubData(res);
    } catch (e) {
      notify(t("GitHub denetimi sırasında hata oluştu."));
    } finally {
      setLoading(false);
    }
  }

  function copyToClipboard(text: string, id: string) {
    navigator.clipboard.writeText(text);
    setCopiedIndex(id);
    setTimeout(() => setCopiedIndex(null), 2000);
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <UserCheck className="w-7 h-7 text-blue-400" /> {t("Profil optimizasyonu")}</h1>
        <p className="text-slate-400 mt-1">
          {t("Tersine İşe Alım (Reverse Recruitment): İşe alımcıların size doğrudan ulaşmasını sağlayacak profil yükseltmeleri.")}</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveTab("linkedin")}
          className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all ${
            activeTab === "linkedin"
              ? "bg-blue-600/20 text-blue-300 border border-blue-500/40"
              : "text-slate-400 hover:text-white"
          }`}
        >
          <Linkedin className="w-4 h-4 text-blue-400" />
          {t("LinkedIn Headline & Hakkımda")}</button>
        <button
          onClick={() => setActiveTab("github")}
          className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all ${
            activeTab === "github"
              ? "bg-purple-600/20 text-purple-300 border border-purple-500/40"
              : "text-slate-400 hover:text-white"
          }`}
        >
          <Github className="w-4 h-4 text-purple-400" />
          {t("GitHub Portföy & README")}</button>
      </div>

      {/* LinkedIn Tab Content */}
      {activeTab === "linkedin" && (
        <div className="space-y-5">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 flex flex-col md:flex-row gap-3">
            <input
              value={targetRole}
              onChange={(e) => setTargetRole(e.target.value)}
              placeholder={t("Hedef Pozisyon (Örn: Senior Backend & AI Agent Architect)...")}
              className="flex-1 bg-slate-950/80 border border-slate-700/80 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500/60"
            />
            <button
              onClick={handleOptimizeLinkedIn}
              disabled={loading}
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-50"
            >
              {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              {loading ? t("Üretiliyor...") : "LinkedIn'i Optimize Et"}
            </button>
          </div>

          {linkedinData && (
            <div className="space-y-4">
              {/* Headlines */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
                <div className="text-xs font-bold text-blue-400 uppercase tracking-wider">
                  {t("Önerilen 3 Güçlü Başlık (Headline)")}</div>
                <div className="space-y-2">
                  {(linkedinData.headlines || []).map((h: string, i: number) => (
                    <div
                      key={i}
                      className="bg-slate-950/80 border border-slate-800 p-3.5 rounded-xl flex items-center justify-between gap-3 text-xs text-slate-200"
                    >
                      <span className="font-mono">{h}</span>
                      <button
                        onClick={() => copyToClipboard(h, `h-${i}`)}
                        className="text-slate-400 hover:text-white p-1"
                        title={t("Kopyala")}
                      >
                        {copiedIndex === `h-${i}` ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* About Section */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-bold text-blue-400 uppercase tracking-wider">
                    {t("Önerilen 'Hakkımda' (About) Bölümü")}</div>
                  <button
                    onClick={() => copyToClipboard(linkedinData.about_section || "", "about")}
                    className="text-xs text-slate-400 hover:text-white flex items-center gap-1"
                  >
                    {copiedIndex === "about" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    {t("Metni Kopyala")}</button>
                </div>
                <div className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
                  {linkedinData.about_section}
                </div>
              </div>

              {/* Tips */}
              {linkedinData.profile_tips && (
                <div className="bg-blue-500/5 border border-blue-500/20 rounded-2xl p-4 space-y-2">
                  <div className="text-xs font-bold text-blue-300">{t("İşe Alımcı Görünürlük Tavsiyeleri:")}</div>
                  <div className="space-y-1">
                    {linkedinData.profile_tips.map((tip: string, i: number) => (
                      <div key={i} className="text-xs text-slate-300">{t("•")}{tip}</div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* GitHub Tab Content */}
      {activeTab === "github" && (
        <div className="space-y-5">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 flex flex-col md:flex-row gap-3">
            <input
              value={githubUsername}
              onChange={(e) => setGithubUsername(e.target.value)}
              placeholder={t("GitHub Kullanıcı Adı...")}
              className="flex-1 bg-slate-950/80 border border-slate-700/80 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/60"
            />
            <button
              onClick={handleAuditGitHub}
              disabled={loading}
              className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-50"
            >
              {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Github className="w-3.5 h-3.5" />}
              {loading ? "Denetleniyor..." : t("GitHub'ı Denetle")}
            </button>
          </div>

          {githubData && (
            <div className="space-y-4">
              {/* Profile README Template */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-bold text-purple-400 uppercase tracking-wider">
                    {t("Kişisel Profil README.md Şablonu")}</div>
                  <button
                    onClick={() => copyToClipboard(githubData.readme_template || "", "readme")}
                    className="text-xs text-slate-400 hover:text-white flex items-center gap-1"
                  >
                    {copiedIndex === "readme" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    {t("README'yi Kopyala")}</button>
                </div>
                <div className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl text-xs font-mono text-slate-300 whitespace-pre-wrap leading-relaxed overflow-x-auto">
                  {githubData.readme_template}
                </div>
              </div>

              {/* Repo Hygiene Checklist */}
              {githubData.repository_health_checklist && (
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-2">
                  <div className="text-xs font-bold text-purple-400 uppercase tracking-wider">
                    {t("Repo Hijyen Kontrol Listesi (Mülakat Hazırlığı)")}</div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
                    {githubData.repository_health_checklist.map((item: string, i: number) => (
                      <div key={i} className="text-xs text-slate-300 bg-slate-950/60 p-3 rounded-xl border border-slate-800 flex items-center gap-2">
                        <span className="text-emerald-400 font-bold">✓</span> {item}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
