"use client";

import { useState } from "react";
import { AlertTriangle, Download, ShieldCheck, Trash2 } from "lucide-react";
import { requestFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

export default function PrivacyPage() {
  const { translate: t } = useLanguage();
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState<"export" | "delete" | null>(null);
  const [notice, setNotice] = useState("");

  async function exportData() {
    setBusy("export");
    setNotice("");
    try {
      const response = await requestFromApi("/system/data/export");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = response.headers.get("content-disposition")?.match(/filename="?([^";]+)"?/)?.[1] || "career-agent-data.json";
      anchor.click();
      URL.revokeObjectURL(url);
      setNotice(t("Dışa aktarma indirildi."));
    } catch (error: any) {
      setNotice(error.message || "Dışa aktarma başarısız.");
    } finally {
      setBusy(null);
    }
  }

  async function deleteData() {
    if (confirmation !== "DELETE") return;
    setBusy("delete");
    setNotice("");
    try {
      const response = await requestFromApi("/system/data", {
        method: "DELETE",
        body: JSON.stringify({ confirmation }),
      });
      const result = await response.json();
      setConfirmation("");
      setNotice(t(result.message || "Çalışma alanı verileri silindi. Giriş hesabın korunuyor."));
    } catch (error: any) {
      setNotice(error.message || "Veriler silinemedi.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <div className="eyebrow mb-2 flex items-center gap-2"><ShieldCheck className="h-4 w-4" />{t("HESAP KONTROLLERİ")}</div>
        <h2 className="text-3xl font-semibold tracking-tight">{t("Verilerini kontrol et")}</h2>
        <p className="muted mt-2 text-sm">{t("Çalışma alanı verilerini dışa aktar veya geri alınamayacak şekilde sil.")}</p>
      </header>

      {notice && <div role="status" className="notice-card success rounded-xl border p-4 text-sm">{notice}</div>}

      <section className="surface-card space-y-4 rounded-2xl border p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <span className="step-number"><Download className="h-4 w-4" /></span>
          <div><h3 className="font-semibold">{t("Verileri dışa aktar")}</h3><p className="muted mt-1 text-sm">{t("JSON dosyasını indir")}</p></div>
        </div>
        <p className="muted text-xs leading-5">{t("API anahtarları, oturum çerezleri ve OAuth erişim anahtarları güvenlik için dışa aktarıma dahil edilmez.")}</p>
        <button type="button" onClick={exportData} disabled={busy !== null} className="secondary-button inline-flex h-10 items-center gap-2 rounded-xl border px-4 text-sm font-semibold disabled:opacity-50">
          <Download className="h-4 w-4" />{busy === "export" ? t("Dışa aktarma hazırlanıyor…") : t("Verileri dışa aktar")}
        </button>
      </section>

      <section className="rounded-2xl border border-rose-500/30 bg-rose-500/[0.04] p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 text-rose-400"><AlertTriangle className="h-5 w-5" /></span>
          <div><h3 className="font-semibold">{t("Çalışma alanı verilerini sil")}</h3><p className="muted mt-1 text-sm leading-6">{t("Bu işlem profilini, ilanlarını, başvurularını, kaynak ayarlarını ve bağlantı bilgilerini siler. Giriş hesabın korunur. Bu işlem geri alınamaz.")}</p></div>
        </div>
        <label className="mt-5 block text-xs font-medium" htmlFor="delete-confirmation">{t("Onaylamak için DELETE yaz")}</label>
        <input id="delete-confirmation" autoComplete="off" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className="field-input mt-2 h-10 w-full rounded-xl border px-3 text-sm sm:max-w-xs" />
        <button type="button" onClick={deleteData} disabled={confirmation !== "DELETE" || busy !== null} className="mt-4 inline-flex min-h-10 items-center gap-2 rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 text-sm font-semibold text-rose-400 transition-colors hover:bg-rose-500/15 disabled:cursor-not-allowed disabled:opacity-40">
          <Trash2 className="h-4 w-4" />{busy === "delete" ? t("Veriler siliniyor…") : t("Tüm çalışma alanı verilerini sil")}
        </button>
      </section>
    </div>
  );
}
