"use client";

import { useState } from "react";
import { ClipboardCheck, X } from "lucide-react";
import { fetchFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

type FitReport = {
  title: string; company: string; match_percent: number | null; note: string;
  breakdown: { skills_named_in_posting: number; skills_you_show: number; skill_coverage_percent: number | null; role_match_percent: number | null; senior_title: boolean };
  keywords_you_have: string[]; keywords_missing: string[]; edits: string[];
  tailored: { summary_line: string; skills_order: string[]; projects_to_show: { title: string; tech_stack: string[] }[] };
};

/** Opens the per-job resume fit report: the match broken down, missing keywords, and what to change for this application. */
export default function FitReportButton({ jobId }: { jobId: string }) {
  const { translate: t } = useLanguage();
  const [report, setReport] = useState<FitReport | null>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setOpen(true);
    setError("");
    try {
      setReport(await fetchFromApi<FitReport>(`/apply/fit_report/${encodeURIComponent(jobId)}`));
    } catch {
      setError(t("Uyum raporu alınamadı."));
    }
  }

  const percent = (value: number | null) => (value == null ? "—" : `%${Math.round(value)}`);

  return (
    <>
      <button type="button" onClick={load} className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-1.5 text-xs text-slate-200 transition hover:bg-slate-700">
        <ClipboardCheck className="h-3.5 w-3.5" />{t("CV uyum raporu")}
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true" aria-label={t("CV uyum raporu")}>
          <div className="max-h-[85vh] w-full max-w-2xl space-y-4 overflow-y-auto rounded-2xl border border-slate-700 bg-slate-950 p-6 text-sm text-slate-200">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold text-white">{t("CV uyum raporu")}</h2>
                {report && <p className="mt-1 text-xs text-slate-400">{report.title} · {report.company}</p>}
              </div>
              <button type="button" onClick={() => setOpen(false)} aria-label={t("Kapat")} className="rounded-lg p-1.5 hover:bg-slate-800"><X className="h-4 w-4" /></button>
            </div>
            {error && <p role="alert" className="text-amber-300">{error}</p>}
            {!report && !error && <p className="text-slate-400">{t("Yükleniyor...")}</p>}
            {report && (
              <>
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div className="rounded-xl border border-slate-800 p-3"><div className="text-xl font-bold text-emerald-400">{percent(report.match_percent)}</div><div className="text-xs text-slate-400">{t("Genel uyum")}</div></div>
                  <div className="rounded-xl border border-slate-800 p-3"><div className="text-xl font-bold text-white">{percent(report.breakdown.skill_coverage_percent)}</div><div className="text-xs text-slate-400">{t("İlandaki beceriler")} ({report.breakdown.skills_you_show}/{report.breakdown.skills_named_in_posting})</div></div>
                  <div className="rounded-xl border border-slate-800 p-3"><div className="text-xl font-bold text-white">{percent(report.breakdown.role_match_percent)}</div><div className="text-xs text-slate-400">{t("Rol uyumu")}</div></div>
                </div>
                <p className="text-xs text-slate-400">{t(report.note)}</p>
                <section><h3 className="text-xs font-semibold uppercase text-slate-400">{t("Bu başvuru için yapılacaklar")}</h3>
                  <ol className="mt-2 list-decimal space-y-2 pl-5">{report.edits.map((edit) => <li key={edit}>{edit}</li>)}</ol></section>
                <section><h3 className="text-xs font-semibold uppercase text-slate-400">{t("CV'nde olan anahtar kelimeler")}</h3>
                  <p className="mt-1 text-emerald-300">{report.keywords_you_have.join(", ") || "—"}</p></section>
                <section><h3 className="text-xs font-semibold uppercase text-slate-400">{t("İlanda olup CV'nde olmayanlar")}</h3>
                  <p className="mt-1 text-amber-300">{report.keywords_missing.join(", ") || "—"}</p></section>
                <section className="rounded-xl border border-slate-800 p-4"><h3 className="text-xs font-semibold uppercase text-slate-400">{t("Bu ilana göre uyarlanmış CV")}</h3>
                  <p className="mt-2"><span className="text-slate-400">{t("Özet satırı")}:</span> {report.tailored.summary_line}</p>
                  <p className="mt-2"><span className="text-slate-400">{t("Beceri sırası")}:</span> {report.tailored.skills_order.join(", ")}</p>
                  <p className="mt-2"><span className="text-slate-400">{t("Öne çıkarılacak projeler")}:</span> {report.tailored.projects_to_show.map((project) => project.title).join(" · ") || "—"}</p></section>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
