"use client";

import { useState } from "react";
import { Search, Users } from "lucide-react";
import { fetchFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

type Person = { first_name: string; last_name_obfuscated: string; title: string; company: string; has_email: boolean };

export default function ApolloPeopleSearch({ location }: { location: string }) {
  const { translate: t } = useLanguage();
  const [domain, setDomain] = useState("");
  const [people, setPeople] = useState<Person[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function search() {
    setBusy(true);
    setError("");
    try {
      const result = await fetchFromApi<{ people: Person[] }>("/decision-makers/search", {
        method: "POST",
        body: JSON.stringify({ company_domain: domain.trim(), location: location.trim() || null }),
      });
      setPeople(result.people || []);
    } catch (cause: unknown) {
      setPeople(null);
      setError(cause instanceof Error && cause.message ? cause.message : t("Apollo araması başarısız oldu."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="apollo-search-title" className="space-y-4 rounded-2xl border border-slate-800/80 bg-[#0e1524] p-6">
      <div>
        <h2 id="apollo-search-title" className="flex items-center gap-2 text-sm font-semibold text-white">
          <Users className="h-4 w-4 text-blue-400" /> {t("Apollo ile karar vericileri ara")}
        </h2>
        <p className="mt-1 text-xs text-slate-400">
          {t("Şirketin alan adına göre yönetici ve üstü kişileri listeler. Arama Apollo kredisi harcamaz; e-posta ve tam soyadı Apollo tarafından bu aramada verilmez.")}
        </p>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="apolloDomain" className="sr-only">{t("Şirket alan adı")}</label>
        <input
          id="apolloDomain"
          value={domain}
          onChange={(event) => setDomain(event.target.value)}
          placeholder="acme.com"
          className="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
        />
        <button
          type="button"
          onClick={search}
          disabled={busy || !domain.trim()}
          className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-blue-500 disabled:opacity-50"
        >
          <Search className="h-3.5 w-3.5" /> {busy ? t("Aranıyor…") : t("Karar vericileri ara")}
        </button>
      </div>
      {error && <div role="alert" className="rounded-xl border border-amber-500/25 bg-amber-500/10 px-4 py-3 text-xs text-amber-200">{error}</div>}
      {people && people.length === 0 && <div className="text-xs text-slate-400">{t("Bu alan adı için Apollo'da yönetici kaydı bulunamadı.")}</div>}
      {people && people.length > 0 && (
        <ul className="space-y-2">
          {people.map((person, index) => (
            <li key={`${person.first_name}-${person.title}-${index}`} className="rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
              <div className="text-xs font-semibold text-white">{[person.first_name, person.last_name_obfuscated].filter(Boolean).join(" ")}</div>
              <div className="mt-0.5 text-xs text-slate-400">{[person.title, person.company].filter(Boolean).join(" — ")}</div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
