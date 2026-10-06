"use client";
import { useLanguage } from "@/lib/i18n";

import { useState } from "react";
import {
  Users,
  Search,
  ExternalLink,
  Copy,
  Check,
  Send,
  Sparkles,
  Compass
} from "lucide-react";
import { fetchFromApi } from "@/lib/api";
import ApolloPeopleSearch from "@/components/ApolloPeopleSearch";

export default function DecisionMakersPage() {
  const { translate: t } = useLanguage();
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");
  const [role, setRole] = useState("");
  const [dork, setDork] = useState("");
  const [coldDm, setColdDm] = useState("");
  const [copied, setCopied] = useState(false);
  const [contactName, setContactName] = useState("");
  const [emailGuess, setEmailGuess] = useState("");
  // True while the address is the app's own pattern guess; typing a real one clears it.
  const [emailIsGuess, setEmailIsGuess] = useState(false);
  const [emailLookupMessage, setEmailLookupMessage] = useState("");
  const [outreachMessage, setOutreachMessage] = useState("");
  const [emailBusy, setEmailBusy] = useState(false);

  function handleGenerate() {
    const cleanCompany = company.replace(/"/g, '').trim();
    const cleanLoc = location.split('/')[0].split(',')[0].trim();
    if (!cleanCompany || !cleanLoc || !role.trim()) return;
    const generatedDork = `site:linkedin.com/in/ "${cleanLoc}" AND "${cleanCompany}" AND ("Manager" OR "Director" OR "Lead" OR "Head")`;
    setDork(generatedDork);

    const s1 = `I'm interested in learning more about ${role} opportunities at ${company}.`;
    const s2 = `I would be glad to share relevant examples from my work and learn more about the team's needs.`;
    const s3 = `Would you be open to a brief conversation about the role?`;
    setColdDm(`${s1} ${s2} ${s3}`);
  }

  function handleCopy() {
    navigator.clipboard.writeText(coldDm);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const googleSearchUrl = `https://www.google.com/search?q=${encodeURIComponent(dork)}`;

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Users className="w-6 h-6 text-blue-500" />
          {t("Karar vericiler")}</h1>
        <p className="text-xs text-slate-400 mt-1">
          {t("Google arama sorgusu ve gözden geçirilebilir iletişim taslağı oluşturur. Kişi ya da e-posta adresinin bulunduğunu veya doğrulandığını iddia etmez.")}</p>
      </div>

      {/* Generator Controls */}
      <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
        <h2 className="text-sm font-semibold text-white flex items-center gap-2">
          <Compass className="w-4 h-4 text-blue-400" /> {t("X-Ray Dork & Cold DM Parametreleri")}</h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="text-xs font-semibold text-slate-400 uppercase">{t("Şirket Adı")}</label>
            <input
              type="text"
              value={company}
              onChange={(e) => { setCompany(e.target.value); setEmailGuess(""); setEmailLookupMessage(""); }}
              className="w-full mt-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-400 uppercase">{t("Hedef Bölge / Şehir")}</label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="w-full mt-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-400 uppercase">{t("Hedef Rol")}</label>
            <input
              type="text"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full mt-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white"
            />
          </div>
        </div>

        <button
          onClick={handleGenerate}
          className="bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs px-5 py-2.5 rounded-xl transition flex items-center gap-2 shadow-lg shadow-blue-600/20"
        >
          <Sparkles className="w-3.5 h-3.5" /> {t("Dork & 3 Cümlelik Cold DM Üret")}</button>
      </div>

      {/* Output Results */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* X-Ray Dork Box */}
        <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-xs font-bold text-white">{t("Google X-Ray Dorking Sorgusu")}</span>
              <span className="text-xs bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded font-mono">
                {t("PRD 3.3 Standardı")}</span>
            </div>
            <p className="text-xs text-slate-400">
              {t("Bu dork sorgusunu Google'a girerek ilgili şirketin bölge müdürünü veya teknik liderini LinkedIn'e girmeden doğrudan bulabilirsiniz:")}</p>
            <pre className="p-3.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-blue-300 font-mono whitespace-pre-wrap break-all">
              {dork}
            </pre>
          </div>

          <a
            href={googleSearchUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="w-full bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs py-2.5 rounded-xl transition flex items-center justify-center gap-2 border border-slate-700"
          >
            <Search className="w-3.5 h-3.5" /> {t("Google'da X-Ray Sorgusunu Aç")}<ExternalLink className="w-3 h-3 text-slate-400" />
          </a>
        </div>

        {/* 3-Sentence Cold DM Box */}
        <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-xs font-bold text-white">{t("3 Cümlelik Kişiselleştirilmiş Cold DM")}</span>
              <span className="text-xs bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded font-mono">
                {t("Taslak · Göndermeden önce gözden geçir")}</span>
            </div>
            <p className="text-xs text-slate-400">
              {t("Cümle 1: Bölgesel gözlem • Cümle 2: Doğrudan değer teklifi • Cümle 3: Düşük sürtünmeli çağrı (CTA).")}</p>
            <div className="p-3.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 leading-relaxed">
              {coldDm}
            </div>
          </div>

          <button
            onClick={handleCopy}
            className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs py-2.5 rounded-xl transition flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/20"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-white" /> {t("Panoya Kopyalandı!")}</>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" /> {t("Mesajı Panoya Kopyala")}</>
            )}
          </button>
        </div>
      </div>

      <ApolloPeopleSearch location={location} />

      {/* Unverified contact pattern suggestions and user-triggered SMTP dispatch */}
      <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-400" /> {t("E-posta deseni tahmini & SMTP gönderimi")}</h2>
            <p className="text-xs text-slate-400">
              {t("Olası adresler yalnızca ad ve şirket adına göre üretilir; gerçeklikleri veya teslim edilebilirlikleri doğrulanmaz. E-posta yalnızca sen gönder düğmesine bastığında denenir.")}</p>
          </div>
          <span className="text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2.5 py-0.5 rounded-full font-mono">
            {t("E-posta doğrulanmadı")}</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-slate-400 uppercase">{t("Yönetici / Karar Verici Ad Soyad")}</label>
              <input
                type="text"
                id="dmFullName"
                value={contactName}
                onChange={(event) => setContactName(event.target.value)}
                className="w-full mt-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white"
              />
            </div>
            <button
              disabled={emailBusy || !contactName.trim() || !company.trim()}
              onClick={async () => {
                setEmailBusy(true);
                setEmailLookupMessage("");
                setOutreachMessage("");
                try {
                  const res = await fetchFromApi("/decision-makers/find_email", {
                    method: "POST",
                    body: JSON.stringify({ full_name: contactName, company_name: company })
                  });
                  setEmailGuess(res.primary_email || "");
                  setEmailIsGuess(res.verification_status === "UNVERIFIED_PATTERN");
                  setEmailLookupMessage(res.verification_status === "UNVERIFIED_PATTERN"
                    ? t("Bu yalnızca bir adres tahminidir; Apollo/Hunter veya posta sunucusu tarafından doğrulanmadı.")
                    : t("Ad ve şirket adı yetersiz; e-posta tahmini oluşturulmadı."));
                } catch (error: any) {
                  setEmailLookupMessage(error.message || t("E-posta tahmini oluşturulamadı."));
                } finally { setEmailBusy(false); }
              }}
              className="bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs px-4 py-2 rounded-xl transition flex items-center gap-1.5"
            >
              <Search className="w-3.5 h-3.5" /> {emailBusy ? t("Tahmin hazırlanıyor…") : t("Doğrulanmamış adres tahmini oluştur")}</button>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2 text-xs flex flex-col justify-between">
            <div>
              <label htmlFor="targetEmailResult" className="text-xs font-semibold text-slate-400 uppercase">{t("E-posta adresi (kendin doğrula)")}</label>
              <input id="targetEmailResult" type="email" value={emailGuess} onChange={(event) => { setEmailGuess(event.target.value); setEmailIsGuess(false); }} placeholder={t("İsteğe bağlı: tahmini kontrol edip düzenle")} className="w-full mt-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white" />
              {emailLookupMessage && <p role="status" className="mt-2 text-xs text-amber-300">{emailLookupMessage}</p>}
            </div>

            <button
              disabled={emailBusy || !emailGuess.trim() || !coldDm.trim()}
              onClick={async () => {
                if (emailIsGuess && !window.confirm(t("Bu adres bir tahmin ve başka birine ait olabilir. Yine de gönderilsin mi?"))) return;
                setEmailBusy(true);
                setOutreachMessage("");
                try {
                  const res = await fetchFromApi("/decision-makers/send_email", {
                    method: "POST",
                    body: JSON.stringify({
                      to_email: emailGuess,
                      subject: `Quick note regarding ${role} @ ${company}`,
                      body_text: coldDm,
                      address_is_guess: emailIsGuess,
                      guess_confirmed: emailIsGuess
                    })
                  });
                  setOutreachMessage(res.message || t("E-posta gönderim durumu: {status}", { status: res.status || "UNKNOWN" }));
                } catch (error: any) {
                  setOutreachMessage(error.message || t("E-posta gönderilemedi."));
                } finally { setEmailBusy(false); }
              }}
              className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs py-2 rounded-xl transition flex items-center justify-center gap-1.5 shadow-md shadow-blue-600/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" /> {emailBusy ? t("Gönderiliyor…") : t("E-postayı şimdi gönder")}</button>
            <button
              type="button"
              disabled={emailBusy || !emailGuess.trim()}
              onClick={async () => {
                try {
                  await fetchFromApi("/decision-makers/suppressions", { method: "POST", body: JSON.stringify({ email: emailGuess }) });
                  setOutreachMessage(t("Bu adrese bir daha e-posta gönderilmeyecek."));
                } catch (error: any) {
                  setOutreachMessage(error.message || t("Adres engellenemedi."));
                }
              }}
              className="w-full rounded-xl border border-slate-700 py-2 text-xs font-semibold text-slate-300 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {t("Bu kişi istemiyor: bir daha yazma")}</button>
            {outreachMessage && <p role="status" className="text-xs text-slate-300">{outreachMessage}</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
