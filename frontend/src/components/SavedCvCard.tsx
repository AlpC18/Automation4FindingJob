"use client";

import { useEffect, useState } from "react";
import { Download, FileCheck2, Trash2, Upload } from "lucide-react";
import { buildApiUrl, fetchFromApi, requestFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

type SavedCv = { filename: string; size_bytes: number; page_count: number | null; uploaded_at: string };

const FIELD_LABELS: Record<string, string> = {
  full_name: "Ad soyad", email: "E-posta", phone: "Telefon", location: "Konum", target_role: "Hedef rol",
  github_url: "GitHub", summary: "Özet", years_of_experience: "Deneyim yılı", skills: "Beceriler",
  languages: "Diller", experience: "Deneyim", education: "Eğitim",
};

/** One upload keeps the CV file and saves the profile from it; shown at the top of the profile page. */
export default function SavedCvCard({ onSaved }: { onSaved?: () => void | Promise<void> }) {
  const { translate: t } = useLanguage();
  const [cv, setCv] = useState<SavedCv | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [filled, setFilled] = useState<string[]>([]);
  const [missing, setMissing] = useState<string[]>([]);

  useEffect(() => {
    fetchFromApi<{ cv: SavedCv | null }>("/setup/cv").then((result) => setCv(result.cv)).catch(() => setMessage(t("Kayıtlı CV bilgisi alınamadı.")));
  }, []);

  const labels = (names: string[]) => names.map((name) => t(FIELD_LABELS[name] || name)).join(", ");

  async function upload(file?: File) {
    if (!file) return;
    setMessage("");
    setFilled([]);
    if (!/\.(pdf|docx)$/i.test(file.name)) {
      setMessage(t("Lütfen PDF veya DOCX biçiminde bir CV seç."));
      return;
    }
    setBusy(true);
    try {
      const body = new FormData();
      body.append("file", file);
      const response = await requestFromApi("/setup/cv", { method: "POST", body });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || t("CV kaydedilemedi."));
      setCv(result.cv);
      setFilled(result.filled_fields || []);
      setMissing(result.missing_fields || []);
      setMessage(t("CV'n ve profilin kaydedildi."));
      await onSaved?.();
    } catch (error: any) {
      setMessage(error.message || t("CV kaydedilemedi."));
    } finally {
      setBusy(false);
    }
  }

  async function download() {
    try {
      const response = await requestFromApi("/setup/cv/download");
      if (!response.ok) throw new Error();
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = cv?.filename || "cv";
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setMessage(t("CV indirilemedi."));
    }
  }

  async function remove() {
    if (!window.confirm(t("Kayıtlı CV dosyası silinsin mi? Profil bilgilerin kalır."))) return;
    try {
      await fetchFromApi("/setup/cv", { method: "DELETE" });
      setCv(null);
      setFilled([]);
      setMessage(t("Kayıtlı CV dosyası silindi."));
    } catch {
      setMessage(t("CV silinemedi."));
    }
  }

  return (
    <section className="career-card" aria-label={t("Kayıtlı CV")}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-sm font-semibold"><FileCheck2 className="h-4 w-4" />{t("Kayıtlı CV")}</h2>
          {cv ? (
            <p className="muted mt-1 break-words text-xs">
              {cv.filename} · {Math.max(1, Math.round(cv.size_bytes / 1024))} KB · {t("yüklendi")}: {String(cv.uploaded_at).slice(0, 16)}
            </p>
          ) : (
            <p className="muted mt-1 text-xs">{t("Henüz CV kaydetmedin. Bir kez yükle; dosyan saklanır ve profilin ondan doldurulur.")}</p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className={`primary-button inline-flex cursor-pointer items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold ${busy ? "pointer-events-none opacity-60" : ""}`}>
            <Upload className="h-4 w-4" />
            {busy ? t("Kaydediliyor…") : cv ? t("Yeni CV yükle") : t("CV yükle ve kaydet")}
            <input type="file" accept=".pdf,.docx" className="sr-only" disabled={busy} onChange={async (event) => { const input = event.currentTarget; await upload(input.files?.[0]); input.value = ""; }} />
          </label>
          {cv && <button type="button" onClick={download} className="secondary-button inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold"><Download className="h-4 w-4" />{t("İndir")}</button>}
          {cv && <button type="button" onClick={remove} className="secondary-button inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold"><Trash2 className="h-4 w-4" />{t("Sil")}</button>}
        </div>
      </div>
      <div role="status" aria-live="polite" className="mt-3 space-y-1 text-xs">
        {message && <p>{message}</p>}
        {filled.length > 0 && <p className="muted">{t("CV'den doldurulan alanlar")}: {labels(filled)}</p>}
        {missing.length > 0 && <p className="text-amber-300">{t("CV'de bulunamadı, aşağıdan kendin ekle")}: {labels(missing)}</p>}
      </div>
    </section>
  );
}
