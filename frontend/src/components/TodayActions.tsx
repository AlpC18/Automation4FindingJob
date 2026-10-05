"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle2, ListChecks } from "lucide-react";
import { fetchFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

type TodayAction = { id: string; kind: string; href: string; title: string; company: string; count?: number; days?: number };
type TodayResponse = { actions: TodayAction[]; total: number };

export default function TodayActions() {
  const { translate: t } = useLanguage();
  const [today, setToday] = useState<TodayResponse | null>(null);

  useEffect(() => {
    fetchFromApi<TodayResponse>("/outcome/today").then(setToday).catch(() => setToday(null));
  }, []);

  function label(action: TodayAction): string {
    switch (action.kind) {
      case "inbox_reply": return t("E-postayı yanıtla");
      case "follow_up_due": return t("Takip mesajı gönder ({days}. gün)", { days: action.days ?? 7 });
      case "confirm_submission": return t("Başvuruyu portalda gönder ve teyit et");
      case "approve_draft": return t("Taslağı incele ve onayla");
      case "closing_soon": return action.days
        ? t("Son başvuruya {days} gün kaldı; başvur", { days: action.days })
        : t("Son başvuru günü bugün; başvur");
      case "interview_prep": return t("Mülakata hazırlan");
      case "offer_review": return t("Teklifi değerlendir");
      case "new_matches": return t("{count} yeni yüksek uyumlu ilanı incele", { count: action.count ?? 0 });
      default: return action.kind;
    }
  }

  if (!today) return null;

  return (
    <section aria-labelledby="today-actions-title" className="rounded-2xl border border-slate-800 bg-[#0e1524] p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 id="today-actions-title" className="flex items-center gap-2 text-sm font-semibold text-white">
            <ListChecks className="h-4 w-4 text-blue-400" /> {t("Bugünün işleri")}
          </h2>
          <p className="mt-1 text-xs text-slate-400">{t("Sırayla ilerle; her satır seni ilgili adıma götürür.")}</p>
        </div>
        {today.total > 0 && <span className="rounded-full bg-blue-600/20 px-2.5 py-1 text-xs font-semibold text-blue-300">{today.total}</span>}
      </div>

      {today.actions.length === 0 ? (
        <div className="mt-4 flex items-center gap-2 text-xs text-slate-400">
          <CheckCircle2 className="h-4 w-4 text-emerald-400" /> {t("Bugün için bekleyen iş yok. Yeni ilan taraması başlatabilirsin.")}
        </div>
      ) : (
        <ol className="mt-4 space-y-2">
          {today.actions.map((action) => (
            <li key={action.id}>
              <Link href={action.href} className="group flex items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3 transition hover:border-blue-500/50">
                <div className="min-w-0">
                  <div className="text-xs font-semibold text-white">{label(action)}</div>
                  {(action.title || action.company) && (
                    <div className="mt-0.5 truncate text-xs text-slate-400">{[action.title, action.company].filter(Boolean).join(" — ")}</div>
                  )}
                </div>
                <ArrowRight className="h-3.5 w-3.5 shrink-0 text-slate-400 group-hover:text-blue-300" />
              </Link>
            </li>
          ))}
        </ol>
      )}
      {today.total > today.actions.length && (
        <p className="mt-3 text-xs text-slate-400">{t("Toplam {total} iş bekliyor; en öncelikliler gösteriliyor.", { total: today.total })}</p>
      )}
    </section>
  );
}
