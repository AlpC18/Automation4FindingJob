"use client";
import { useLanguage } from "@/lib/i18n";
import { useEffect, useState } from "react";
import { DollarSign, Plus, Search, Upload, CheckCircle2 } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function SalaryIntelPage() {
  const { translate: t } = useLanguage();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [showAdd, setShowAdd] = useState(false);
  const emptyForm = { company: "", city: "", salary_min: "", salary_median: "", salary_max: "", currency: "USD", notes: "", source_type: "user_reported", source_name: "", source_url: "", as_of: "", sample_size: "", source_count: "" };
  const [form, setForm] = useState(emptyForm);
  const [searching, setSearching] = useState(false);
  const [salaryFeedback, setSalaryFeedback] = useState<Record<string, string[]>>({});
  const [feedbackNote, setFeedbackNote] = useState("");
  const [feedbackBusy, setFeedbackBusy] = useState<string | null>(null);
  const [feedbackNotice, setFeedbackNotice] = useState("");

  useEffect(() => {
    fetchFromApi("/rank/salary/stats").then(setStats).catch(() => {});
  }, []);

  async function handleSearch() {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const res = await fetchFromApi("/rank/salary/search", {
        method: "POST",
        body: JSON.stringify({ query }),
      });
      setResults(res.results || []);
      const reports = await Promise.all((res.results || []).map(async (item: any) => {
        const params = new URLSearchParams({ company: item.company });
        const own = await fetchFromApi(`/trust/feedback?${params}`).catch(() => ({ feedback_types: [] }));
        return [item.company, own.feedback_types || []] as const;
      }));
      setSalaryFeedback(Object.fromEntries(reports));
    } finally { setSearching(false); }
  }

  async function handleAdd() {
    await fetchFromApi("/rank/salary/add", {
      method: "POST",
      body: JSON.stringify({
        ...form,
        salary_min: form.salary_min ? parseFloat(form.salary_min) : null,
        salary_median: form.salary_median ? parseFloat(form.salary_median) : null,
        salary_max: form.salary_max ? parseFloat(form.salary_max) : null,
        sample_size: form.sample_size ? parseInt(form.sample_size, 10) : null,
        source_count: form.source_count ? parseInt(form.source_count, 10) : null,
      }),
    });
    setShowAdd(false);
    setForm(emptyForm);
    fetchFromApi("/rank/salary/stats").then(setStats);
    if (query.trim()) await handleSearch();
  }

  async function toggleSalaryFeedback(company: string, feedbackType: string) {
    const existing = salaryFeedback[company] || [];
    const remove = existing.includes(feedbackType);
    setFeedbackBusy(`${company}:${feedbackType}`);
    setFeedbackNotice("");
    try {
      const params = new URLSearchParams({ company });
      if (remove) {
        await fetchFromApi(`/trust/feedback/${feedbackType}?${params}`, { method: "DELETE" });
      } else {
        await fetchFromApi("/trust/feedback", { method: "POST", body: JSON.stringify({ company, feedback_type: feedbackType, note: feedbackNote }) });
      }
      const result = await fetchFromApi(`/trust/feedback?${params}`);
      setSalaryFeedback((current) => ({ ...current, [company]: result.feedback_types || [] }));
      setFeedbackNotice(t("Geri bildirimin yalnızca bu hesabında saklanır."));
      setFeedbackNote("");
    } catch {
      setFeedbackNotice(t("Geri bildirim kaydedilemedi. Tekrar deneyin."));
    } finally {
      setFeedbackBusy(null);
    }
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <DollarSign className="w-7 h-7 text-yellow-400" /> {t("Maaş İstihbaratı")}</h1>
          <p className="text-slate-400 mt-1">{t("Şirketlere göre maaş bilgisi: ara, ekle, karşılaştır")}</p>
        </div>
        <button onClick={() => setShowAdd(!showAdd)}
          className="px-4 py-2 bg-yellow-600/20 text-yellow-300 border border-yellow-500/30 rounded-lg text-sm hover:bg-yellow-600/30 transition-colors flex items-center gap-2">
          <Plus className="w-4 h-4" /> {t("Şirket Ekle")}</button>
      </div>

      {stats && (
        <div className="flex gap-4 text-center">
          <div className="bg-slate-800/60 border border-slate-700/40 rounded-xl px-6 py-3">
            <div className="text-xl font-bold text-white">{stats.total_companies}</div>
            <div className="text-xs text-slate-400">{t("Şirket")}</div>
          </div>
          <div className="bg-slate-800/60 border border-slate-700/40 rounded-xl px-6 py-3">
            <div className="text-xl font-bold text-white">{stats.unique_cities}</div>
            <div className="text-xs text-slate-400">{t("Şehir")}</div>
          </div>
          <div className="bg-slate-800/60 border border-slate-700/40 rounded-xl px-6 py-3">
            <div className="text-xl font-bold text-white">{stats.currencies?.join(", ") || "—"}</div>
            <div className="text-xs text-slate-400">{t("Para Birimi")}</div>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder={t("Şirket adı ara (fuzzy match)...")}
            className="w-full bg-slate-800/60 border border-slate-700/40 rounded-lg pl-10 pr-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-yellow-500/40" />
        </div>
        <button onClick={handleSearch} disabled={searching}
          className="px-5 py-3 bg-yellow-600 hover:bg-yellow-500 text-white font-medium rounded-xl text-sm disabled:opacity-50">
          {searching ? t("Arıyor...") : "Ara"}
        </button>
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-3">
          {results.map((r: any, i: number) => (
            <div key={i} className="bg-slate-800/50 border border-slate-700/40 rounded-xl p-5">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <div className="text-sm font-semibold text-white">{r.company}</div>
                  {r.city && <div className="text-xs text-slate-400">{r.city}</div>}
                </div>
                <div className="text-right">
                  {r.salary_min && r.salary_max && (
                    <div className="text-sm font-mono text-yellow-400">
                      {r.currency} {r.salary_min?.toLocaleString()} – {r.salary_max?.toLocaleString()} / {r.period}
                    </div>
                  )}
              {r.salary_median && (
                    <div className="text-xs text-slate-400">{t("Medyan:")}{r.currency} {r.salary_median?.toLocaleString()}</div>
                  )}
                </div>
              </div>
              <div className="mt-3 rounded-lg border border-slate-700/60 bg-slate-950/50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${r.evidence?.level === "well_documented" ? "bg-emerald-500/10 text-emerald-300" : r.evidence?.level === "partially_documented" ? "bg-amber-500/10 text-amber-200" : "bg-slate-700/60 text-slate-300"}`}>
                    {t(r.evidence?.level === "well_documented" ? "Kanıt bilgisi ayrıntılı" : r.evidence?.level === "partially_documented" ? "Kanıt bilgisi kısmi" : "Kanıt bilgisi sınırlı")} · {r.evidence?.score ?? 0}/100
                  </span>
                  <span className="text-xs text-slate-400">{t("Bağımsız olarak doğrulanmamıştır")}</span>
                </div>
                <div className="mt-2 grid gap-1 text-xs text-slate-400 sm:grid-cols-2">
                  <span>{t("Veri türü")}: {t(({ user_reported: "Kullanıcı bildirimi", company_disclosed: "Şirket açıklaması", survey: "Anket", job_posting: "İş ilanı", other: "Diğer" } as Record<string, string>)[r.source_type] || "Diğer")}</span>
                  <span>{t("Kaynak")}: {r.source_name || t("Belirtilmemiş")}</span>
                  <span>{t("Kaynak tarihi")}: {r.as_of || t("Bilinmiyor")}</span>
                  <span>{t("Örneklem")}: {r.sample_size ?? t("Bilinmiyor")}</span>
                  <span>{t("Kaynak sayısı")}: {r.source_count ?? t("Bilinmiyor")}</span>
                </div>
                {r.source_url && /^https?:\/\//i.test(r.source_url) && <a href={r.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs text-blue-300 underline">{t("Kaynağı aç")}</a>}
                <p className="mt-2 text-xs leading-4 text-slate-400">{t("Bu puan yalnızca kaynak bilgisinin tamlığını gösterir; maaşın doğruluğunu veya şirket güvenilirliğini kanıtlamaz.")}</p>
              </div>
              <input value={feedbackNote} onChange={(event) => setFeedbackNote(event.target.value)} maxLength={2000} placeholder={t("Geri bildirim için isteğe bağlı not")} className="mt-3 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white placeholder-slate-500" />
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {[["salary_mismatch", "Maaş bilgisi hatalı"], ["salary_consistent", "Maaş bilgisi tutarlı"], ["salary_outdated", "Güncelliğini yitirmiş"], ["source_unavailable", "Kaynak açılamıyor"]].map(([type, label]) => {
                  const selected = (salaryFeedback[r.company] || []).includes(type);
                  const key = `${r.company}:${type}`;
                  return <button key={type} type="button" disabled={feedbackBusy !== null} onClick={() => void toggleSalaryFeedback(r.company, type)} className={`rounded-md border px-2.5 py-1.5 text-xs disabled:opacity-50 ${selected ? "border-emerald-500/30 text-emerald-300" : "border-slate-700 text-slate-400 hover:text-white"}`}>
                    {feedbackBusy === key ? t("Kaydediliyor…") : selected ? `${t(label)} · ${t("Geri al")}` : t(label)}
                  </button>;
                })}
              </div>
              {feedbackNotice && <p role="status" className="mt-2 text-xs text-slate-400">{feedbackNotice}</p>}
              {r.notes && <div className="text-xs text-slate-400 mt-1">{r.notes}</div>}
            </div>
          ))}
        </div>
      )}

      {results.length === 0 && query && !searching && (
        <div className="text-center py-10 text-slate-400">{t("Sonuç bulunamadı. Yeni şirket ekleyebilirsiniz.")}</div>
      )}

      {/* Add Form */}
      {showAdd && (
        <div className="bg-slate-800/60 border border-yellow-500/20 rounded-2xl p-6 space-y-4">
          <h3 className="text-md font-semibold text-white">{t("Yeni Şirket Maaş Verisi")}</h3>
          <div className="grid grid-cols-2 gap-3">
            <input value={form.company} onChange={(e) => setForm({...form, company: e.target.value})} placeholder={t("Şirket Adı *")}
              className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" />
            <input value={form.city} onChange={(e) => setForm({...form, city: e.target.value})} placeholder={t("Şehir")}
              className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" />
            <input value={form.salary_min} onChange={(e) => setForm({...form, salary_min: e.target.value})} placeholder={t("Min Maaş")} type="number"
              className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" />
            <input value={form.salary_median} onChange={(e) => setForm({...form, salary_median: e.target.value})} placeholder={t("Medyan Maaş")} type="number"
              className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" />
            <input value={form.salary_max} onChange={(e) => setForm({...form, salary_max: e.target.value})} placeholder={t("Max Maaş")} type="number"
              className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" />
            <input value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} placeholder={t("Not")}
              className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" />
            <select value={form.source_type} onChange={(e) => setForm({...form, source_type: e.target.value})} className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2 text-sm text-white">
              <option value="user_reported">{t("Kullanıcı bildirimi")}</option><option value="company_disclosed">{t("Şirket açıklaması")}</option><option value="survey">{t("Anket")}</option><option value="job_posting">{t("İş ilanı")}</option><option value="other">{t("Diğer")}</option>
            </select>
            <input value={form.source_name} onChange={(e) => setForm({...form, source_name: e.target.value})} placeholder={t("Kaynak adı (ör. şirket kariyer sayfası)")} className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" />
            <input value={form.source_url} onChange={(e) => setForm({...form, source_url: e.target.value})} placeholder={t("Kaynak URL (isteğe bağlı)")} type="url" className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" />
            <label className="text-xs text-slate-400">{t("Kaynak tarihi")}<input value={form.as_of} onChange={(e) => setForm({...form, as_of: e.target.value})} type="date" className="mt-1 w-full bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2 text-sm text-white" /></label>
            <input value={form.sample_size} onChange={(e) => setForm({...form, sample_size: e.target.value})} placeholder={t("Örneklem büyüklüğü (isteğe bağlı)")} type="number" min="1" className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" />
            <input value={form.source_count} onChange={(e) => setForm({...form, source_count: e.target.value})} placeholder={t("Bağımsız kaynak sayısı (isteğe bağlı)")} type="number" min="1" className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500" />
          </div>
          <p className="text-xs text-slate-400">{t("Kanıt puanı yalnızca sağladığın kaynak bilgisinin tamlığını ölçer. Veriler bağımsız olarak doğrulanmaz.")}</p>
          <button onClick={handleAdd} className="px-5 py-2 bg-yellow-600 hover:bg-yellow-500 text-white rounded-xl text-sm font-medium">{t("Kaydet")}</button>
        </div>
      )}
    </div>
  );
}
