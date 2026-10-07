"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, CheckCircle2, ExternalLink, XCircle } from "lucide-react";
import { fetchFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

type Level = "on" | "limited" | "off";
type Capability = { id: string; level: Level; href: string; provider?: string; portals?: string[]; error?: string };

export default function FeatureReadiness() {
  const { translate: t } = useLanguage();
  const [capabilities, setCapabilities] = useState<Capability[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetchFromApi<{ capabilities: Capability[] }>("/system/capabilities?verify=true")
      .then((result) => setCapabilities(result.capabilities || []))
      .catch(() => setFailed(true));
  }, []);

  function title(id: string): string {
    switch (id) {
      case "ai_writing": return t("CV, niyet mektubu ve mülakat yapay zekâsı");
      case "job_scan": return t("İlan taraması");
      case "email_send": return t("Takip ve tanışma e-postası gönderimi");
      case "inbox_sync": return t("Gelen kutusu senkronizasyonu");
      case "stealth_proxy": return t("Tarayıcı otomasyonu için proxy");
      case "automation": return t("Gece taraması ve sabah taslakları");
      default: return id;
    }
  }

  function detail(item: Capability): string {
    if (item.id === "ai_writing") {
      if (item.level === "off") return t("Anahtar girilmiş ama {provider} yanıt vermiyor: {error}", { provider: item.provider || "", error: item.error || "" });
      return item.level === "on"
        ? t("{provider} ile çalışıyor; test çağrısı başarılı.", { provider: item.provider || "" })
        : t("Yapay zekâ anahtarı yok; şablon tabanlı yedek motor kullanılıyor.");
    }
    if (item.id === "job_scan") {
      if (item.level === "off") return t("Tarama SCRAPER_MODE ayarıyla kapatılmış.");
      return item.level === "on"
        ? t("{count} portal bağlı.", { count: item.portals?.length ?? 0 })
        : t("Yalnızca anahtarsız kaynaklar taranıyor; portal bağlamak için Apify ayarla.");
    }
    if (item.level === "on") return t("Hazır.");
    if (item.id === "stealth_proxy") return t("Proxy ayarlı değil; tarayıcı otomasyonu kendi IP adresinden çıkar.");
    if (item.id === "email_send") return t("SMTP ayarlı değil; e-postalar gönderilemez.");
    if (item.id === "inbox_sync") return t("Gmail veya Outlook bağlı değil; yanıtlar otomatik işlenmez.");
    if (item.id === "automation") return t("Otomasyon servisi çalışmıyor; taramalar yalnızca elle başlar.");
    return "";
  }

  if (failed) return <div role="alert" className="notice-card rounded-xl border p-4 text-sm">{t("Özellik durumu alınamadı.")}</div>;
  if (!capabilities) return null;

  const levelLabel: Record<Level, string> = { on: t("Çalışıyor"), limited: t("Sınırlı"), off: t("Kapalı") };
  const levelColor: Record<Level, string> = { on: "text-emerald-400", limited: "text-amber-400", off: "text-red-400" };

  return (
    <section aria-labelledby="feature-readiness-title" className="surface-card rounded-2xl border p-5 sm:p-6">
      <h2 id="feature-readiness-title" className="font-semibold">{t("Hangi özellikler çalışıyor?")}</h2>
      <p className="muted mt-1 text-xs">{t("Her satır eksik olanı gösterir ve ayar ekranına götürür.")}</p>
      <ul className="mt-4 space-y-2">
        {capabilities.map((item) => {
          const Icon = item.level === "on" ? CheckCircle2 : item.level === "limited" ? AlertTriangle : XCircle;
          return (
            <li key={item.id}>
              <Link href={item.href} className="flex items-center justify-between gap-4 rounded-xl border p-3 transition hover:border-[var(--accent)]">
                <span className="min-w-0">
                  <span className="block text-sm font-semibold">{title(item.id)}</span>
                  <span className="muted mt-0.5 block text-xs">{detail(item)}</span>
                </span>
                <span className={`inline-flex shrink-0 items-center gap-1.5 text-xs font-medium ${levelColor[item.level]}`}>
                  <Icon className="h-4 w-4" />{levelLabel[item.level]}<ExternalLink className="ml-1 h-3.5 w-3.5" />
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
