"use client";
import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  LayoutDashboard,
  Send,
  Sparkles,
  UserCheck,
  Calendar,
  DollarSign,
  GraduationCap,
  Target,
  FileText,
  Activity,
  Compass,
  ArrowRight,
  Zap,
  Mail,
  Award,
  Cpu,
} from "lucide-react";
import { useLanguage } from "@/lib/i18n";

interface ActionItem {
  id: string;
  name: string;
  category: "Navigasyon" | "Aksiyonlar";
  href?: string;
  icon: any;
  action?: () => void;
}

export default function CommandPalette() {
  const { translate: t } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const items: ActionItem[] = [
    { id: "dash", name: "Genel Bakış Dashboard", category: "Navigasyon", href: "/", icon: LayoutDashboard },
    { id: "auto", name: "Onay bekleyen başvurular", category: "Navigasyon", href: "/auto-apply", icon: Send },
    { id: "sem", name: "Anlamsal arama", category: "Navigasyon", href: "/semantic-search", icon: Sparkles },
    { id: "prof", name: "LinkedIn & GitHub Profil Optimizatörü", category: "Navigasyon", href: "/profile-optimizer", icon: UserCheck },
    { id: "fol", name: "Akıllı Takip & Mülakat Takvimi", category: "Navigasyon", href: "/follow-up", icon: Calendar },
    { id: "outreach", name: "Yöneticiye Doğrudan Ulaşma (Cold Outreach)", category: "Navigasyon", href: "/cold-outreach", icon: Mail },
    { id: "negotiator", name: "Maaş & Teklif Pazarlık Koçu", category: "Navigasyon", href: "/offer-negotiator", icon: Award },
    { id: "router", name: "Model yönlendirici", category: "Navigasyon", href: "/llm-router", icon: Cpu },
    { id: "onb", name: "Hızlı kurulum", category: "Navigasyon", href: "/onboarding", icon: Zap },
    { id: "star", name: "STAR Mülakat Hazırlık Koçu", category: "Navigasyon", href: "/star-prep", icon: Target },
    { id: "sal", name: "Maaş İstihbarat Arama Motoru", category: "Navigasyon", href: "/salary-intel", icon: DollarSign },
    { id: "ups", name: "Upskill & Öğrenme Yol Haritası", category: "Navigasyon", href: "/upskill", icon: GraduationCap },
    { id: "rep", name: "HTML Rapor Oluşturucu", category: "Navigasyon", href: "/reports", icon: FileText },
    { id: "port", name: "Portal Sağlık ve Scraper Durumu", category: "Navigasyon", href: "/portal-health", icon: Activity },
    { id: "car", name: "Kariyer Yolu Keşif Haritası", category: "Navigasyon", href: "/career-map", icon: Compass },
  ];

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      } else if (e.key === "Escape") {
        setIsOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setSearch("");
    }
  }, [isOpen]);

  const filteredItems = items.filter((item) =>
    `${t(item.name)} ${item.name}`.toLowerCase().includes(search.toLowerCase())
  );

  function executeItem(item: ActionItem) {
    setIsOpen(false);
    if (item.href) {
      router.push(item.href);
    } else if (item.action) {
      item.action();
    }
  }

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div
        className="w-full max-w-xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div className="flex items-center px-4 border-b border-slate-800">
          <Search className="w-5 h-5 text-slate-400 mr-3" />
          <input
            ref={inputRef}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("Sayfa veya aksiyon arayın... (Örn: 'vektör', 'başvuru', 'maaş')")}
            className="w-full py-4 bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none"
          />
          <kbd className="hidden sm:inline-block text-xs bg-slate-800 text-slate-400 px-2 py-1 rounded font-mono border border-slate-700">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filteredItems.length === 0 ? (
            <div className="text-center py-8 text-xs text-slate-400">{t("Eşleşen komut bulunamadı.")}</div>
          ) : (
            filteredItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => executeItem(item)}
                  className="w-full flex items-center justify-between p-3 rounded-xl hover:bg-slate-800/80 text-left transition-colors group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-slate-800 text-slate-400 group-hover:text-blue-400 group-hover:bg-blue-500/10 transition-colors">
                      <Icon className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-slate-200 group-hover:text-white">
                        {t(item.name)}
                      </div>
                      <div className="text-xs text-slate-400">{t(item.category)}</div>
                    </div>
                  </div>
                  <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-slate-300 transition-colors" />
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
