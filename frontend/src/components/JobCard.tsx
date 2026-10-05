"use client";

import Link from "next/link";
import { AlertTriangle, CheckSquare, DollarSign, ExternalLink, EyeOff, Heart, Layers, Link2, ShieldAlert, Square } from "lucide-react";
import { getExternalJobUrl } from "@/lib/job-links";
import { useLanguage } from "@/lib/i18n";
import { formatTimestamp, jobFreshness, linkStatus } from "@/lib/scan-status.cjs";

/** One listing in the jobs feed. State and actions stay in the jobs page and arrive through `ctx`. */
export default function JobCard({ job, ctx }: { job: any; ctx: any }) {
  const { locale, translate: t } = useLanguage();
  const { selectedJobIds, toggleJobSelection, toggleJobFlag, checkJobLink, linkCheckBusy, linkLabels, prepareApplication, preparingJob, setDetailJob } = ctx;
    const hasRedFlags = job.red_flags && job.red_flags.length > 0;
    const isGhost = job.ghost_score >= 35;
    const skillGaps = job.skill_gaps || {};
    const sourceUrl = getExternalJobUrl(job.url);
    const freshness = jobFreshness(job);
    const linkState = linkStatus(job.source_link_check);
    const explanation = skillGaps.score_explanation;

    return (
      <div
        key={job.id}
        className="p-5 rounded-2xl bg-[#0e1524] border border-slate-800/80 hover:border-slate-700 transition space-y-4"
      >
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                aria-label={`${job.title} ilanını seç`}
                onClick={() => toggleJobSelection(job.id)}
                className="text-slate-400 hover:text-blue-400"
              >
                {selectedJobIds.includes(job.id)
                  ? <CheckSquare className="w-4 h-4 text-blue-400" />
                  : <Square className="w-4 h-4" />}
              </button>
              <button type="button" onClick={() => setDetailJob(job)} className="text-left text-base font-bold text-white transition hover:text-blue-400">{job.title}</button>
              <span className="text-xs bg-slate-800 text-slate-300 px-2.5 py-0.5 rounded-full border border-slate-700 font-medium">
                {job.company}
              </span>
              <span className="text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded uppercase font-mono">
                {job.platform}
              </span>
              {sourceUrl && <a href={sourceUrl} target="_self" onClick={(event) => event.stopPropagation()} className="inline-flex items-center gap-1 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2 py-0.5 text-xs font-semibold text-emerald-300 transition hover:bg-emerald-500/20">
                {t("Kaynak ilanda aç")}<ExternalLink className="h-3 w-3" />
              </a>}
              {sourceUrl && <button type="button" onClick={() => void checkJobLink(job)} disabled={linkCheckBusy === job.id} className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold transition disabled:opacity-50 ${linkState === "reachable" ? "border-emerald-500/30 text-emerald-300" : ["broken", "unreachable", "invalid"].includes(linkState) ? "border-rose-500/30 text-rose-300" : "border-slate-700 text-slate-400 hover:text-white"}`}>
                <Link2 className="h-3 w-3" /> {linkCheckBusy === job.id ? t("Kontrol ediliyor…") : linkState === "unchecked" ? t("Linki kontrol et") : linkLabels[linkState]}
              </button>}
              <button type="button" title={t("Favoriye ekle / çıkar")} onClick={() => void toggleJobFlag(job, "favorite")} className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold transition ${job.favorite ? "border-rose-500/40 bg-rose-500/10 text-rose-300" : "border-slate-700 text-slate-400 hover:text-rose-300"}`}>
                <Heart className={`h-3 w-3 ${job.favorite ? "fill-current" : ""}`} /> {job.favorite ? t("Favoride") : t("Favori")}
              </button>
              <button type="button" title={t("İlanı gizle")} onClick={() => void toggleJobFlag(job, "hidden")} className="inline-flex items-center gap-1 rounded-full border border-slate-700 px-2 py-0.5 text-xs font-semibold text-slate-400 transition hover:border-amber-500/40 hover:text-amber-300">
                <EyeOff className="h-3 w-3" /> {t("Gizle")}
              </button>
              {(job.source_aliases || []).length > 0 && <span title={t("Bu ilan başka kaynaklarda da bulundu")} className="text-xs rounded-full border border-slate-700 px-2 py-0.5 text-slate-400">+{job.source_aliases.length} {t("kaynak kopyası birleştirildi")}</span>}
            </div>

            <div className="text-xs text-slate-400 flex flex-wrap gap-x-4 gap-y-1 pt-0.5">
              <span>{job.location}</span>
              <span>{job.remote_type}</span>
              <span>{job.salary_range}</span>
              <span>{job.posted_date}</span>
            </div>
          </div>

          {/* Estimated fit & ghost badges */}
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-sm font-bold text-emerald-400 font-mono">≈ %{job.match_score ?? "—"} {t("Tahmini uyum")}</div>
              <div className="text-xs text-slate-400 uppercase font-semibold">
                {job.match_tier} {t("Tier •")}{job.match_status}
              </div>
            </div>
            {isGhost && (
              <div className="text-right">
                <div className="text-xs font-bold text-rose-400 flex items-center gap-1">
                  <ShieldAlert className="w-3.5 h-3.5" /> %{job.ghost_score} {t("Ghost")}</div>
                <div className="text-xs text-rose-400/80">{t("Hayalet İlan Riski")}</div>
              </div>
            )}
          </div>
        </div>

        {/* Job Description Preview */}
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
          <span>{t("Veri kaynağı")}: {job.platform}{(job.source_aliases || []).length > 0 ? ` (+${job.source_aliases.map((alias: any) => alias.platform).join(", ")})` : ""}</span>
          <span>{t("İlk görüldü")}: {formatTimestamp(job.first_seen_at, locale)}</span>
          <span>{t("Kaynakta son görüldü")}: {formatTimestamp(job.last_seen_at, locale)}</span>
          <span>{t("Link son kontrol")}: {job.source_link_check?.checked_at && linkState !== "queued" ? `${formatTimestamp(job.source_link_check.checked_at, locale)} · ${linkLabels[linkState]}` : t("yapılmadı")}</span>
        </div>
        {(freshness.level === "stale" || freshness.level === "aging" || ["broken", "unreachable"].includes(linkState)) && <div className="flex flex-wrap gap-2 text-xs">
          {freshness.level === "stale" && <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-amber-200">{t("Eskimiş olabilir: son taramada kaynak bu ilanı döndürmedi")}</span>}
          {freshness.level === "aging" && <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-amber-200">{freshness.days} {t("gündür kaynakta yeniden doğrulanmadı")}</span>}
          {["broken", "unreachable"].includes(linkState) && <span className="rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-rose-200">{t("İlan linki açılmıyor; ilan kapanmış olabilir")}</span>}
        </div>}
        <p className="text-xs text-slate-300 leading-relaxed line-clamp-2">{job.description}</p>

        {job.ai_review && (
          <div className="rounded-xl border border-blue-500/20 bg-blue-500/[0.04] p-3">
            <div className="text-xs font-semibold text-blue-200">{t("Yapay zekâ değerlendirmesi")} · {job.ai_review.score}/100</div>
            {job.ai_review.verdict && <p className="mt-1 text-xs text-slate-300">{job.ai_review.verdict}</p>}
            <div className="mt-2 flex flex-wrap gap-1.5">
              {(job.ai_review.strengths || []).map((item: string) => <span key={`s-${item}`} className="rounded-full border border-emerald-500/20 px-2 py-0.5 text-xs text-emerald-200">✓ {item}</span>)}
              {(job.ai_review.gaps || []).map((item: string) => <span key={`g-${item}`} className="rounded-full border border-amber-500/20 px-2 py-0.5 text-xs text-amber-200">{t("Eksik")}: {item}</span>)}
            </div>
            <p className="mt-2 text-xs text-slate-400">{t("CV'n ve ilan metni okunarak üretildi; işe alınma olasılığı değildir. Kural tabanlı puan: {score}", { score: job.ai_review.rule_score ?? "—" })}</p>
          </div>
        )}
        <div className="rounded-xl border border-emerald-500/15 bg-emerald-500/[0.03] p-3"><div className="text-xs font-semibold text-emerald-200">{t("Neden uyuyor? · kural tabanlı tahmin")}</div><p className="mt-1 text-xs text-slate-400">{t("Bu puan işveren ATS puanı veya işe alınma olasılığı değildir; beceri örtüşmesine ve ilan başlığının hedef rolüne benzerliğine dayanır.")}</p><div className="mt-2 flex flex-wrap gap-1.5">{(skillGaps.matched_evidence || skillGaps.matched_skills || []).slice(0, 6).map((entry: any) => <span key={typeof entry === "string" ? entry : entry.required_skill} title={entry.evidence_source === "saved_cv_text" ? t("Kaydedilmiş CV metninde bulundu") : t("Profil beceri listesinde bulundu")} className="rounded-full border border-emerald-500/20 px-2 py-0.5 text-xs text-emerald-200">✓ {typeof entry === "string" ? entry : entry.profile_evidence}{typeof entry === "string" ? "" : entry.evidence_source === "saved_cv_text" ? ` · ${t("CV")}` : ` · ${t("Profil")}`}</span>)}{(skillGaps.missing_skills || []).slice(0, 6).map((skill: string) => <span key={skill} className="rounded-full border border-amber-500/20 px-2 py-0.5 text-xs text-amber-200">{t("Eksik")}: {skill}</span>)}{!(skillGaps.matched_skills || []).length && !(skillGaps.missing_skills || []).length && <span className="text-xs text-slate-400">{t("İlan metninde tanınan beceri bulunamadı; puan büyük ölçüde varsayılana dayanıyor.")}</span>}</div>{explanation && <p className="mt-2 text-xs text-slate-400">{t("Puan dökümü")}: {t("beceri")} {explanation.skill_points}/{explanation.skill_points_max ?? 70}{explanation.role_points !== undefined ? ` · ${t("rol uyumu")} ${explanation.role_points}/${explanation.role_points_max}` : ""} · {t("deneyim")} {explanation.experience_points}/{explanation.experience_points_max ?? 30}{explanation.target_role_missing ? ` · ${t("profilde hedef rol yok")}` : ""}{explanation.seniority_deduction > 0 ? ` · ${t("kıdem uyumsuzluğu")} −${explanation.seniority_deduction}` : ""}{explanation.risk_deduction > 0 ? ` · ${t("risk kesintisi")} −${explanation.risk_deduction}` : ""}{explanation.experience_missing ? ` · ${t("profilde deneyim yılı yok")}` : ""}{explanation.confidence === "low" ? ` · ${t("düşük güven")}` : ""}</p>}</div>

        {/* Warnings & Diagnostics Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
          {/* Red Flags & Ghost Reasons */}
          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1.5">
            <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> {t("Kırmızı Çizgiler & Riskler")}</div>
            {hasRedFlags ? (
              job.red_flags.map((rf: string, idx: number) => (
                <div
                  key={idx}
                  className="text-xs text-rose-400 bg-rose-500/10 px-2 py-1 rounded border border-rose-500/20"
                >
                  {rf}
                </div>
              ))
            ) : (
              <div className="text-xs text-emerald-400">{t("✓ Herhangi bir kırmızı çizgi uyuşmazlığı yok.")}</div>
            )}

            {isGhost && job.ghost_reasons?.length > 0 && (
              <div className="text-xs text-amber-400 bg-amber-500/10 px-2 py-1 rounded border border-amber-500/20">
                {t("Hayalet İlan Nedeni:")} {job.ghost_reasons[0]}
              </div>
            )}
          </div>

          {/* Skill Gap & GitHub Suggestions */}
          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1.5">
            <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-indigo-400" /> {t("Yetenek Boşluğu (Skill Gap)")}</div>
            <div className="flex flex-wrap gap-1">
              {skillGaps.matched_skills?.map((s: string) => (
                <span
                  key={s}
                  className="text-xs bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded font-mono"
                >
                  +{s}
                </span>
              ))}
              {skillGaps.missing_skills?.map((s: string) => (
                <span
                  key={s}
                  className="text-xs bg-rose-500/10 text-rose-400 px-1.5 py-0.5 rounded font-mono"
                >
                  -{s}
                </span>
              ))}
            </div>
            {skillGaps.actionable_recommendations?.[0] && (
              <div className="text-xs text-indigo-300 leading-tight">
                {skillGaps.actionable_recommendations[0]}
              </div>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-xs">
          <div className="text-xs text-slate-400 flex items-center gap-2">
            <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
            <span>
              {t("Maaş Skalası:")}{" "}
              <strong className="text-white">
                {job.salary_benchmark?.formatted_display || t("Piyasa benchmarkı hesaplanıyor")}
              </strong>
              {job.salary_benchmark?.source_type === "modeled_estimate" && <span className="ml-1 text-xs text-amber-300">{t("Tahmini · işveren tarafından doğrulanmadı")}</span>}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/decision-makers"
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition text-xs"
            >
              {t("Karar Verici (X-Ray)")}</Link>
            <button onClick={() => void prepareApplication(job)} disabled={preparingJob === job.id} className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold transition text-xs shadow-md shadow-blue-600/20 disabled:opacity-50">
              {preparingJob === job.id ? t("Taslak hazırlanıyor…") : t("Başvuru taslağı hazırla")}
            </button>
          </div>
        </div>
      </div>
    );
}
