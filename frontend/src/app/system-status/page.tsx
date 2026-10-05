"use client";

import dynamic from "next/dynamic";
import PageTabs from "@/components/PageTabs";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  Activity, AlertTriangle, Bot, CheckCircle2, Clock3, Database,
  ExternalLink, Mail, RefreshCw, Server, ShieldCheck, XCircle,
} from "lucide-react";
import { fetchFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import FeatureReadiness from "@/components/FeatureReadiness";

type Check = { status?: string; engine?: string; enabled?: boolean; issues?: string[] };
type Health = { status?: string; environment?: string; version?: string; checks?: Record<string, Check> };

const stateLabel = (status?: string, t?: (value: string) => string) => {
  const labels: Record<string, string> = {
    healthy: "Hazır", success: "Başarılı", ready: "Hazır", disabled: "Kapalı",
    invalid: "Yapılandırma gerekli", unhealthy: "Kontrol gerekli", degraded: "Kontrol gerekli",
    error: "Hata", needs_configuration: "Kurulum gerekli",
  };
  return t ? t(labels[status || ""] || "Bilinmiyor") : labels[status || ""] || "Bilinmiyor";
};

function SystemStatusPage() {
  const { translate: t } = useLanguage();
  const [health, setHealth] = useState<Health | null>(null);
  const [sources, setSources] = useState<any>(null);
  const [providers, setProviders] = useState<any>(null);
  const [email, setEmail] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const refresh = useCallback(async (quiet = false) => {
    if (quiet) setRefreshing(true); else setLoading(true);
    const results = await Promise.allSettled([
      fetchFromApi<Health>("/system/health"),
      fetchFromApi("/scrape/sources"),
      fetchFromApi("/llm/providers"),
      fetchFromApi("/setup/notification-preferences"),
    ]);
    const nextErrors: string[] = [];
    if (results[0].status === "fulfilled") setHealth(results[0].value);
    else nextErrors.push("Sistem sağlık bilgisi alınamadı.");
    if (results[1].status === "fulfilled") setSources(results[1].value);
    else nextErrors.push("İlan kaynağı durumu alınamadı.");
    if (results[2].status === "fulfilled") setProviders(results[2].value);
    else nextErrors.push("Yapay zekâ sağlayıcı durumu alınamadı.");
    if (results[3].status === "fulfilled") setEmail(results[3].value);
    else nextErrors.push("E-posta ayarı durumu alınamadı.");
    setErrors(nextErrors);
    setLastChecked(new Date());
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const checks = health?.checks || {};
  const sourceList = sources?.sources || [];
  const providerList = providers?.providers || [];
  const activeProvider = providers?.effective_provider || providers?.active_provider;
  const mailReady = Boolean(email?.smtp_configured && email?.recipient_configured);
  const sourceHealth = sources?.health || {};
  const sourceNeedsFix = sourceList.some((item: any) => item.token_needs_reentry)
    || Object.values(sourceHealth).some((item: any) => ["error", "blocked"].includes(item?.status));
  const configuredProviders = providerList.filter((item: any) => item.is_configured).length;
  const rows = [
    { title: "Veritabanı", detail: checks.database?.engine || "", status: checks.database?.status, icon: Database, href: "/privacy" },
    { title: "İş kuyruğu / Redis", detail: checks.redis?.status === "disabled" ? "Yerel modda devre dışı" : "Arka plan görevleri", status: checks.redis?.status, icon: Server, href: "/daemon-settings" },
    { title: "Otomasyon daemon'u", detail: checks.daemon?.enabled ? "Etkin" : "Durum bilgisi", status: checks.daemon?.status, icon: Clock3, href: "/daemon-settings" },
    { title: "Yapay zekâ sağlayıcısı", detail: `${activeProvider || "Sağlayıcı seçilmemiş"} · ${configuredProviders} hazır`, status: providerList.some((item: any) => item.id === providers?.effective_provider && item.is_configured) ? "healthy" : "needs_configuration", icon: Bot, href: "/llm" },
    { title: "E-posta hatırlatmaları", detail: mailReady ? "SMTP ve alıcı ayarlı" : "SMTP veya profil e-postası eksik", status: mailReady ? "healthy" : "needs_configuration", icon: Mail, href: "/preferences" },
    { title: "Apify tokenları", detail: `${sourceList.length} kaynak · ${sourceNeedsFix ? "yeniden yapılandırma gerekiyor" : "kaynak ayarları kontrol edildi"}`, status: sourceNeedsFix ? "unhealthy" : (sourceList.some((item: any) => item.token_configured) ? "healthy" : "needs_configuration"), icon: ShieldCheck, href: "/sources" },
  ];
  const needsAttention = rows.filter((row) => !["healthy", "success", "ready", "disabled"].includes(row.status || "")).length + errors.length;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <div className="eyebrow mb-2 flex items-center gap-2"><Activity className="h-4 w-4" />{t("SİSTEM VE ENTEGRASYONLAR")}</div>
          <h1 className="text-3xl font-semibold tracking-tight">{t("Sistem kontrolü")}</h1>
          <p className="muted mt-2 max-w-2xl text-sm leading-6">{t("Servislerin ve bağlantıların mevcut durumunu kontrol et. Bu ekran ücretli tarama başlatmaz ve gizli anahtarları göstermez.")}</p>
        </div>
        <button type="button" onClick={() => void refresh(true)} disabled={refreshing || loading} className="secondary-button inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-4 text-sm font-semibold disabled:opacity-50">
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />{t("Durumu yenile")}
        </button>
      </header>

      <section className="surface-card flex flex-wrap items-center justify-between gap-4 rounded-2xl border p-5">
        <div className="flex items-center gap-3">
          {needsAttention === 0 ? <CheckCircle2 className="h-6 w-6 text-emerald-400" /> : <AlertTriangle className="h-6 w-6 text-amber-400" />}
          <div><p className="font-semibold">{t(needsAttention === 0 ? "Kontroller tamam" : `${needsAttention} kontrol dikkat istiyor`)}</p><p className="muted mt-1 text-xs">{t("Uygulama")}: {health?.environment || "—"} · {t("Sürüm")}: {health?.version || "—"}</p></div>
        </div>
        <span className="muted text-xs">{lastChecked ? `${t("Son kontrol")}: ${lastChecked.toLocaleTimeString()}` : t("Kontrol ediliyor…")}</span>
      </section>

      {errors.length > 0 && <div role="alert" className="notice-card rounded-xl border p-4 text-sm">{errors.map((error) => <p key={error}>{t(error)}</p>)}</div>}

      <section className="grid gap-3 sm:grid-cols-2">
        {rows.map((row) => {
          const Icon = row.icon;
          const ok = ["healthy", "success", "ready", "disabled"].includes(row.status || "");
          return <Link key={row.title} href={row.href} className="surface-card flex items-center justify-between gap-4 rounded-2xl border p-4 transition hover:border-[var(--accent)]">
            <span className="flex min-w-0 items-center gap-3"><span className="step-number"><Icon className="h-4 w-4" /></span><span className="min-w-0"><span className="block truncate text-sm font-semibold">{t(row.title)}</span><span className="muted mt-1 block truncate text-xs">{t(row.detail)}</span></span></span>
            <span className={`inline-flex shrink-0 items-center gap-1.5 text-xs font-medium ${ok ? "text-emerald-400" : "text-amber-400"}`}>{ok ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}{stateLabel(row.status, t)}<ExternalLink className="ml-1 h-3.5 w-3.5" /></span>
          </Link>;
        })}
      </section>

      <FeatureReadiness />

      <section className="surface-card rounded-2xl border p-5 sm:p-6">
        <h2 className="font-semibold">{t("Önerilen sonraki adımlar")}</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <Link href="/sources" className="secondary-button rounded-xl border p-4 text-sm"><span className="block font-semibold">{t("Apify anahtarlarını yenile")}</span><span className="muted mt-1 block text-xs">{t("Geçersiz tokenları değiştir ve bağlantıyı test et.")}</span></Link>
          <Link href="/llm" className="secondary-button rounded-xl border p-4 text-sm"><span className="block font-semibold">{t("AI sağlayıcısını ayarla")}</span><span className="muted mt-1 block text-xs">{t("Anahtar ve model bağlantısını kontrol et.")}</span></Link>
          <Link href="/privacy" className="secondary-button rounded-xl border p-4 text-sm"><span className="block font-semibold">{t("Yedek ve veri dışa aktarımı")}</span><span className="muted mt-1 block text-xs">{t("Verilerini indirip güvenli bir konumda sakla.")}</span></Link>
        </div>
        <p className="muted mt-4 text-xs leading-5">{t("Apify taraması yalnızca İlan kaynakları ekranından sen başlattığında çalışır. Yedek indirme düğmesi de mevcut kaynak yönetimi ekranındadır.")}</p>
      </section>
    </div>
  );
}

// Loaded only when their tab is opened, so this page stays as light as before.
const PortalHealthPage = dynamic(() => import("../portal-health/page"));
const TestSpritePage = dynamic(() => import("../testsprite/page"));

// Related screens live here as tabs so the menu stays short; each still has its own route.
const TABS = [
    { label: "Sistem kontrolü", Component: SystemStatusPage },
    { label: "Portal sağlığı", Component: PortalHealthPage },
    { label: "Test merkezi", Component: TestSpritePage },
];

export default function SystemStatusPageWithTabs() {
  return <PageTabs tabs={TABS} />;
}
