import Link from "next/link";
import { ArrowUpRight, Compass, FolderOpen, GraduationCap, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { useLanguage } from "@/lib/i18n";

export function CareerHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
    <div><p className="eyebrow mb-3">{eyebrow}</p><h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h2><p className="muted mt-3 max-w-2xl text-sm leading-6">{description}</p></div>
    {action && <div className="flex shrink-0 flex-wrap gap-2">{action}</div>}
  </div>;
}

export function CareerMetric({ label, value, detail, icon: Icon }: { label: string; value: ReactNode; detail: string; icon: LucideIcon }) {
  return <div className="career-card"><div className="flex items-center justify-between gap-3"><p className="muted text-xs">{label}</p><Icon className="h-4 w-4 muted" /></div><p className="mt-4 break-words text-2xl font-semibold tracking-tight">{value}</p><p className="muted mt-2 text-xs leading-5">{detail}</p></div>;
}

export function CareerNotice({ children, error = false }: { children: ReactNode; error?: boolean }) {
  return <div role={error ? "alert" : "status"} className={`notice-card rounded-xl border p-4 text-sm ${error ? "" : "success"}`}>{children}</div>;
}

export function CareerEmpty({ title, children, href, action }: { title: string; children: ReactNode; href?: string; action?: string }) {
  return <div className="empty-hint rounded-2xl border border-dashed p-8 text-center"><p className="font-semibold text-[var(--text)]">{title}</p><p className="mx-auto mt-2 max-w-lg text-sm leading-6">{children}</p>{href && <Link href={href} className="secondary-button career-action mt-4 border">{action}<ArrowUpRight className="h-4 w-4" /></Link>}</div>;
}

export function CareerLinks({ current }: { current: "map" | "learn" | "portfolio" }) {
  const { translate: t } = useLanguage();
  const links = [
    { id: "map", title: "Kariyer haritası", detail: "Bir sonraki rolünü keşfet ve geçiş planını oluştur.", href: "/career-map", icon: Compass },
    { id: "learn", title: "Öğrenme planı", detail: "Beceri hedeflerini kaynaklara ve takip edilebilir adımlara dönüştür.", href: "/upskill", icon: GraduationCap },
    { id: "portfolio", title: "Portföy stüdyosu", detail: "Projelerini ve deneyimini paylaşılabilir bir sayfada sergile.", href: "/portfolio-site", icon: FolderOpen },
  ];
  return <section aria-label={t("Diğer kariyer araçları")} className="grid gap-4 sm:grid-cols-2">{links.filter(item => item.id !== current).map(({ id, title, detail, href, icon: Icon }) => <Link key={id} href={href} className="career-card group flex items-start gap-4 transition-colors hover:border-[var(--accent-border)]"><span className="brand-mark rounded-xl p-3"><Icon className="h-5 w-5" /></span><div className="min-w-0 flex-1"><h3 className="text-sm font-semibold">{t(title)}</h3><p className="muted mt-2 text-xs leading-5">{t(detail)}</p></div><ArrowUpRight className="h-4 w-4 muted" /></Link>)}</section>;
}

export function downloadText(content: string, filename: string, type = "text/plain;charset=utf-8") {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
