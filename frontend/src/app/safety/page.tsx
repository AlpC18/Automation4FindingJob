"use client";
import { useLanguage } from "@/lib/i18n";

import { useEffect, useState } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  Sliders,
  Server,
  Lock,
  Globe,
  CheckCircle2,
  RefreshCw
} from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function SafetyPage() {
  const { translate: t } = useLanguage();
  const [health, setHealth] = useState<any>({});
  const [loading, setLoading] = useState(true);

  // LinkedIn Session Handshake State
  const [sessionStatus, setSessionStatus] = useState<any>(null);
  const [loadingSession, setLoadingSession] = useState(false);
  const [manualJson, setManualJson] = useState("");
  const [savingCookies, setSavingCookies] = useState(false);
  const [cookieFeedback, setCookieFeedback] = useState<string | null>(null);

  async function loadHealth() {
    try {
      setLoading(true);
      const res = await fetchFromApi("/scrape/health");
      setHealth(res || {});
    } finally {
      setLoading(false);
    }
  }

  async function loadSessionStatus() {
    try {
      setLoadingSession(true);
      const res = await fetchFromApi("/scrape/linkedin_session_status");
      setSessionStatus(res || null);
    } catch (e) {
      setSessionStatus(null);
    } finally {
      setLoadingSession(false);
    }
  }

  async function handleSaveManualCookies() {
    try {
      setSavingCookies(true);
      setCookieFeedback(null);
      let parsed = JSON.parse(manualJson);
      if (!Array.isArray(parsed)) {
        parsed = [parsed];
      }
      const res = await fetchFromApi("/scrape/sync_linkedin_session", {
        method: "POST",
        body: JSON.stringify({ cookies: parsed })
      });
      if (res.status === "SUCCESS") {
        setCookieFeedback(`✓ Başarılı: ${res.cookie_count} çerez kaydedildi (li_at: ${res.has_li_at ? "Aktif" : "Eksik"}).`);
        setManualJson("");
        await loadSessionStatus();
      } else {
        setCookieFeedback(`Hata: ${res.message || "Kaydedilemedi"}`);
      }
    } catch (e: any) {
      setCookieFeedback(`Geçersiz JSON formatı: ${e.message}`);
    } finally {
      setSavingCookies(false);
    }
  }

  async function handleClearSession() {
    if (!confirm(t("LinkedIn oturum çerezlerini silmek istediğinize emin misiniz?"))) return;
    try {
      await fetchFromApi("/scrape/clear_linkedin_session", { method: "POST" });
      await loadSessionStatus();
      setCookieFeedback("Oturum çerezleri temizlendi.");
    } catch (e) {
      // ignore
    }
  }

  useEffect(() => {
    loadHealth();
    loadSessionStatus();
  }, []);

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <ShieldCheck className="w-6 h-6 text-emerald-400" />
          {t("Hesap güvenliği")}</h1>
        <p className="text-xs text-slate-400 mt-1">
          {t("Kullanıcı hesaplarının shadowban ve IP engellemelerine karşı korunması için otonom kota ve gecikme katmanı.")}</p>
      </div>

      {/* Health Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries(health).map(([key, val]: any) => (
          <div key={key} className="p-5 rounded-2xl bg-[#0e1524] border border-slate-800 space-y-3">
            <div className="flex justify-between items-center text-xs">
              <span className="font-bold text-white">{val.platform}</span>
              <span className={`text-xs px-2 py-0.5 rounded-full font-mono ${val.is_safe ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400'}`}>
                {val.is_safe ? t("GÜVENLİ") : t("LİMİTE ULAŞILDI")}
              </span>
            </div>

            <div className="text-2xl font-bold text-white font-mono">
              {val.remaining} <span className="text-xs text-slate-400 font-sans font-normal">/ {val.daily_limit} {t("kalan")}</span>
            </div>

            <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all"
                style={{ width: `${val.health_pct}%` }}
              ></div>
            </div>

            <div className="text-xs text-slate-400">
              {t("Bugün kullanılan:")}<strong>{val.used_today}</strong> {t("işlem")}</div>
          </div>
        ))}
      </div>

      {/* Safety Controls & Settings */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Anti-Bot & Jitter Settings */}
        <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Sliders className="w-4 h-4 text-blue-400" /> {t("İnsan Davranışı Simülasyonu (Jitter Delays)")}</h2>
          <p className="text-xs text-slate-400">
            {t("Ajan istekleri arasına rastgele insansı bekleme süreleri (random jitter) eklenerek bot tespiti engellenir.")}</p>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between items-center p-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <div>
                <div className="font-semibold text-white">{t("İstekler Arası Rastgele Gecikme")}</div>
                <div className="text-xs text-slate-400">{t("1.5sn ile 4.0sn arasında rastgele bekleme")}</div>
              </div>
              <span className="text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded font-mono">
                {t("Aktif")}</span>
            </div>

            <div className="flex justify-between items-center p-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <div>
                <div className="font-semibold text-white">{t("Tarayıcı Parmak İzi Gizleme")}</div>
                <div className="text-xs text-slate-400">{t("navigator.webdriver ve Canvas fingerprint spoofing")}</div>
              </div>
              <span className="text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded font-mono">
                {t("Aktif")}</span>
            </div>

            <div className="flex justify-between items-center p-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <div>
                <div className="font-semibold text-white">{t("Maksimum Günlük Kota Kilidi")}</div>
                <div className="text-xs text-slate-400">{t("Kotaya ulaşıldığında otonom duraklatma")}</div>
              </div>
              <span className="text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded font-mono">
                {t("Devrede")}</span>
            </div>
          </div>
        </div>

        {/* Residential Proxy Configuration */}
        <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Globe className="w-4 h-4 text-emerald-400" /> {t("Konut Tipi Proxy (Residential Proxy)")}</h2>
          <p className="text-xs text-slate-400">
            {t("LinkedIn ve yerel portalların IP banlarını aşmak için konut proxy rotasyonu.")}</p>

          <div className="space-y-3 text-xs">
            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">{t("Proxy URL / Gateway")}</label>
              <input
                type="text"
                defaultValue="http://residential-eu-pool.proxy.io:8080"
                className="w-full mt-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-300 font-mono"
              />
            </div>

            <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
              <div>
                <div className="font-bold text-white">{t("Proxy Durumu: Hazır")}</div>
                <div className="text-xs text-slate-400">{t("IP çıkış bölgesi: Frankfurt / Amsterdam (Düşük Gecikme)")}</div>
              </div>
            </div>
          </div>
        </div>

      </div>

      {/* LinkedIn Session Handshake & Cookie Persistence */}
      <div className="p-6 rounded-2xl bg-[#0e1524] border border-blue-900/50 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <Lock className="w-5 h-5 text-sky-400" />
              {t("LinkedIn Session Handshake (Playwright Oturum Entegrasyonu)")}</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              {t("Chrome Eklentimiz ile tek tıkla aktarılan veya manuel yüklenen")}<code>cookies.json</code> {t("çerezleri. Playwright 2FA sormadan doğrudan adınıza Easy Apply yapar.")}</p>
          </div>
          <button
            onClick={loadSessionStatus}
            disabled={loadingSession}
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs px-3 py-1.5 rounded-xl border border-slate-700 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingSession ? "animate-spin" : ""}`} /> {t("Durumu Yenile")}</button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-1">
            <div className="text-xs text-slate-400 uppercase font-semibold">{t("Oturum Durumu")}</div>
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${sessionStatus?.is_synced && sessionStatus?.has_li_at ? "bg-emerald-400 animate-pulse" : "bg-rose-500"}`}></span>
              <span className="text-sm font-bold text-white">
                {sessionStatus?.is_synced && sessionStatus?.has_li_at ? "Aktif & Senkronize" : "Senkronize Edilmedi"}
              </span>
            </div>
            <div className="text-xs text-slate-400">
              {sessionStatus?.has_li_at ? t("✓ li_at (Anahtar oturum çerezi) mevcut") : "li_at oturumu eksik"}
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-1">
            <div className="text-xs text-slate-400 uppercase font-semibold">{t("Kayıtlı Çerez Sayısı")}</div>
            <div className="text-sm font-bold text-white font-mono">
              {sessionStatus?.cookie_count || 0} {t("Çerez")}</div>
            <div className="text-xs text-slate-400">
              {t("Son Senkronizasyon:")}{sessionStatus?.last_synced_at || "Yok"}
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-1">
            <div className="text-xs text-slate-400 uppercase font-semibold">{t("Playwright Entegrasyonu")}</div>
            <div className="text-sm font-bold text-emerald-400">
              {sessionStatus?.is_synced ? t("Tarayıcı otomasyonu hazır") : "Beklemede"}
            </div>
            <div className="text-xs text-slate-400">
              {sessionStatus?.expires_at ? `Bitiş: ${sessionStatus.expires_at}` : t("Eklenti 'Handshake' butonuna basınız")}
            </div>
          </div>
        </div>

        {/* Manual Cookie JSON Paste Fallback */}
        <div className="pt-2 border-t border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300">
              {t("Manuel Çerez (JSON) Yapıştırma / Güncelleme:")}</span>
            {sessionStatus?.is_synced && (
              <button
                onClick={handleClearSession}
                className="text-xs text-rose-400 hover:text-rose-300 font-semibold underline"
              >
                {t("Oturumu Temizle")}</button>
            )}
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder='[{"name": "li_at", "value": "AQED...", "domain": ".linkedin.com"}]'
              value={manualJson}
              onChange={(e) => setManualJson(e.target.value)}
              className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
            />
            <button
              onClick={handleSaveManualCookies}
              disabled={savingCookies || !manualJson.trim()}
              className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-4 py-2 rounded-xl transition disabled:opacity-50"
            >
              {savingCookies ? "Kaydediliyor..." : "Kaydet"}
            </button>
          </div>
          {cookieFeedback && (
            <div className="text-xs text-sky-400 font-medium">{cookieFeedback}</div>
          )}
        </div>
      </div>
    </div>
  );
}
