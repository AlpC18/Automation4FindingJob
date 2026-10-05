"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Check } from "lucide-react";
import { fetchFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { formatTimestamp } from "@/lib/scan-status.cjs";
import type { ScanStatus } from "@/components/ScanStatusPanel";

interface Readiness {
  checks: Record<string, boolean>;
}

interface Step {
  title: string;
  done: boolean;
  missing: string[];
  note: string;
  href: string;
  action: string;
}

/** Profil → hedef rol/lokasyon → kaynak ve API → ilk tarama; her adım eksiğini söyler. */
export default function SetupSteps() {
  const { locale, translate: t } = useLanguage();
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [status, setStatus] = useState<ScanStatus | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    Promise.all([fetchFromApi<Readiness>("/setup/readiness"), fetchFromApi<ScanStatus>("/scrape/status")])
      .then(([readinessResult, statusResult]) => { setReadiness(readinessResult); setStatus(statusResult); })
      .catch(() => setFailed(true));
  }, []);

  if (failed) return <p role="status" className="rounded-xl border border-rose-500/20 bg-rose-500/5 px-4 py-3 text-xs text-rose-300">{t("Kurulum durumu alınamadı; backend bağlantısını kontrol et.")}</p>;
  if (!readiness || !status) return null;

  const checks = readiness.checks || {};
  const sources = Object.entries(status.sources || {});
  const readySources = sources.filter(([, source]) => source.configured).map(([name]) => name);
  const keylessSources = sources.filter(([, source]) => source.requires_key && !source.configured).map(([name]) => name);
  const lastRun = status.last_run;
  const scanned = Boolean(lastRun && ["success", "partial"].includes(lastRun.status));

  const steps: Step[] = [
    {
      title: t("Profil"),
      done: Boolean(checks.full_name && checks.contact && checks.skills && checks.experience),
      missing: [!checks.full_name && t("Ad soyad"), !checks.contact && t("E-posta"), !checks.skills && t("Beceriler"), !checks.experience && t("CV metni veya deneyim")].filter(Boolean) as string[],
      note: t("Eşleşme tahmini bu bilgilerden hesaplanır."),
      href: "/onboarding",
      action: t("Profili düzenle"),
    },
    {
      title: t("Hedef rol ve konum"),
      done: Boolean(checks.target_role && checks.location),
      missing: [!checks.target_role && t("Hedef rol"), !checks.location && t("Konum veya çalışma tercihi")].filter(Boolean) as string[],
      note: t("Tarama bu rol ve konumla yapılır."),
      href: "/onboarding",
      action: t("Tercihleri seç"),
    },
    {
      title: t("Kaynak ve API kurulumu"),
      done: readySources.length > 0,
      missing: readySources.length ? [] : [t("Taramaya hazır kaynak yok")],
      note: keylessSources.length ? `${t("Hazır")}: ${readySources.join(", ") || "—"} · ${t("Anahtar bekleyen (isteğe bağlı)")}: ${keylessSources.join(", ")}` : `${t("Hazır")}: ${readySources.join(", ")}`,
      href: "/sources",
      action: t("Kaynakları kontrol et"),
    },
    {
      title: t("İlk tarama"),
      done: scanned,
      missing: scanned ? [] : [lastRun ? t("Son tarama başarısız; kaynak hatasını kontrol et") : t("Henüz tarama yapılmadı")],
      note: scanned ? `${t("Son tarama")}: ${formatTimestamp(lastRun?.completed_at || lastRun?.started_at, locale)}` : t("Tarama yalnızca sen başlattığında çalışır."),
      href: "/jobs",
      action: t("Taramaya git"),
    },
  ];
  const nextIndex = steps.findIndex((step) => !step.done);

  return (
    <section aria-label={t("Başlangıç akışı")} className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {steps.map((step, index) => (
        <Link key={step.title} href={step.href} aria-current={index === nextIndex ? "step" : undefined} className={`group rounded-2xl border bg-[#0e1524] p-4 transition hover:border-blue-500/50 ${index === nextIndex ? "border-blue-500/50" : "border-slate-800"}`}>
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs font-bold text-blue-400">{String(index + 1).padStart(2, "0")}</span>
            <span className={`inline-flex items-center gap-1 text-xs font-semibold ${step.done ? "text-emerald-300" : "text-amber-300"}`}>{step.done && <Check className="h-3 w-3" />}{step.done ? t("Tamam") : index === nextIndex ? t("Sıradaki adım") : t("Eksik")}</span>
          </div>
          <h2 className="mt-2 text-sm font-semibold text-white">{step.title}</h2>
          {step.missing.length > 0 && <p className="mt-1 text-xs text-amber-200">{t("Eksik:")} {step.missing.join(" · ")}</p>}
          <p className="mt-1 text-xs text-slate-400">{step.note}</p>
          {!step.done && <span className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-blue-300">{step.action}<ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1" /></span>}
        </Link>
      ))}
    </section>
  );
}
