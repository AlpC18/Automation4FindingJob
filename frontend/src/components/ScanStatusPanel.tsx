"use client";

import Link from "next/link";
import { useLanguage } from "@/lib/i18n";
import { formatTimestamp } from "@/lib/scan-status.cjs";

export interface ScanRun {
  id: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  raw_fetched_count?: number;
  total_scraped: number;
  newly_saved_count: number;
  duplicate_count?: number;
  filtered_count?: number;
  removed_count: number;
  filtered?: Record<string, number>;
  errors?: string[];
}

export interface SourceHealth {
  configured: boolean;
  requires_key?: boolean;
  missing?: string[];
  quota_reached?: boolean;
  status: string;
  last_error?: string | null;
  last_run_at?: number | null;
  last_jobs_count?: number;
  runs_today?: number;
  daily_run_limit?: number | null;
}

export interface ScanStatus {
  current_total: number;
  last_run: ScanRun | null;
  sources: Record<string, SourceHealth>;
  scheduler: { is_running: boolean; nightly_time: string; timezone: string; last_nightly_run: string | null; saved_searches: number; scheduled_searches: number };
  empty_state: { cause: string; dominant_filter?: string | null; error?: string | null; counts: Record<string, number> } | null;
}

interface ScanStatusPanelProps {
  status: ScanStatus | null;
  unavailable: boolean;
  runs: ScanRun[];
}

const SOURCE_ERROR_STATES = ["error", "blocked", "failed"];

export default function ScanStatusPanel({ status, unavailable, runs }: ScanStatusPanelProps) {
  const { locale, translate: t } = useLanguage();
  const lastRun = status?.last_run || null;
  const filterLabels: Record<string, string> = {
    location_mismatch: t("konum uyuşmadı"),
    work_mode_mismatch: t("çalışma şekli uyuşmadı"),
    low_quality: t("eksik/düşük kaliteli ilan"),
    expired: t("süresi dolmuş"),
  };
  const missingLabels: Record<string, string> = {
    actor_id: t("Actor ID eksik"),
    api_token: t("API anahtarı eksik"),
    token_reentry: t("Anahtar yeniden girilmeli"),
    disabled: t("Kaynak kapalı"),
  };
  const runStatusLabel = (value: string) => value === "success" ? t("Başarılı") : value === "partial" ? t("Kısmi") : t("Hata");
  const runStatusClass = (value: string) => value === "success" ? "text-emerald-400" : value === "partial" ? "text-amber-300" : "text-rose-300";
  const filterBreakdown = Object.entries(lastRun?.filtered || {}).filter(([key, count]) => filterLabels[key] && count > 0);

  return (
    <section className="rounded-xl border border-slate-800 bg-[#0e1524] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">{t("Tarama durumu ve kaynak güveni")}</h2>
          <p className="mt-1 text-xs text-slate-400">{t("Sayılar son taramanın kayıtlı sonucudur; kaynak başına anahtar, hata ve günlük limit durumu aşağıdadır.")}</p>
        </div>
        <Link href="/sources" className="shrink-0 text-xs font-semibold text-emerald-300 hover:text-white">{t("Kaynak ayarları")} →</Link>
      </div>

      {unavailable ? <p className="mt-3 text-xs text-rose-300">{t("Tarama durumu alınamadı; backend bağlantısını kontrol et.")}</p> : <>
        <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-xs">
          {lastRun ? <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-slate-300">{t("Son tarama")}: <strong className="text-white">{formatTimestamp(lastRun.completed_at || lastRun.started_at, locale)}</strong></span>
              <span className={`font-semibold ${runStatusClass(lastRun.status)}`}>{runStatusLabel(lastRun.status)}</span>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
              {[
                [t("Bulunan"), lastRun.raw_fetched_count ?? lastRun.total_scraped],
                [t("Yeni"), lastRun.newly_saved_count],
                [t("Tekrar (birleştirildi)"), lastRun.duplicate_count ?? 0],
                [t("Elenen"), lastRun.filtered_count ?? 0],
                [t("Arşivlenen eski ilan"), lastRun.removed_count],
              ].map(([label, value]) => <div key={String(label)} className="rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2"><dt className="text-xs text-slate-400">{label}</dt><dd className="mt-0.5 font-mono text-base font-bold text-white">{value}</dd></div>)}
            </dl>
            {filterBreakdown.length > 0 && <p className="mt-2 text-xs text-slate-400">{t("Eleme nedenleri")}: {filterBreakdown.map(([key, count]) => `${count} ${filterLabels[key]}`).join(" · ")}</p>}
            {(lastRun.errors || []).slice(0, 2).map((error) => <p key={error} className="mt-2 text-xs text-rose-300">{error}</p>)}
          </> : <p className="text-slate-400">{t("Henüz tarama yapılmadı. Rol ve konum seçip “Tarama başlat” ile ilk taramayı çalıştır.")}</p>}
        </div>

        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {Object.entries(status?.sources || {}).map(([name, source]) => {
            const failed = SOURCE_ERROR_STATES.includes(source.status);
            const missing = source.missing || [];
            const stateLabel = missing.includes("token_reentry") ? t("Anahtar yenilenmeli") : failed ? t("Kaynak hatası") : source.configured ? t("Hazır") : t("Kurulum gerekli");
            const stateClass = missing.includes("token_reentry") || failed ? "text-rose-300" : source.configured ? "text-emerald-300" : "text-amber-300";
            return (
              <div key={name} className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-xs">
                <div className="flex items-center justify-between gap-2"><strong className="capitalize text-slate-200">{name}</strong><span className={stateClass}>{stateLabel}</span></div>
                <div className="mt-1 text-xs text-slate-400">{t("Anahtar")}: {!source.requires_key ? t("gerekmez") : missing.length ? missing.map((key) => missingLabels[key] || key).join(", ") : t("kayıtlı")}</div>
                <div className="mt-1 text-xs text-slate-400">{source.last_run_at ? `${t("Son tarama")}: ${formatTimestamp(source.last_run_at, locale)} · ${source.last_jobs_count ?? 0} ${t("ilan")}` : t("Henüz tarama yok")}</div>
                {source.daily_run_limit ? <div className={`mt-1 text-xs ${source.quota_reached ? "text-rose-300" : "text-slate-400"}`}>{t("Bugünkü çalıştırma")}: {source.runs_today ?? 0}/{source.daily_run_limit}{source.quota_reached ? ` · ${t("günlük limit doldu")}` : ""}</div> : null}
                {source.last_error && <div className="mt-1 line-clamp-2 text-xs text-rose-300">{source.last_error}</div>}
              </div>
            );
          })}
        </div>

        {runs.length > 1 && <details className="mt-3 text-xs">
          <summary className="cursor-pointer text-slate-400 hover:text-white">{t("Önceki taramalar")} ({runs.length - 1})</summary>
          <ul className="mt-2 space-y-1">
            {runs.slice(1).map((run) => <li key={run.id} className="flex flex-wrap justify-between gap-2 rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2 text-xs text-slate-300">
              <span><span className={`font-semibold ${runStatusClass(run.status)}`}>{runStatusLabel(run.status)}</span> · {formatTimestamp(run.completed_at || run.started_at, locale)}</span>
              <span>{run.raw_fetched_count ?? run.total_scraped} {t("bulundu")} · {run.newly_saved_count} {t("yeni")} · {run.filtered_count ?? 0} {t("elendi")}</span>
            </li>)}
          </ul>
        </details>}
      </>}
    </section>
  );
}
