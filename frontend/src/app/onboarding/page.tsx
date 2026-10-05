"use client";
import { notify } from "@/lib/notify";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, ArrowRight, Search, MapPin, Check } from "lucide-react";
import { fetchFromApi, requestFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import SetupSteps from "@/components/SetupSteps";
import CvImportReview, { type CvAiAnalysis, type CvProfileFields, type CvQualityReport } from "@/components/CvImportReview";

type LocalizedOption = { value: string; tr: string; en: string };

const ROLE_GROUPS: { id: string; tr: string; en: string; roles: LocalizedOption[] }[] = [
  { id: "technology", tr: "Teknoloji & Yazılım", en: "Technology & Software", roles: [
    { value: "Software Engineer", tr: "Yazılım Mühendisi", en: "Software Engineer" },
    { value: "Computer Engineer", tr: "Bilgisayar Mühendisi", en: "Computer Engineer" },
    { value: "Full-Stack Developer", tr: "Full-Stack Geliştirici", en: "Full-Stack Developer" },
    { value: "Frontend Developer", tr: "Frontend Geliştirici", en: "Frontend Developer" },
    { value: "Backend Developer", tr: "Backend Geliştirici", en: "Backend Developer" },
    { value: "Mobile App Developer", tr: "Mobil Uygulama Geliştiricisi", en: "Mobile App Developer" },
    { value: "iOS Developer", tr: "iOS Geliştiricisi", en: "iOS Developer" },
    { value: "Android Developer", tr: "Android Geliştiricisi", en: "Android Developer" },
    { value: "Data Engineer", tr: "Veri Mühendisi", en: "Data Engineer" },
    { value: "Data Analyst", tr: "Veri Analisti", en: "Data Analyst" },
    { value: "Data Scientist", tr: "Veri Bilimci", en: "Data Scientist" },
    { value: "Machine Learning Engineer", tr: "Makine Öğrenmesi Mühendisi", en: "Machine Learning Engineer" },
    { value: "AI Engineer", tr: "Yapay Zekâ Mühendisi", en: "AI Engineer" },
    { value: "DevOps Engineer", tr: "DevOps Mühendisi", en: "DevOps Engineer" },
    { value: "Cloud Engineer", tr: "Bulut Mühendisi", en: "Cloud Engineer" },
    { value: "Site Reliability Engineer", tr: "Site Reliability Mühendisi", en: "Site Reliability Engineer" },
    { value: "Cybersecurity Analyst", tr: "Siber Güvenlik Analisti", en: "Cybersecurity Analyst" },
    { value: "QA Automation Engineer", tr: "QA Otomasyon Mühendisi", en: "QA Automation Engineer" },
    { value: "Embedded Systems Engineer", tr: "Gömülü Sistemler Mühendisi", en: "Embedded Systems Engineer" },
    { value: "Network Engineer", tr: "Ağ Mühendisi", en: "Network Engineer" },
    { value: "IT Support Specialist", tr: "BT Destek Uzmanı", en: "IT Support Specialist" },
    { value: "UX/UI Designer", tr: "UX/UI Tasarımcısı", en: "UX/UI Designer" },
  ] },
  { id: "business", tr: "İş & Yönetim", en: "Business & Management", roles: [
    { value: "Business Analyst", tr: "İş Analisti", en: "Business Analyst" },
    { value: "Product Manager", tr: "Ürün Yöneticisi", en: "Product Manager" },
    { value: "Project Manager", tr: "Proje Yöneticisi", en: "Project Manager" },
    { value: "Program Manager", tr: "Program Yöneticisi", en: "Program Manager" },
    { value: "Operations Manager", tr: "Operasyon Yöneticisi", en: "Operations Manager" },
    { value: "Management Consultant", tr: "Yönetim Danışmanı", en: "Management Consultant" },
    { value: "Supply Chain Analyst", tr: "Tedarik Zinciri Analisti", en: "Supply Chain Analyst" },
    { value: "Procurement Specialist", tr: "Satın Alma Uzmanı", en: "Procurement Specialist" },
  ] },
  { id: "finance", tr: "Finans & Muhasebe", en: "Finance & Accounting", roles: [
    { value: "Financial Analyst", tr: "Finansal Analist", en: "Financial Analyst" },
    { value: "Accountant", tr: "Muhasebeci", en: "Accountant" },
    { value: "Financial Controller", tr: "Finans Kontrolörü", en: "Financial Controller" },
    { value: "Auditor", tr: "Denetçi", en: "Auditor" },
    { value: "Risk Analyst", tr: "Risk Analisti", en: "Risk Analyst" },
    { value: "Investment Analyst", tr: "Yatırım Analisti", en: "Investment Analyst" },
    { value: "Financial Planning Analyst", tr: "Finansal Planlama Analisti", en: "Financial Planning Analyst" },
  ] },
  { id: "sales-marketing", tr: "Satış & Pazarlama", en: "Sales & Marketing", roles: [
    { value: "Sales Representative", tr: "Satış Temsilcisi", en: "Sales Representative" },
    { value: "Account Executive", tr: "Müşteri Portföy Yöneticisi", en: "Account Executive" },
    { value: "Business Development Manager", tr: "İş Geliştirme Yöneticisi", en: "Business Development Manager" },
    { value: "Digital Marketing Specialist", tr: "Dijital Pazarlama Uzmanı", en: "Digital Marketing Specialist" },
    { value: "Growth Marketing Manager", tr: "Büyüme Pazarlaması Yöneticisi", en: "Growth Marketing Manager" },
    { value: "SEO Specialist", tr: "SEO Uzmanı", en: "SEO Specialist" },
    { value: "Content Strategist", tr: "İçerik Stratejisti", en: "Content Strategist" },
    { value: "Brand Manager", tr: "Marka Yöneticisi", en: "Brand Manager" },
  ] },
  { id: "healthcare", tr: "Sağlık & Yaşam Bilimleri", en: "Healthcare & Life Sciences", roles: [
    { value: "Registered Nurse", tr: "Hemşire", en: "Registered Nurse" },
    { value: "Physician", tr: "Doktor", en: "Physician" },
    { value: "Clinical Research Associate", tr: "Klinik Araştırma Uzmanı", en: "Clinical Research Associate" },
    { value: "Healthcare Data Analyst", tr: "Sağlık Verisi Analisti", en: "Healthcare Data Analyst" },
    { value: "Medical Laboratory Scientist", tr: "Tıbbi Laboratuvar Uzmanı", en: "Medical Laboratory Scientist" },
    { value: "Pharmacist", tr: "Eczacı", en: "Pharmacist" },
  ] },
  { id: "engineering", tr: "Mühendislik & Üretim", en: "Engineering & Manufacturing", roles: [
    { value: "Mechanical Engineer", tr: "Makine Mühendisi", en: "Mechanical Engineer" },
    { value: "Electrical Engineer", tr: "Elektrik Mühendisi", en: "Electrical Engineer" },
    { value: "Civil Engineer", tr: "İnşaat Mühendisi", en: "Civil Engineer" },
    { value: "Industrial Engineer", tr: "Endüstri Mühendisi", en: "Industrial Engineer" },
    { value: "Automation Engineer", tr: "Otomasyon Mühendisi", en: "Automation Engineer" },
    { value: "Quality Engineer", tr: "Kalite Mühendisi", en: "Quality Engineer" },
    { value: "Process Engineer", tr: "Proses Mühendisi", en: "Process Engineer" },
  ] },
  { id: "people-education", tr: "İnsan & Eğitim", en: "People & Education", roles: [
    { value: "Human Resources Specialist", tr: "İnsan Kaynakları Uzmanı", en: "Human Resources Specialist" },
    { value: "Recruiter", tr: "İşe Alım Uzmanı", en: "Recruiter" },
    { value: "Learning and Development Specialist", tr: "Öğrenme ve Gelişim Uzmanı", en: "Learning and Development Specialist" },
    { value: "Teacher", tr: "Öğretmen", en: "Teacher" },
    { value: "Instructional Designer", tr: "Eğitim Tasarımcısı", en: "Instructional Designer" },
    { value: "Researcher", tr: "Araştırmacı", en: "Researcher" },
  ] },
  { id: "design-service", tr: "Tasarım & Müşteri Deneyimi", en: "Design & Customer Experience", roles: [
    { value: "Product Designer", tr: "Ürün Tasarımcısı", en: "Product Designer" },
    { value: "Graphic Designer", tr: "Grafik Tasarımcı", en: "Graphic Designer" },
    { value: "UX Researcher", tr: "UX Araştırmacısı", en: "UX Researcher" },
    { value: "Customer Success Manager", tr: "Müşteri Başarı Yöneticisi", en: "Customer Success Manager" },
    { value: "Customer Support Specialist", tr: "Müşteri Destek Uzmanı", en: "Customer Support Specialist" },
    { value: "Technical Support Engineer", tr: "Teknik Destek Mühendisi", en: "Technical Support Engineer" },
  ] },
];

const EUROPE_COUNTRIES: LocalizedOption[] = [
  { value: "Albania", tr: "Arnavutluk", en: "Albania" }, { value: "Andorra", tr: "Andorra", en: "Andorra" },
  { value: "Armenia", tr: "Ermenistan", en: "Armenia" }, { value: "Austria", tr: "Avusturya", en: "Austria" },
  { value: "Azerbaijan", tr: "Azerbaycan", en: "Azerbaijan" }, { value: "Belarus", tr: "Belarus", en: "Belarus" },
  { value: "Belgium", tr: "Belçika", en: "Belgium" }, { value: "Bosnia and Herzegovina", tr: "Bosna-Hersek", en: "Bosnia and Herzegovina" },
  { value: "Bulgaria", tr: "Bulgaristan", en: "Bulgaria" }, { value: "Croatia", tr: "Hırvatistan", en: "Croatia" },
  { value: "Cyprus", tr: "Kıbrıs", en: "Cyprus" }, { value: "Czechia", tr: "Çekya", en: "Czechia" },
  { value: "Denmark", tr: "Danimarka", en: "Denmark" }, { value: "Estonia", tr: "Estonya", en: "Estonia" },
  { value: "Finland", tr: "Finlandiya", en: "Finland" }, { value: "France", tr: "Fransa", en: "France" },
  { value: "Georgia", tr: "Gürcistan", en: "Georgia" }, { value: "Germany", tr: "Almanya", en: "Germany" },
  { value: "Greece", tr: "Yunanistan", en: "Greece" }, { value: "Hungary", tr: "Macaristan", en: "Hungary" },
  { value: "Iceland", tr: "İzlanda", en: "Iceland" }, { value: "Ireland", tr: "İrlanda", en: "Ireland" },
  { value: "Italy", tr: "İtalya", en: "Italy" }, { value: "Kosovo", tr: "Kosova", en: "Kosovo" },
  { value: "Latvia", tr: "Letonya", en: "Latvia" }, { value: "Liechtenstein", tr: "Lihtenştayn", en: "Liechtenstein" },
  { value: "Lithuania", tr: "Litvanya", en: "Lithuania" }, { value: "Luxembourg", tr: "Lüksemburg", en: "Luxembourg" },
  { value: "Malta", tr: "Malta", en: "Malta" }, { value: "Moldova", tr: "Moldova", en: "Moldova" },
  { value: "Monaco", tr: "Monako", en: "Monaco" }, { value: "Montenegro", tr: "Karadağ", en: "Montenegro" },
  { value: "Netherlands", tr: "Hollanda", en: "Netherlands" }, { value: "North Macedonia", tr: "Kuzey Makedonya", en: "North Macedonia" },
  { value: "Norway", tr: "Norveç", en: "Norway" }, { value: "Poland", tr: "Polonya", en: "Poland" },
  { value: "Portugal", tr: "Portekiz", en: "Portugal" }, { value: "Romania", tr: "Romanya", en: "Romania" },
  { value: "Russia", tr: "Rusya", en: "Russia" }, { value: "San Marino", tr: "San Marino", en: "San Marino" },
  { value: "Serbia", tr: "Sırbistan", en: "Serbia" }, { value: "Slovakia", tr: "Slovakya", en: "Slovakia" },
  { value: "Slovenia", tr: "Slovenya", en: "Slovenia" }, { value: "Spain", tr: "İspanya", en: "Spain" },
  { value: "Sweden", tr: "İsveç", en: "Sweden" }, { value: "Switzerland", tr: "İsviçre", en: "Switzerland" },
  { value: "Turkey", tr: "Türkiye", en: "Türkiye" }, { value: "Ukraine", tr: "Ukrayna", en: "Ukraine" },
  { value: "United Kingdom", tr: "Birleşik Krallık", en: "United Kingdom" }, { value: "Vatican City", tr: "Vatikan", en: "Vatican City" },
];

const LOCATION_PRESETS: LocalizedOption[] = [
  { value: "United States", tr: "Amerika Birleşik Devletleri", en: "United States" },
  { value: "Worldwide Remote", tr: "Dünya geneli uzaktan", en: "Worldwide remote" },
  { value: "Turkey", tr: "Türkiye geneli", en: "Türkiye-wide" },
];

export default function OnboardingPage() {
  const { locale, translate: t } = useLanguage();
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [cvBusy, setCvBusy] = useState(false);
  const [cvMessage, setCvMessage] = useState("");
  const [cvSuggestions, setCvSuggestions] = useState<{ fields: CvProfileFields; text: string; ai_used: boolean; quality?: CvQualityReport; analysis?: CvAiAnalysis | null; optimized_cv_text?: string; ai_warning?: string | null } | null>(null);
  const [useAiCvExtraction, setUseAiCvExtraction] = useState(false);
  const [roleGroup, setRoleGroup] = useState("technology");
  const [roleSearch, setRoleSearch] = useState("");
  const [customRole, setCustomRole] = useState("");
  const [locationRegion, setLocationRegion] = useState<"europe" | "us" | "remote">("europe");
  const [locationSearch, setLocationSearch] = useState("");

  async function importCv(file?: File) {
    if (!file) return;
    setCvMessage("");
    try {
      if (!/\.(pdf|docx)$/i.test(file.name)) throw new Error(t("Lütfen PDF veya DOCX biçiminde bir CV seç."));
      setCvBusy(true);
      const uploadData = new FormData();
      uploadData.append("file", file);
      uploadData.append("use_ai", String(useAiCvExtraction));
      const response = await requestFromApi("/setup/parse_cv", { method: "POST", body: uploadData });
      const parsed = await response.json();
      if (!response.ok) throw new Error(parsed.detail || t("CV dosyası okunamadı."));
      setCvSuggestions({ fields: parsed.fields || {}, text: parsed.text || "", ai_used: Boolean(parsed.ai_used), quality: parsed.quality, analysis: parsed.analysis, optimized_cv_text: parsed.optimized_cv_text || "", ai_warning: parsed.ai_warning });
      setCvMessage(`${t("CV içeriği çıkarıldı")}: ${parsed.character_count || 0} ${t("karakter")}. ${t("Aşağıdaki alanları kontrol edip seç.")}`);
    } catch (error: any) {
      setCvMessage(error.message || t("CV dosyası okunamadı."));
    } finally {
      setCvBusy(false);
    }
  }

  function applyCvSuggestions(fields: CvProfileFields) {
    setFormData((current: any) => {
      const next = { ...current, raw_cv_text: cvSuggestions?.text || current.raw_cv_text };
      for (const [key, value] of Object.entries(fields)) {
        if (key === "confidence") continue;
        if (key === "skills" || key === "languages") next[key] = (value as string[]).join(", ");
        else if (key === "experience") next.experience = (value as NonNullable<CvProfileFields["experience"]>).map((item) => ({ ...item, bulletsText: Array.isArray(item.bullets) ? item.bullets.join("\n") : item.bullets || "" }));
        else if (key === "education") next.education = value;
        else next[key] = value;
      }
      return next;
    });
    setCvSuggestions(null);
    setCvMessage(t("Seçilen bilgiler forma aktarıldı. Kaydetmeden önce tekrar gözden geçir."));
  }

  // Form State
  const [formData, setFormData] = useState<any>({
    full_name: "",
    email: "",
    phone: "",
    target_role: "",
    years_of_experience: 0,
    location: "",
    skills: "",
    work_preference: "",
    languages: "",
    github_url: "",
    summary: "",
    raw_cv_text: "",
    experience: [],
    education: [],
    work_style: "",
    writing_tone: "",
  });

  useEffect(() => {
    fetchFromApi("/setup/profile").then((res) => {
      const profile = res.profile || {};
      setFormData((current) => ({
        ...current,
        full_name: profile.full_name || current.full_name,
        email: profile.email || current.email,
        phone: profile.phone || current.phone,
        target_role: profile.target_role || current.target_role,
        years_of_experience: profile.years_of_experience || current.years_of_experience,
        location: profile.location || current.location,
        skills: Array.isArray(profile.skills) ? profile.skills.join(", ") : current.skills,
        work_preference: profile.work_preference || current.work_preference,
        languages: Array.isArray(profile.languages) ? profile.languages.join(", ") : current.languages,
        github_url: profile.github_url || current.github_url,
        summary: profile.summary || current.summary,
        raw_cv_text: profile.raw_cv_text || current.raw_cv_text,
        experience: Array.isArray(profile.experience) ? profile.experience.map((item: any) => ({
          title: item.title || "", company: item.company || "", period: item.period || "",
          bulletsText: (item.bullets || item.achievements || []).join("\n"),
        })) : current.experience,
        education: Array.isArray(profile.education) ? profile.education.map((item: any) => ({
          degree: item.degree || "", school: item.school || "", year: item.year || "",
        })) : current.education,
        work_style: profile.work_style || current.work_style,
        writing_tone: profile.writing_tone || current.writing_tone,
      }));
      if (profile.location === "United States") setLocationRegion("us");
      else if (["Worldwide Remote", "Turkey"].includes(profile.location)) setLocationRegion("remote");
    }).catch(() => {});
  }, []);

  async function handleFinish() {
    try {
      setSaving(true);
      await fetchFromApi("/setup/update_profile", {
        method: "POST",
        body: JSON.stringify({
          ...formData,
          skills: formData.skills.split(",").map(s => s.trim()).filter(Boolean),
          languages: formData.languages.split(",").map((s: string) => s.trim()).filter(Boolean),
          experience: formData.experience.map(({ bulletsText, ...item }: any) => ({
            ...item,
            bullets: bulletsText.split(/\n+/).map((line: string) => line.trim()).filter(Boolean),
          })).filter((item: any) => item.title || item.company),
          education: formData.education.filter((item: any) => item.degree || item.school),
        })
      });
      // Next step of the start flow: source and API setup, then the first scan.
      router.push("/sources");
    } catch (e) {
      notify(t("Profil kaydedilemedi."));
    } finally {
      setSaving(false);
    }
  }

  const stepGaps: Record<number, string[]> = {
    1: [!formData.full_name.trim() && t("Ad soyad"), !formData.email.trim() && t("E-posta"), !formData.target_role && t("Hedef rol"), !formData.location && t("Konum veya çalışma tercihi")].filter(Boolean) as string[],
    2: [!formData.raw_cv_text.trim() && formData.experience.length === 0 && t("CV metni veya deneyim")].filter(Boolean) as string[],
    3: [!formData.skills.trim() && t("Beceriler")].filter(Boolean) as string[],
  };
  const currentGaps = stepGaps[step] || [];

  return (
    <div className="max-w-2xl mx-auto py-6 space-y-6">
      <SetupSteps />
      {/* Wizard Progress */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-mono text-blue-400 font-bold uppercase tracking-wider">
            {t("ADIM")} {step} {t("/ 5")}</div>
          <h1 className="text-xl font-bold text-white mt-1">
            {step === 1 && t("1. Hedef Pozisyon & Temel Bilgiler")}
            {step === 2 && t("2. CV, Deneyim & Eğitim")}
            {step === 3 && t("3. Teknik Yetenek Kümesi")}
            {step === 4 && t("4. Çalışma Tarzı & Kültürel Uyum")}
            {step === 5 && t("5. Niyet Mektubu & Başvuru Tonu")}
          </h1>
        </div>
        <div className="flex gap-1.5">
          {[1, 2, 3, 4, 5].map((s) => (
            <div
              key={s}
              className={`h-2 w-8 rounded-full transition-colors ${
                s <= step ? "bg-blue-500" : "bg-slate-800"
              }`}
            />
          ))}
        </div>
      </div>

      {/* Step Containers */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
        {step === 1 && (
          <div className="space-y-4">
            <div>
              <label className="text-xs text-slate-400 block mb-1">{t("Ad Soyad")}</label>
              <input
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-4 py-2.5 text-xs text-white"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">{t("E-Posta")}</label>
              <input
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-4 py-2.5 text-xs text-white"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">{t("Hedef Pozisyon / Rol Başlığı")}</label>
              <p className="mb-2 text-xs text-slate-400">{t("Sektör seç, ardından hedef rolünü seç. Listede yoksa özel rol girebilirsin.")}</p>
              <div className="mb-2 flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label={t("Sektör kategorileri")}>
                {ROLE_GROUPS.map((group) => <button key={group.id} type="button" role="tab" aria-selected={roleGroup === group.id} onClick={() => { setRoleGroup(group.id); setRoleSearch(""); }} className={`shrink-0 rounded-full border px-3 py-1.5 text-xs font-medium transition ${roleGroup === group.id ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300" : "border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200"}`}>{locale === "en" ? group.en : group.tr}</button>)}
              </div>
              <div className="relative mb-2"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input value={roleSearch} onChange={(e) => setRoleSearch(e.target.value)} placeholder={t("Rol ara…")} aria-label={t("Rol ara")} className="w-full rounded-xl border border-slate-700/80 bg-slate-950/80 py-2.5 pl-9 pr-3 text-xs text-white" /></div>
              <div className="grid max-h-48 grid-cols-1 gap-2 overflow-y-auto pr-1 sm:grid-cols-2" role="group" aria-label={t("Hedef rol seçenekleri")}>
                {(ROLE_GROUPS.find((group) => group.id === roleGroup)?.roles || []).filter((role) => `${role.tr} ${role.en}`.toLocaleLowerCase(locale === "tr" ? "tr-TR" : "en-US").includes(roleSearch.trim().toLocaleLowerCase(locale === "tr" ? "tr-TR" : "en-US"))).map((role) => {
                  const selected = formData.target_role === role.value;
                  return <button key={role.value} type="button" aria-pressed={selected} onClick={() => setFormData({ ...formData, target_role: role.value })} className={`flex min-h-10 items-center justify-between gap-2 rounded-xl border px-3 py-2 text-left text-xs transition ${selected ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200" : "border-slate-800 bg-slate-950/50 text-slate-300 hover:border-slate-600 hover:bg-slate-900"}`}><span>{locale === "en" ? role.en : role.tr}</span>{selected && <Check className="h-3.5 w-3.5 shrink-0 text-emerald-400" />}</button>;
                })}
              </div>
              {roleSearch && !(ROLE_GROUPS.find((group) => group.id === roleGroup)?.roles || []).some((role) => `${role.tr} ${role.en}`.toLocaleLowerCase(locale === "tr" ? "tr-TR" : "en-US").includes(roleSearch.trim().toLocaleLowerCase(locale === "tr" ? "tr-TR" : "en-US"))) && <p className="py-3 text-center text-xs text-slate-400">{t("Bu kategoride eşleşen rol yok.")}</p>}
              <div className="mt-2 flex gap-2"><input value={customRole} onChange={(e) => setCustomRole(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && customRole.trim()) { e.preventDefault(); setFormData({ ...formData, target_role: customRole.trim() }); setCustomRole(""); } }} placeholder={t("Listede yoksa özel rol yaz")} aria-label={t("Özel hedef rol")} className="min-w-0 flex-1 rounded-xl border border-slate-700/80 bg-slate-950/80 px-3 py-2 text-xs text-white" /><button type="button" disabled={!customRole.trim()} onClick={() => { setFormData({ ...formData, target_role: customRole.trim() }); setCustomRole(""); }} className="rounded-xl border border-slate-700 px-3 py-2 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-40">{t("Rolü kullan")}</button></div>
              {formData.target_role && <p className="mt-2 text-xs text-emerald-300">{t("Seçilen rol:")} {formData.target_role}</p>}
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="text-xs text-slate-400 block mb-1">{t("Deneyim (Yıl)")}</label>
                <input
                  type="number"
                  value={formData.years_of_experience}
                  onChange={(e) => setFormData({ ...formData, years_of_experience: Number(e.target.value) })}
                  className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-4 py-2.5 text-xs text-white"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">{t("Lokasyon / Tercih")}</label>
                <p className="mb-2 text-xs text-slate-400">{t("Arama için tek bir ülke veya özel şehir seç.")}</p>
                <div className="mb-2 grid grid-cols-3 gap-1 rounded-xl border border-slate-800 bg-slate-950/60 p-1" role="tablist" aria-label={t("Lokasyon kategorileri")}>
                  {[{ id: "europe", tr: "Avrupa", en: "Europe" }, { id: "us", tr: "ABD", en: "United States" }, { id: "remote", tr: "Uzaktan", en: "Remote" }].map((item) => <button key={item.id} type="button" role="tab" aria-selected={locationRegion === item.id} onClick={() => { setLocationRegion(item.id as "europe" | "us" | "remote"); setLocationSearch(""); }} className={`rounded-lg px-2 py-2 text-xs font-medium transition ${locationRegion === item.id ? "bg-slate-800 text-white" : "text-slate-400 hover:text-slate-200"}`}>{locale === "en" ? item.en : item.tr}</button>)}
                </div>
                {locationRegion === "europe" && <>
                  <div className="relative mb-2"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input value={locationSearch} onChange={(e) => setLocationSearch(e.target.value)} placeholder={t("Avrupa ülkelerinde ara…")} aria-label={t("Ülke ara")} className="w-full rounded-xl border border-slate-700/80 bg-slate-950/80 py-2.5 pl-9 pr-3 text-xs text-white" /></div>
                  <div className="grid max-h-36 grid-cols-2 gap-1.5 overflow-y-auto pr-1 sm:grid-cols-3" role="group" aria-label={t("Avrupa ülkeleri")}>
                    {EUROPE_COUNTRIES.filter((country) => `${country.tr} ${country.en}`.toLocaleLowerCase(locale === "tr" ? "tr-TR" : "en-US").includes(locationSearch.trim().toLocaleLowerCase(locale === "tr" ? "tr-TR" : "en-US"))).map((country) => <button key={country.value} type="button" aria-pressed={formData.location === country.value} onClick={() => setFormData({ ...formData, location: country.value })} className={`truncate rounded-lg border px-2.5 py-2 text-left text-xs transition ${formData.location === country.value ? "border-sky-500/40 bg-sky-500/10 text-sky-200" : "border-slate-800 bg-slate-950/40 text-slate-300 hover:border-slate-600"}`}>{locale === "en" ? country.en : country.tr}</button>)}
                  </div>
                </>}
                {locationRegion === "us" && <button type="button" aria-pressed={formData.location === "United States"} onClick={() => setFormData({ ...formData, location: "United States" })} className={`flex w-full items-center justify-between rounded-xl border px-3 py-3 text-left text-xs transition ${formData.location === "United States" ? "border-sky-500/40 bg-sky-500/10 text-sky-200" : "border-slate-800 bg-slate-950/40 text-slate-300 hover:border-slate-600"}`}>{locale === "en" ? "United States" : "Amerika Birleşik Devletleri"}{formData.location === "United States" && <Check className="h-4 w-4 text-sky-400" />}</button>}
                {locationRegion === "remote" && <div className="grid grid-cols-1 gap-1.5">{LOCATION_PRESETS.filter((item) => item.value !== "United States").map((item) => <button key={item.value} type="button" aria-pressed={formData.location === item.value} onClick={() => setFormData({ ...formData, location: item.value })} className={`flex items-center justify-between rounded-xl border px-3 py-2.5 text-left text-xs transition ${formData.location === item.value ? "border-sky-500/40 bg-sky-500/10 text-sky-200" : "border-slate-800 bg-slate-950/40 text-slate-300 hover:border-slate-600"}`}>{locale === "en" ? item.en : item.tr}{formData.location === item.value && <Check className="h-4 w-4 text-sky-400" />}</button>)}</div>}
                <div className="relative mt-2"><MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input value={formData.location} onChange={(e) => setFormData({ ...formData, location: e.target.value })} placeholder={t("Veya şehir / özel lokasyon yaz")} aria-label={t("Özel lokasyon")} className="w-full rounded-xl border border-slate-700/80 bg-slate-950/80 py-2.5 pl-9 pr-3 text-xs text-white" /></div>
                {formData.location && <p className="mt-1 text-xs text-sky-300">{t("Seçilen lokasyon:")} {formData.location}</p>}
              </div>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4 max-h-[65vh] overflow-y-auto pr-1">
            <div>
              <label className="text-xs text-slate-400 block mb-1">{t("Telefon")}</label>
              <input value={formData.phone} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-4 py-2.5 text-xs text-white" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">{t("Çalışma Tercihi")}</label>
                <input value={formData.work_preference} onChange={(e) => setFormData({ ...formData, work_preference: e.target.value })} placeholder={t("Uzaktan, hibrit, ofis...")} className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-4 py-2.5 text-xs text-white" />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">{t("Diller (virgülle ayırın)")}</label>
                <input value={formData.languages} onChange={(e) => setFormData({ ...formData, languages: e.target.value })} placeholder={t("Türkçe, English...")} className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-4 py-2.5 text-xs text-white" />
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">{t("GitHub / Portfolyo URL")}</label>
              <input value={formData.github_url} onChange={(e) => setFormData({ ...formData, github_url: e.target.value })} className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-4 py-2.5 text-xs text-white" />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">{t("Profesyonel Özet")}</label>
              <textarea rows={3} value={formData.summary} onChange={(e) => setFormData({ ...formData, summary: e.target.value })} className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl p-3 text-xs text-white" />
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs text-slate-400">{t("Ham CV Metni")}</label>
                <label className="text-xs text-blue-300 cursor-pointer">
                  {cvBusy ? t("CV okunuyor…") : t("PDF / DOCX yükle")}
                  <input
                    type="file"
                    accept=".pdf,.docx"
                    className="hidden"
                    disabled={cvBusy}
                    onChange={async (event) => {
                      const input = event.currentTarget;
                      await importCv(input.files?.[0]);
                      input.value = "";
                    }}
                  />
                </label>
              </div>
              <label className="mb-2 flex items-start gap-2 text-xs leading-relaxed text-slate-400">
                <input type="checkbox" checked={useAiCvExtraction} onChange={(event) => setUseAiCvExtraction(event.target.checked)} className="mt-0.5" />
                <span>{t("AI ile çıkarım seçilirse CV metni Ayarlar'da seçili AI sağlayıcısında işlenir; bulut sağlayıcısıysa metin cihazından çıkar. Kapalıysa yalnızca yerel çıkarım kullanılır.")}</span>
              </label>
              {cvMessage && <p role="status" className="mb-2 text-xs text-slate-400">{cvMessage}</p>}
              {cvSuggestions && <div className="mb-3"><CvImportReview fields={cvSuggestions.fields} originalText={cvSuggestions.text} quality={cvSuggestions.quality} analysis={cvSuggestions.analysis} optimizedCvText={cvSuggestions.optimized_cv_text} aiWarning={cvSuggestions.ai_warning} aiUsed={cvSuggestions.ai_used} onApply={applyCvSuggestions} onCancel={() => setCvSuggestions(null)} /></div>}
              <textarea rows={5} value={formData.raw_cv_text} onChange={(e) => setFormData({ ...formData, raw_cv_text: e.target.value })} className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl p-3 text-xs text-white" />
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs text-slate-400">{t("İş Deneyimi")}</label>
                <button type="button" onClick={() => setFormData({ ...formData, experience: [...formData.experience, { title: "", company: "", period: "", bulletsText: "" }] })} className="text-xs text-blue-300">{t("+ Deneyim ekle")}</button>
              </div>
              {formData.experience.map((item: any, index: number) => (
                <div key={index} className="p-3 mb-2 rounded-xl border border-slate-800 space-y-2">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    {(["title", "company", "period"] as const).map((key) => <input key={key} placeholder={{ title: "Pozisyon", company: "Şirket", period: "Dönem" }[key]} value={item[key]} onChange={(e) => setFormData({ ...formData, experience: formData.experience.map((row: any, i: number) => i === index ? { ...row, [key]: e.target.value } : row) })} className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white" />)}
                  </div>
                  <textarea rows={2} placeholder={t("Başarılar (her satıra bir madde)")} value={item.bulletsText} onChange={(e) => setFormData({ ...formData, experience: formData.experience.map((row: any, i: number) => i === index ? { ...row, bulletsText: e.target.value } : row) })} className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-xs text-white" />
                  <button type="button" onClick={() => setFormData({ ...formData, experience: formData.experience.filter((_: any, i: number) => i !== index) })} className="text-xs text-rose-300">{t("Deneyimi kaldır")}</button>
                </div>
              ))}
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs text-slate-400">{t("Eğitim")}</label>
                <button type="button" onClick={() => setFormData({ ...formData, education: [...formData.education, { degree: "", school: "", year: "" }] })} className="text-xs text-blue-300">{t("+ Eğitim ekle")}</button>
              </div>
              {formData.education.map((item: any, index: number) => (
                <div key={index} className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-2">
                  {(["degree", "school", "year"] as const).map((key) => <input key={key} placeholder={{ degree: "Derece / Program", school: "Kurum", year: "Yıl" }[key]} value={item[key]} onChange={(e) => setFormData({ ...formData, education: formData.education.map((row: any, i: number) => i === index ? { ...row, [key]: e.target.value } : row) })} className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white" />)}
                </div>
              ))}
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <div>
              <label className="text-xs text-slate-400 block mb-1">
                {t("Teknik Beceriler & Frameworkler (Virgülle Ayırın)")}
              </label>
              <textarea
                rows={4}
                value={formData.skills}
                onChange={(e) => setFormData({ ...formData, skills: e.target.value })}
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl p-3 text-xs text-white leading-relaxed"
              />
            </div>
            <div className="text-xs text-slate-400">
              {t("Bu beceriler ilanlarla uyum tahmininde ve CV taslaklarında kanıt olarak kullanılır; yalnızca gerçekten sahip olduklarını yaz.")}</div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-3">
            <div className="text-xs text-slate-400 mb-2">{t("En rahat çalıştığınız model hangisidir?")}</div>
            {[
              { id: "autonomous", title: "Bağımsız & İnisiyatif Alan", desc: "Minimal denetim, yüksek otonomi ve sonuç odaklılık." },
              { id: "collaborative", title: "İş Birliği & Çapraz Takım", desc: "Sürekli iletişim, beyin fırtınası ve takım uyumu." },
              { id: "methodical", title: "Metodik & Süreç Odaklı", desc: "Ayrıntılı planlama, dokümantasyon ve net yönergeler." }
            ].map((opt) => (
              <button
                key={opt.id}
                onClick={() => setFormData({ ...formData, work_style: opt.id })}
                className={`w-full text-left p-3.5 rounded-xl border transition-all ${
                  formData.work_style === opt.id
                    ? "bg-blue-600/20 border-blue-500/50 text-blue-200"
                    : "bg-slate-950/60 border-slate-800 text-slate-400 hover:text-white"
                }`}
              >
                <div className="text-xs font-bold text-white">{t(opt.title)}</div>
                <div className="text-xs text-slate-400 mt-0.5">{t(opt.desc)}</div>
              </button>
            ))}
          </div>
        )}

        {step === 5 && (
          <div className="space-y-3">
            <div className="text-xs text-slate-400 mb-2">{t("Başvurularda kullanılacak varsayılan yazım dili tonu:")}</div>
            {[
              { id: "professional_conversational", title: "Profesyonel & Doğal", desc: "Sıcak, akıcı ve insan yazımı hissi veren dengeli dil." },
              { id: "technical", title: "Teknik & Metrik Odaklı", desc: "Doğrudan mühendislik çıktılarına ve somut sayılara odaklanan net üslup." },
              { id: "formal", title: "Kurumsal & Resmi", desc: "Geleneksel kurumsal firmalar ve resmi başvurular için uygun ton." }
            ].map((tone) => (
              <button
                key={tone.id}
                onClick={() => setFormData({ ...formData, writing_tone: tone.id })}
                className={`w-full text-left p-3.5 rounded-xl border transition-all ${
                  formData.writing_tone === tone.id
                    ? "bg-indigo-600/20 border-indigo-500/50 text-indigo-200"
                    : "bg-slate-950/60 border-slate-800 text-slate-400 hover:text-white"
                }`}
              >
                <div className="text-xs font-bold text-white">{t(tone.title)}</div>
                <div className="text-xs text-slate-400 mt-0.5">{t(tone.desc)}</div>
              </button>
            ))}
          </div>
        )}

        <p role="status" className={`text-xs ${currentGaps.length ? "text-amber-300" : "text-emerald-300"}`}>{currentGaps.length ? `${t("Bu adımda eksik:")} ${currentGaps.join(" · ")}` : step <= 3 ? t("Bu adımda eksik yok.") : t("Bu adım isteğe bağlı.")}</p>

        {/* Buttons */}
        <div className="flex justify-between pt-4 border-t border-slate-800">
          {step > 1 ? (
            <button
              onClick={() => setStep(step - 1)}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300 rounded-xl transition-colors"
            >
              {t("Geri")}
            </button>
          ) : <div />}

          {step < 5 ? (
            <button
              onClick={() => setStep(step + 1)}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white rounded-xl flex items-center gap-1.5 transition-colors"
            >
              {t("İlerle")} <ArrowRight className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              onClick={handleFinish}
              disabled={saving}
              className="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white rounded-xl flex items-center gap-1.5 transition-colors disabled:opacity-50 shadow-lg shadow-emerald-600/20"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              {saving ? t("Kaydediliyor...") : t("Kaydet ve kaynak kurulumuna geç")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
