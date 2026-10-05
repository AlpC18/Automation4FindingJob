"use client";

import Link from "next/link";
import { useLanguage } from "@/lib/i18n";
import type { ScanStatus } from "@/components/ScanStatusPanel";

interface EmptyFeedGuideProps {
  /** Listings exist in the feed but the on-page filters hide all of them. */
  hiddenByPageFilters: boolean;
  emptyState: ScanStatus["empty_state"];
  unavailable: boolean;
  onClearFilters: () => void;
}

interface Guidance {
  title: string;
  detail: string;
  fix: string;
  href?: string;
  action?: string;
}

export default function EmptyFeedGuide({ hiddenByPageFilters, emptyState, unavailable, onClearFilters }: EmptyFeedGuideProps) {
  const { translate: t } = useLanguage();
  const counts = emptyState?.counts || {};
  const filterDetails: Record<string, string> = {
    location_mismatch: t("En çok eleme konum filtresinden geldi: kaynakların döndürdüğü ilanların konumu seçtiğin konumla eşleşmedi."),
    work_mode_mismatch: t("En çok eleme çalışma şekli filtresinden geldi: ilanların çalışma şekli seçtiğin tercihle eşleşmedi."),
    low_quality: t("İlanların çoğu başlık, şirket veya açıklama eksik olduğu için elendi."),
    expired: t("İlanların çoğu süresi dolmuş olduğu için elendi."),
  };
  const filterFixes: Record<string, string> = {
    location_mismatch: t("Düzeltme: konumu genişlet (ör. ülke adı veya Remote) ve taramayı tekrar başlat."),
    work_mode_mismatch: t("Düzeltme: farklı bir çalışma şekli/konum ön ayarı seçip taramayı tekrar başlat."),
    low_quality: t("Düzeltme: rol adını daha yaygın bir ünvanla değiştirip tekrar tara."),
    expired: t("Düzeltme: rol adını genişletip tekrar tara; bu kaynakta güncel ilan az olabilir."),
  };

  const guidance: Record<string, Guidance> = {
    no_scan: { title: t("Sorun değil: henüz tarama yapılmadı"), detail: t("Kaynaklar hazır ama bu hesapta kayıtlı bir tarama yok."), fix: t("Düzeltme: yukarıdan rol ve konum seçip “Tarama başlat”a bas.") },
    source_setup: { title: t("Neden: taramaya hazır kaynak yok"), detail: t("Hiçbir kaynak yapılandırılmamış; tarama başlatılsa da ilan gelmez."), fix: t("Düzeltme: Kaynaklar sayfasında Actor ID ve API anahtarını kaydet."), href: "/sources", action: t("Kaynak ayarlarına git") },
    quota: { title: t("Neden: API kotası / günlük limit doldu"), detail: t("Son taramada kaynak, kota veya günlük çalıştırma limiti nedeniyle ilan döndürmedi. Filtrelerinle ilgili değil."), fix: t("Düzeltme: Kaynaklar sayfasında kota durumunu yenile; limit ertesi gün sıfırlanır veya ek bir anahtar ekleyebilirsin."), href: "/sources", action: t("Kota durumunu aç") },
    credentials: { title: t("Neden: API anahtarı veya Actor ayarı eksik/geçersiz"), detail: t("Son taramada kaynak kimlik doğrulama veya yapılandırma hatası verdi."), fix: t("Düzeltme: Kaynaklar sayfasında anahtarı yeniden kaydet ve “Bağlantıyı test et” ile doğrula."), href: "/sources", action: t("Anahtarı düzelt") },
    connection: { title: t("Neden: kaynağa bağlanılamadı"), detail: t("Son taramada kaynak sunucusuna ulaşılamadı veya sunucu hata döndürdü. Filtrelerinle ilgili değil."), fix: t("Düzeltme: internet bağlantını kontrol et ve birkaç dakika sonra taramayı tekrar başlat."), href: "/sources", action: t("Bağlantıyı test et") },
    source_error: { title: t("Neden: kaynak hata verdi"), detail: t("Son taramada kaynak beklenmeyen bir hata döndürdü; ilan alınamadı."), fix: t("Düzeltme: aşağıdaki hata mesajını Kaynaklar sayfasındaki ayarlarla karşılaştır."), href: "/sources", action: t("Kaynak ayarlarına git") },
    filters: { title: t("Neden: arama filtreleri tüm ilanları eledi"), detail: `${counts.raw_fetched ?? 0} ${t("ilan bulundu ama hiçbiri seçtiğin koşullara uymadı.")} ${filterDetails[emptyState?.dominant_filter || ""] || ""}`, fix: filterFixes[emptyState?.dominant_filter || ""] || t("Düzeltme: rol veya konum seçimini genişletip tekrar tara.") },
    no_results: { title: t("Neden: kaynaklar bu arama için ilan döndürmedi"), detail: t("Bağlantı ve anahtarlar çalıştı, hata yok; ancak bu rol/konum için sonuç gelmedi."), fix: t("Düzeltme: daha genel bir ünvan dene (ör. “Backend Developer”) veya konumu genişlet.") },
    all_processed: { title: t("Neden: bulunan ilanların hepsi zaten işlenmiş"), detail: t("Son taramadaki ilanlar daha önce kaydedilmiş, gizlenmiş veya başvuru sürecine alınmış."), fix: t("Düzeltme: farklı bir rol ile tara ya da başvurularını Kanban panelinden takip et."), href: "/kanban", action: t("Kanban panelini aç") },
  };

  const item: Guidance | null = hiddenByPageFilters
    ? { title: t("Neden: sayfadaki filtreler tüm ilanları gizliyor"), detail: t("Kayıtlı ilan var; bağlantı veya kota sorunu yok."), fix: t("Düzeltme: filtreleri temizle.") }
    : unavailable
      ? { title: t("Neden: backend'e ulaşılamıyor"), detail: t("Tarama durumu alınamadığı için neden belirlenemedi."), fix: t("Düzeltme: backend servisinin çalıştığını kontrol edip sayfayı yenile.") }
      : guidance[emptyState?.cause || "no_scan"] || guidance.no_scan;

  return (
    <div className="rounded-2xl border border-slate-800 bg-[#0e1524] p-8 text-center">
      <div className="mx-auto max-w-xl space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{t("0 ilan")}</p>
        <p className="font-semibold text-slate-100">{item.title}</p>
        <p className="text-xs text-slate-400">{item.detail}</p>
        {!hiddenByPageFilters && emptyState?.error && <p className="rounded-lg border border-rose-500/20 bg-rose-500/5 px-3 py-2 text-left text-xs text-rose-300">{emptyState.error}</p>}
        <p className="text-xs font-medium text-emerald-300">{item.fix}</p>
        <div className="flex flex-wrap justify-center gap-2 pt-1">
          {hiddenByPageFilters && <button type="button" onClick={onClearFilters} className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800">{t("Filtreleri temizle")}</button>}
          {!hiddenByPageFilters && item.href && <Link href={item.href} className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800">{item.action}</Link>}
        </div>
      </div>
    </div>
  );
}
