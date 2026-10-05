"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowUpRight, BarChart3, Bot, BriefcaseBusiness,
  CalendarDays, CheckSquare, ChevronDown, Compass, Cpu, FileText, Globe2,
  FileSearch, GraduationCap, Inbox, LayoutDashboard, LifeBuoy, Menu, MessageSquareText,
  Moon, Newspaper, Radio, Search, Send, Settings2, ShieldCheck, Sparkles, Activity,
  Sun, Target, UserRound, Users, Volume2, X,
} from "lucide-react";
import CandidateHeader from "@/components/CandidateHeader";
import ApifyUsageButton from "@/components/ApifyUsageButton";
import LlmUsageButton from "@/components/LlmUsageButton";
import Toaster from "@/components/Toaster";
import CommandPalette from "@/components/CommandPalette";
import NotificationDrawer from "@/components/NotificationDrawer";
import { useLanguage } from "@/lib/i18n";

// The daily flow stays visible; everything else lives under "Daha fazla" so the menu is short.
const groups = [
  {
    label: "ÇALIŞMA ALANI",
    tone: "workspace",
    links: [
      { name: "Genel Bakış", href: "/", icon: LayoutDashboard },
      { name: "İş ilanları", href: "/jobs", icon: Search },
      { name: "Başvurular", href: "/kanban", icon: CheckSquare },
      { name: "Gelen kutusu", href: "/inbox", icon: Inbox },
      { name: "Takip takvimi", href: "/follow-up", icon: CalendarDays },
    ],
  },
  {
    label: "KARİYERİNİ ŞEKİLLENDİR",
    tone: "career",
    links: [
      { name: "Profilim", href: "/setup", icon: UserRound },
      { name: "Kategori ve alanlar", href: "/preferences", icon: Compass },
      { name: "CV'yi analiz et", href: "/cv-analysis", icon: FileSearch },
    ],
  },
  {
    label: "SİSTEM",
    tone: "system",
    links: [
      { name: "İlan kaynakları", href: "/sources", icon: Globe2 },
      { name: "Yapay zekâ / API anahtarları", href: "/llm", icon: Cpu },
    ],
  },
];

const moreGroups = [
  {
    label: "ARAÇLAR",
    tone: "tools",
    links: [
      { name: "Analitik", href: "/analytics", icon: BarChart3 },
      { name: "Mülakat hazırlığı", href: "/interview", icon: MessageSquareText },
      { name: "Otonom başvurular", href: "/auto-apply", icon: Send },
      { name: "Soğuk erişim", href: "/cold-outreach", icon: Send },
      { name: "Karar vericiler", href: "/decision-makers", icon: Users },
      { name: "İş teklifi pazarlığı", href: "/offer-negotiator", icon: BriefcaseBusiness },
      { name: "Maaş istihbaratı", href: "/salary-intel", icon: BarChart3 },
      { name: "Kariyer haritası", href: "/career-map", icon: Target },
      { name: "Öğrenme planı", href: "/upskill", icon: GraduationCap },
      { name: "Portfolyo", href: "/portfolio-site", icon: Globe2 },
      { name: "Davranışsal profil", href: "/behavioral", icon: UserRound },
      { name: "Yazım stili", href: "/writing-style", icon: FileText },
      { name: "İş akışı zaman çizelgesi", href: "/timeline", icon: CalendarDays },
    ],
  },
  {
    label: "SİSTEM",
    tone: "system",
    links: [
      { name: "Hesap güvenliği", href: "/safety", icon: ShieldCheck },
      { name: "Veri ve gizlilik", href: "/privacy", icon: ShieldCheck },
      { name: "Otomatik çalışma ayarları", href: "/daemon-settings", icon: Settings2 },
      { name: "Raporlar", href: "/reports", icon: FileText },
      { name: "Haftalık bülten", href: "/weekly-digest", icon: Newspaper },
      { name: "Sistem kontrolü", href: "/system-status", icon: Activity },
    ],
  },
];

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { locale, setLocale, translate: t } = useLanguage();
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("career-agent-theme");
    const nextTheme = saved === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = nextTheme;
    setTheme(nextTheme);
  }, []);

  useEffect(() => setMobileOpen(false), [pathname]);

  const inMore = moreGroups.some((group) => group.links.some((item) => isActive(pathname, item.href)));

  function renderGroup(group: (typeof groups)[number]) {
    return (
      <section key={`${group.tone}-${group.links[0].href}`} className={`nav-group nav-group-${group.tone}`}>
        <h2 className="muted mb-2 px-3 text-xs font-bold tracking-[0.16em]">{t(group.label)}</h2>
        <div className="space-y-1">
          {group.links.map((item) => {
            const Icon = item.icon;
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`nav-link flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-[13px] font-medium transition-colors ${active ? "active" : ""}`}
              >
                <Icon className="h-[17px] w-[17px] shrink-0" />
                <span className="flex-1">{t(item.name)}</span>
                {active && <span className="nav-indicator h-1.5 w-1.5 rounded-full" />}
              </Link>
            );
          })}
        </div>
      </section>
    );
  }

  useEffect(() => {
    if (window.matchMedia("(max-width: 1023px) and (hover: none) and (pointer: coarse)").matches) {
      setMobileOpen(true);
    }
  }, []);

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = nextTheme;
    localStorage.setItem("career-agent-theme", nextTheme);
    setTheme(nextTheme);
  }

  const themeButton = (
    <button
      type="button"
      onClick={toggleTheme}
      className="theme-toggle inline-flex h-8 w-8 items-center justify-center rounded-lg border p-0 transition-colors"
      aria-label={theme === "dark" ? t("Açık temaya geç") : t("Koyu temaya geç")}
      title={theme === "dark" ? t("Açık görünüm") : t("Koyu görünüm")}
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );

  return (
    <div className="app-layout min-h-screen">
      <CommandPalette />
      <Toaster />

      {mobileOpen && <button className="mobile-scrim fixed inset-0 z-40 lg:hidden" onClick={() => setMobileOpen(false)} aria-label={t("Menüyü kapat")} />}

      <aside className={`app-sidebar fixed inset-y-0 left-0 z-50 flex w-[250px] flex-col border-r transition-transform duration-200 lg:translate-x-0 ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="sidebar-brand flex h-[66px] shrink-0 items-center justify-between border-b px-4">
          <Link href="/" className="flex items-center gap-3" aria-label="Career Agent home">
            <span className="brand-mark flex h-9 w-9 items-center justify-center rounded-2xl"><Bot className="h-4 w-4" /></span>
            <span>
              <span className="block text-sm font-bold tracking-[0.12em]">CAREER AGENT</span>
              <span className="muted block pt-0.5 text-xs tracking-[0.16em]">{t("KARİYER ÇALIŞMA ALANI")}</span>
            </span>
          </Link>
          <button onClick={() => setMobileOpen(false)} className="icon-button rounded-lg p-2 lg:hidden" aria-label={t("Menüyü kapat")}><X className="h-4 w-4" /></button>
        </div>

        <div className="sidebar-profile mx-3 mt-3 rounded-2xl border p-2.5">
          <CandidateHeader compact />
        </div>

        <nav className="min-h-0 flex-1 space-y-4 overflow-y-auto px-2.5 py-4" aria-label={t("Ana menü")}>
          {groups.map(renderGroup)}
          <details className="nav-more" open={moreOpen || inMore} onToggle={(event) => setMoreOpen(event.currentTarget.open)}>
            <summary className="muted flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-[13px] font-semibold">
              <ChevronDown className="h-4 w-4 shrink-0" />
              {t("Daha fazla")}
            </summary>
            <div className="mt-3 space-y-4">{moreGroups.map(renderGroup)}</div>
          </details>
        </nav>

        <div className="sidebar-footer shrink-0 border-t p-3">
          <div className="flex items-center justify-between rounded-xl px-2 py-2">
            <span className="flex items-center gap-2 text-xs font-medium"><span className="status-dot h-2 w-2 rounded-full" />{t("Sistem durumu")}</span>
            <span className="muted text-xs">{t("API bağlı")}</span>
          </div>
          <Link href="/preferences" className="footer-settings mt-1 flex items-center justify-between rounded-xl px-3 py-2.5 text-xs font-medium">
            <span className="flex items-center gap-2"><Settings2 className="h-4 w-4" />{t("Tercihleri düzenle")}</span><ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </aside>

      <div className="min-h-screen lg:pl-[250px]">
        <header className="app-header sticky top-0 z-30 flex h-[56px] items-center justify-between border-b px-3 sm:px-4 lg:px-5">
          <div className="flex min-w-0 items-center">
            <button onClick={() => setMobileOpen(true)} className="icon-button rounded-lg p-1.5 lg:hidden" aria-label={t("Menüyü aç")}><Menu className="h-[18px] w-[18px]" /></button>
          </div>
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-2.5">
            <NotificationDrawer />
            <LlmUsageButton />
            <ApifyUsageButton />
            <label className="language-picker inline-flex items-center gap-1 rounded-lg border px-2 text-xs font-medium" title={t("Dil")}>
              <Globe2 className="h-3.5 w-3.5" />
              <select
                aria-label={t("Dil")}
                value={locale}
                onChange={(event) => setLocale(event.target.value as "tr" | "en")}
                className="bg-transparent py-1.5 text-xs font-semibold outline-none"
              >
                <option value="tr">TR</option>
                <option value="en">EN</option>
              </select>
            </label>
            {themeButton}
            <div className="hidden sm:block"><CandidateHeader dense /></div>
          </div>
        </header>

        <main className="app-main min-h-[calc(100vh-56px)] px-4 py-5 sm:px-5 lg:px-6 lg:py-6 lg:pb-8">
          <div className="mx-auto w-full max-w-[1440px]">{children}</div>
        </main>
      </div>

      <nav className="mobile-nav fixed inset-x-0 bottom-0 z-30 grid-cols-5 gap-1 border-t px-2 pb-[max(env(safe-area-inset-bottom),0.5rem)] pt-2" aria-label={t("Mobil menü")}>
        {[
      { name: "Ana sayfa", href: "/", icon: LayoutDashboard },
          { name: "İlanlar", href: "/jobs", icon: Search },
          { name: "Alanlar", href: "/preferences", icon: Compass },
          { name: "Başvurular", href: "/kanban", icon: CheckSquare },
          { name: "Profil", href: "/setup", icon: UserRound },
        ].map((item) => {
          const Icon = item.icon;
          const active = isActive(pathname, item.href);
          return <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined} className={`mobile-nav-link flex flex-col items-center gap-1 rounded-xl py-1.5 text-xs ${active ? "active" : ""}`}><Icon className="h-[18px] w-[18px]" /><span>{t(item.name)}</span></Link>;
        })}
      </nav>
    </div>
  );
}
