"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Check, ChevronRight, Compass, MapPin, Plus, Save, Sparkles, X } from "lucide-react";
import { fetchFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

const categories = [
  "Yazılım ve teknoloji", "Veri ve analitik", "Ürün ve tasarım",
  "Pazarlama ve içerik", "Satış ve müşteri", "Finans ve operasyon", "Sağlık ve eğitim",
];

const workModes = ["Uzaktan", "Hibrit", "Ofisten", "Esnek"];
const cardClass = "surface-card rounded-2xl border p-5 sm:p-6";

export default function PreferencesPage() {
  const { translate: t } = useLanguage();
  const [profile, setProfile] = useState<any>({});
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [roleSuggestions, setRoleSuggestions] = useState<any[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [customRole, setCustomRole] = useState("");
  const [location, setLocation] = useState("");
  const [workPreference, setWorkPreference] = useState("");
  const [skills, setSkills] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [followUpEmailEnabled, setFollowUpEmailEnabled] = useState(false);
  const [followUpEmailReady, setFollowUpEmailReady] = useState(false);
  const [savingEmailPreference, setSavingEmailPreference] = useState(false);
  const [emailPreferenceMessage, setEmailPreferenceMessage] = useState("");
  const [smtpForm, setSmtpForm] = useState({ host: "", port: 587, username: "", password: "", from_email: "", use_tls: true });
  const [smtpSource, setSmtpSource] = useState("not_configured");
  const [smtpBusy, setSmtpBusy] = useState(false);
  const [smtpTestBusy, setSmtpTestBusy] = useState(false);
  const [smtpMessage, setSmtpMessage] = useState("");

  useEffect(() => {
    fetchFromApi("/setup/profile")
      .then((response) => {
        const data = response.profile || {};
        const roles = Array.isArray(data.target_roles) && data.target_roles.length
          ? data.target_roles
          : (data.target_role || "").split(/[,;\n]/).map((role: string) => role.trim()).filter(Boolean);
        setProfile(data);
        setSelectedCategories(Array.isArray(data.target_categories) ? data.target_categories : []);
        setSelectedRoles(roles);
        setLocation(data.location || "");
        setWorkPreference(data.work_preference || "");
        setSkills(Array.isArray(data.skills) ? data.skills.join(", ") : "");
      })
      .catch(() => {
        setMessage("Profil bilgileri yüklenemedi. API bağlantısını kontrol edip yeniden deneyin.");
      })
      .finally(() => setLoading(false));
    fetchFromApi("/setup/notification-preferences")
      .then((data) => {
        setFollowUpEmailEnabled(Boolean(data.follow_up_email_reminders));
        setFollowUpEmailReady(Boolean(data.smtp_configured && data.recipient_configured));
      })
      .catch(() => setFollowUpEmailReady(false));
    fetchFromApi("/notifications/smtp")
      .then((data) => {
        setSmtpForm({ host: data.host || "", port: Number(data.port) || 587, username: data.username || "", password: "", from_email: data.from_email || "", use_tls: data.use_tls !== false });
        setSmtpSource(data.source || "not_configured");
      })
      .catch(() => setSmtpMessage(t("SMTP ayarları alınamadı.")));
  }, []);

  const visibleRoles = useMemo(() => roleSuggestions.map((role) => role.title).filter(Boolean), [roleSuggestions]);

  async function loadRoleSuggestions() {
    if (!selectedCategories.length) {
      setMessage("Önce ilgilendiğin en az bir kategori seç.");
      return;
    }
    setLoadingSuggestions(true);
    setMessage("");
    try {
      const result = await fetchFromApi("/setup/discovered_roles");
      setRoleSuggestions(Array.isArray(result.roles) ? result.roles : []);
      if (!result.roles?.length) setMessage("Profil bilgilerine göre öneri bulunamadı. Kendi pozisyonunu ekleyebilirsin.");
    } catch {
      setMessage("Pozisyon önerileri alınamadı. Kendi pozisyonunu ekleyebilirsin.");
    } finally {
      setLoadingSuggestions(false);
    }
  }

  function toggleValue(value: string, current: string[], update: (next: string[]) => void) {
    update(current.includes(value) ? current.filter((item) => item !== value) : [...current, value]);
    setMessage("");
  }

  function addCustomRole() {
    const value = customRole.trim();
    if (value && !selectedRoles.includes(value)) setSelectedRoles((current) => [...current, value]);
    setCustomRole("");
  }

  async function savePreferences() {
    setSaving(true);
    setMessage("");
    try {
      const nextProfile = {
        ...profile,
        full_name: profile.full_name || "",
        email: profile.email || "",
        target_role: selectedRoles[0] || "",
        target_roles: selectedRoles,
        target_categories: selectedCategories,
        years_of_experience: Number(profile.years_of_experience) || 0,
        skills: skills.split(",").map((skill) => skill.trim()).filter(Boolean),
        location,
        work_preference: workPreference,
      };
      await fetchFromApi("/setup/update_profile", { method: "POST", body: JSON.stringify(nextProfile) });
      setProfile(nextProfile);
      setMessage("Tercihlerin kaydedildi. İlan eşleşmeleri bu alanlara göre kişiselleştirilecek.");
    } catch {
      setMessage("Tercihler kaydedilemedi. Lütfen profilini tamamlayıp tekrar dene.");
    } finally {
      setSaving(false);
    }
  }

  async function setFollowUpEmailPreference(enabled: boolean) {
    setSavingEmailPreference(true);
    setEmailPreferenceMessage("");
    try {
      const result = await fetchFromApi("/setup/notification-preferences", {
        method: "PUT",
        body: JSON.stringify({ enabled }),
      });
      setFollowUpEmailEnabled(Boolean(result.follow_up_email_reminders));
      setFollowUpEmailReady(Boolean(result.smtp_configured && result.recipient_configured));
      setEmailPreferenceMessage(enabled ? t("E-posta takip hatırlatmaları açıldı.") : t("E-posta takip hatırlatmaları kapatıldı."));
    } catch {
      setEmailPreferenceMessage(t("Açmak için profil e-postası ve SMTP ayarlarının tamamlanması gerekir."));
    } finally {
      setSavingEmailPreference(false);
    }
  }

  async function saveSmtpSettings() {
    setSmtpBusy(true);
    setSmtpMessage("");
    try {
      const result = await fetchFromApi("/notifications/smtp", {
        method: "PUT",
        body: JSON.stringify({ ...smtpForm, port: Number(smtpForm.port) || 587 }),
      });
      setSmtpForm((current) => ({ ...current, password: "" }));
      setSmtpSource(result.source || "account");
      const preference = await fetchFromApi("/setup/notification-preferences");
      setFollowUpEmailReady(Boolean(preference.smtp_configured && preference.recipient_configured));
      setSmtpMessage(t("SMTP ayarları şifreli olarak kaydedildi."));
    } catch (error: any) {
      setSmtpMessage(error.message || t("SMTP ayarları kaydedilemedi."));
    } finally { setSmtpBusy(false); }
  }

  async function testSmtpSettings() {
    setSmtpTestBusy(true);
    setSmtpMessage("");
    try {
      const result = await fetchFromApi("/notifications/smtp/test", { method: "POST", body: "{}" });
      setSmtpMessage(result.message || t("SMTP bağlantı sonucu: {status}", { status: result.status || "unknown" }));
    } catch (error: any) {
      setSmtpMessage(error.message || t("SMTP bağlantısı doğrulanamadı."));
    } finally { setSmtpTestBusy(false); }
  }

  async function resetSmtpSettings() {
    setSmtpBusy(true);
    setSmtpMessage("");
    try {
      const result = await fetchFromApi("/notifications/smtp", { method: "DELETE" });
      setSmtpSource(result.source || "environment");
      setSmtpForm({ host: result.host || "", port: Number(result.port) || 587, username: result.username || "", password: "", from_email: result.from_email || "", use_tls: result.use_tls !== false });
      const preference = await fetchFromApi("/setup/notification-preferences");
      setFollowUpEmailReady(Boolean(preference.smtp_configured && preference.recipient_configured));
      setSmtpMessage(t("Hesap SMTP ayarları kaldırıldı."));
    } catch (error: any) {
      setSmtpMessage(error.message || t("SMTP ayarları kaldırılamadı."));
    } finally { setSmtpBusy(false); }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-7">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <div className="eyebrow mb-2 flex items-center gap-2"><Compass className="h-4 w-4" />{t("KARİYER TERCİHLERİ")}</div>
          <h2 className="text-3xl font-semibold tracking-tight sm:text-[34px]">{t("Sana uygun işleri seç")}</h2>
          <p className="muted mt-2 max-w-2xl text-sm leading-6">{t("İlgilendiğin sektörleri ve pozisyonları belirle. İlan keşfi ve öneriler bu tercihlere göre şekillensin.")}</p>
        </div>
        <button type="button" onClick={savePreferences} disabled={saving || loading} className="primary-button inline-flex h-11 items-center justify-center gap-2 rounded-xl px-5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60">
          <Save className="h-4 w-4" />{saving ? t("Kaydediliyor…") : t("Tercihleri kaydet")}
        </button>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-5">
          <section className={cardClass}>
            <div className="mb-5 flex items-start justify-between gap-4">
              <div><div className="flex items-center gap-2 text-base font-semibold"><span className="step-number">01</span>{t("Sektör kategorileri")}</div><p className="muted mt-2 text-xs">{t("Birden fazla alan seçebilirsin.")}</p></div>
              <span className="muted text-xs">{selectedCategories.length} {t("seçili")}</span>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {categories.map((category) => {
                const selected = selectedCategories.includes(category);
                return <button key={category} type="button" onClick={() => toggleValue(category, selectedCategories, setSelectedCategories)} aria-pressed={selected} className={`choice-card flex min-h-12 items-center justify-between gap-3 rounded-xl border px-4 py-3 text-left text-sm font-medium transition-colors ${selected ? "selected" : ""}`}>
                  <span>{t(category)}</span>{selected ? <Check className="h-4 w-4 shrink-0" /> : <ChevronRight className="muted h-4 w-4 shrink-0" />}
                </button>;
              })}
            </div>
          </section>

          <section className={cardClass}>
            <div className="mb-5 flex items-start justify-between gap-4">
              <div><div className="flex items-center gap-2 text-base font-semibold"><span className="step-number">02</span>{t("Pozisyon ve uzmanlık alanları")}</div><p className="muted mt-2 text-xs">{t("Seçtiğin kategorilere uygun roller gösterilir. Birden fazla seçebilirsin.")}</p></div>
              <span className="muted text-xs">{selectedRoles.length} {t("seçili")}</span>
            </div>
            <button type="button" onClick={loadRoleSuggestions} disabled={loadingSuggestions || loading} className="secondary-button mb-4 inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-3.5 text-xs font-semibold disabled:opacity-60"><Sparkles className="h-4 w-4" />{loadingSuggestions ? t("Profiline göre aranıyor…") : t("Profilime göre rol öner")}</button>
            {visibleRoles.length ? <div className="flex flex-wrap gap-2">
              {roleSuggestions.map((suggestion) => {
                const role = suggestion.title;
                const selected = selectedRoles.includes(role);
                return <button key={suggestion.id || role} type="button" onClick={() => toggleValue(role, selectedRoles, setSelectedRoles)} aria-pressed={selected} className={`choice-chip rounded-full border px-3.5 py-2 text-xs font-medium transition-colors ${selected ? "selected" : ""}`}>
                  {selected && <Check className="mr-1.5 inline h-3.5 w-3.5" />}{role}
                </button>;
              })}
            </div> : <div className="empty-hint rounded-xl border border-dashed p-5 text-center text-sm">{t("Kategorilerini seçtikten sonra profiline göre dinamik rol önerileri alabilir veya kendi pozisyonunu ekleyebilirsin.")}</div>}
            <div className="mt-5 flex flex-col gap-2 sm:flex-row">
              <input value={customRole} onChange={(event) => setCustomRole(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); addCustomRole(); } }} placeholder={t("Kendi pozisyonunu ekle")} className="field-input h-11 flex-1 rounded-xl border px-3.5 text-sm" />
              <button type="button" onClick={addCustomRole} className="secondary-button inline-flex h-11 items-center justify-center gap-2 rounded-xl border px-4 text-sm font-medium"><Plus className="h-4 w-4" />{t("Alan ekle")}</button>
            </div>
            {selectedRoles.filter((role) => !visibleRoles.includes(role)).length > 0 && <div className="mt-4 flex flex-wrap gap-2">
              {selectedRoles.filter((role) => !visibleRoles.includes(role)).map((role) => <span key={role} className="choice-chip selected inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs">{role}<button type="button" onClick={() => setSelectedRoles((current) => current.filter((item) => item !== role))} aria-label={`${role} alanını kaldır`}><X className="h-3.5 w-3.5" /></button></span>)}
            </div>}
          </section>

          <section className={cardClass}>
            <div className="mb-5"><div className="flex items-center gap-2 text-base font-semibold"><span className="step-number">03</span>{t("Çalışma koşulları")}</div><p className="muted mt-2 text-xs">{t("İlanları konumuna ve çalışma biçimine göre daralt.")}</p></div>
            <label className="muted mb-2 block text-xs font-medium" htmlFor="job-location">{t("Tercih edilen konum")}</label>
            <div className="relative mb-5"><MapPin className="muted absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2" /><input id="job-location" value={location} onChange={(event) => setLocation(event.target.value)} placeholder={t("Örn. İstanbul, Türkiye veya Avrupa")} className="field-input h-11 w-full rounded-xl border pl-10 pr-3.5 text-sm" /></div>
            <div className="muted mb-2 block text-xs font-medium">{t("Çalışma biçimi")}</div>
            <div className="flex flex-wrap gap-2">{workModes.map((mode) => <button key={mode} type="button" onClick={() => setWorkPreference(workPreference === mode ? "" : mode)} aria-pressed={workPreference === mode} className={`choice-chip rounded-full border px-4 py-2 text-xs font-medium ${workPreference === mode ? "selected" : ""}`}>{t(mode)}</button>)}</div>
          </section>

          <section className={cardClass}>
            <div className="mb-4 flex items-center gap-2 text-base font-semibold"><span className="step-number">04</span>{t("Beceriler")}</div>
            <p className="muted mb-3 text-xs">{t("İlan eşleşmelerini iyileştirmek için becerilerini virgülle ayırarak yaz.")}</p>
            <textarea value={skills} onChange={(event) => setSkills(event.target.value)} rows={3} placeholder={t("Örn. React, Python, ürün analitiği, İngilizce")} className="field-input w-full resize-y rounded-xl border p-3.5 text-sm leading-6" />
          </section>

          <section className={cardClass}>
            <div className="mb-1 text-base font-semibold">{t("E-posta bildirimleri")}</div>
            <p className="muted mb-4 text-xs">{t("SMTP bilgileri bu hesaba özel şifreli saklanır; parola tekrar gösterilmez. Test bağlantısı e-posta göndermez.")}</p>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border px-3 py-2 text-xs">
              <span>{t("SMTP ayar kaynağı")}</span>
              <span className="font-medium">{smtpSource === "account" ? t("Hesaba özel · şifreli") : smtpSource === "environment" ? t("Sunucu ortam ayarları") : t("Yapılandırılmadı")}</span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="muted text-xs">{t("SMTP sunucusu")}<input value={smtpForm.host} onChange={(event) => setSmtpForm((current) => ({ ...current, host: event.target.value }))} placeholder="smtp.example.com" autoComplete="off" className="field-input mt-1 h-10 w-full rounded-xl border px-3 text-sm" /></label>
              <label className="muted text-xs">{t("SMTP portu")}<input type="number" min={1} max={65535} value={smtpForm.port} onChange={(event) => setSmtpForm((current) => ({ ...current, port: Number(event.target.value) }))} className="field-input mt-1 h-10 w-full rounded-xl border px-3 text-sm" /></label>
              <label className="muted text-xs">{t("SMTP kullanıcı adı")}<input value={smtpForm.username} onChange={(event) => setSmtpForm((current) => ({ ...current, username: event.target.value }))} autoComplete="username" className="field-input mt-1 h-10 w-full rounded-xl border px-3 text-sm" /></label>
              <label className="muted text-xs">{t("SMTP parolası")}<input type="password" value={smtpForm.password} onChange={(event) => setSmtpForm((current) => ({ ...current, password: event.target.value }))} placeholder={t("Mevcut parolayı korumak için boş bırak")} autoComplete="new-password" className="field-input mt-1 h-10 w-full rounded-xl border px-3 text-sm" /></label>
              <label className="muted text-xs sm:col-span-2">{t("Gönderici e-posta adresi")}<input type="email" value={smtpForm.from_email} onChange={(event) => setSmtpForm((current) => ({ ...current, from_email: event.target.value }))} autoComplete="email" className="field-input mt-1 h-10 w-full rounded-xl border px-3 text-sm" /></label>
            </div>
            <label className="mt-3 flex items-center gap-2 text-xs"><input type="checkbox" checked={smtpForm.use_tls} onChange={(event) => setSmtpForm((current) => ({ ...current, use_tls: event.target.checked }))} className="accent-emerald-500" />{t("STARTTLS kullan (önerilir)")}</label>
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="button" onClick={saveSmtpSettings} disabled={smtpBusy || !smtpForm.host || !smtpForm.from_email} className="primary-button rounded-xl px-4 py-2 text-xs font-semibold disabled:opacity-50">{smtpBusy ? t("Kaydediliyor…") : t("SMTP ayarlarını şifreli kaydet")}</button>
              <button type="button" onClick={testSmtpSettings} disabled={smtpBusy || smtpTestBusy || smtpSource === "not_configured"} className="secondary-button rounded-xl border px-4 py-2 text-xs font-semibold disabled:opacity-50">{smtpTestBusy ? t("Bağlantı kontrol ediliyor…") : t("SMTP bağlantısını test et")}</button>
              <button type="button" onClick={resetSmtpSettings} disabled={smtpBusy || smtpSource !== "account"} className="secondary-button rounded-xl border px-4 py-2 text-xs font-semibold disabled:opacity-50">{t("Hesap SMTP ayarlarını kaldır")}</button>
            </div>
            {smtpMessage && <p role="status" className="mt-3 text-xs text-emerald-400">{smtpMessage}</p>}
            <div className="my-5 border-t" />
            <label className="flex items-start gap-3 text-sm">
              <input type="checkbox" checked={followUpEmailEnabled} onChange={(event) => setFollowUpEmailPreference(event.target.checked)} disabled={!followUpEmailReady || savingEmailPreference || loading} className="mt-1 accent-emerald-500" />
              <span><span className="font-medium">{t("Başvuru takip zamanı geldiğinde bana e-posta gönder")}</span><span className="muted mt-1 block text-xs leading-5">{t("E-posta yalnızca sana gelir; hiçbir başvuru veya takip mesajı işverene otomatik gönderilmez.")}</span></span>
            </label>
            {!followUpEmailReady && <p className="muted mt-3 text-xs leading-5">{t("Bu seçeneği açmak için profil e-postası ve SMTP ayarları gereklidir.")}</p>}
            {emailPreferenceMessage && <p role="status" className="mt-3 text-xs text-emerald-400">{emailPreferenceMessage}</p>}
          </section>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
          <div className="summary-card rounded-2xl border p-5">
            <div className="flex items-center gap-2 text-sm font-semibold"><Sparkles className="h-4 w-4" />{t("Tercih özeti")}</div>
            <p className="muted mt-1 text-xs">{t("Seçimlerin ilan arama deneyimini kişiselleştirir.")}</p>
            <div className="summary-divider my-4 border-t" />
            <div className="summary-row"><span className="muted">{t("Kategoriler")}</span><strong>{selectedCategories.length}</strong></div>
            <div className="summary-row mt-3"><span className="muted">{t("Pozisyonlar")}</span><strong>{selectedRoles.length}</strong></div>
            <div className="summary-row mt-3"><span className="muted">{t("Çalışma biçimi")}</span><strong>{workPreference ? t(workPreference) : t("Seçilmedi")}</strong></div>
            <div className="summary-divider my-4 border-t" />
            {selectedRoles.length ? <div className="flex flex-wrap gap-1.5">{selectedRoles.slice(0, 5).map((role) => <span key={role} className="summary-tag rounded-lg px-2 py-1 text-[10px]">{t(role)}</span>)}{selectedRoles.length > 5 && <span className="muted px-1 py-1 text-[10px]">+{selectedRoles.length - 5}</span>}</div> : <p className="muted text-xs">{t("Henüz pozisyon seçmedin.")}</p>}
          </div>
          {message && <div role="status" className={`notice-card rounded-xl border p-4 text-xs leading-5 ${message.startsWith("Tercihlerin") ? "success" : ""}`}>{message}</div>}
          <div className="help-card rounded-2xl p-5"><div className="text-sm font-semibold">{t("Profilini de tamamla")}</div><p className="muted mt-1 text-xs leading-5">{t("Daha isabetli eşleşmeler için deneyim ve özgeçmiş bilgilerini ekle.")}</p><Link href="/setup" className="inline-flex items-center gap-1.5 pt-4 text-xs font-semibold">{t("Profile git")}<ChevronRight className="h-3.5 w-3.5" /></Link></div>
          {loading && <p className="muted text-center text-xs">{t("Profil bilgileri yükleniyor…")}</p>}
        </aside>
      </div>
    </div>
  );
}
