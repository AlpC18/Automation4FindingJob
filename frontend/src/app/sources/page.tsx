"use client";

import { useEffect, useState } from "react";
import { Activity, CheckCircle2, Eye, EyeOff, Save, ShieldAlert, Upload, XCircle } from "lucide-react";
import { fetchFromApi, requestFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import SetupSteps from "@/components/SetupSteps";
import CompanyBoards from "@/components/CompanyBoards";

const providers = [
  { id: "linkedin", title: "LinkedIn" },
  { id: "upwork", title: "Upwork" },
  { id: "kosovajob", title: "KosovaJob" },
  { id: "fiverr", title: "Fiverr" },
  { id: "freelancer", title: "Freelancer.com" },
  { id: "toptal", title: "Toptal" },
  { id: "gjirafawork", title: "GjirafaWork" },
  { id: "kariyernet", title: "Kariyer.net" },
  { id: "indeed", title: "Indeed" },
  { id: "glassdoor", title: "Glassdoor" },
  { id: "wellfound", title: "Wellfound" },
];

type ProviderConfig = { actor_id: string; input_json: string; enabled: boolean; token_configured: boolean; token_count: number; token_needs_reentry?: boolean };
type ProviderHealth = { status: string; configured: boolean; last_error?: string | null; last_run_at?: number | null; last_jobs_count: number; runs_7d: number; successes_7d: number; runs_today?: number; daily_run_limit?: number; max_items_per_run?: number; max_charge_per_run_usd?: number };
type QuotaAccount = { slot: number; masked: string; valid: boolean; used_usd: number | null; remaining_usd: number | null; error?: string | null };

export default function SourcesPage() {
  const { translate: t } = useLanguage();
  const [configs, setConfigs] = useState<Record<string, ProviderConfig>>({});
  const [health, setHealth] = useState<Record<string, ProviderHealth>>({});
  const [tokens, setTokens] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [backupBusy, setBackupBusy] = useState(false);
  const [restoreBusy, setRestoreBusy] = useState(false);
  const [restoreConfirmation, setRestoreConfirmation] = useState("");
  const [restoreFile, setRestoreFile] = useState<File | null>(null);
  const [testBusy, setTestBusy] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, string>>({});
  const [quotaAccounts, setQuotaAccounts] = useState<QuotaAccount[]>([]);
  const [revealedTokens, setRevealedTokens] = useState<Record<string, string[]>>({});
  const [revealBusy, setRevealBusy] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const result = await fetchFromApi("/scrape/sources");
      const next: Record<string, ProviderConfig> = {};
      for (const provider of result.sources || []) next[provider.source] = provider;
      setConfigs(next);
      setHealth(result.health || {});
      setNotice("");
    } catch (error: any) {
      setNotice(error.message || t("Veriler yüklenemedi. Sayfayı yenileyip tekrar dene."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  useEffect(() => {
    fetchFromApi("/scrape/apify-quota").then((result) => setQuotaAccounts(result.accounts || [])).catch(() => setQuotaAccounts([]));
  }, []);

  async function toggleReveal(providerId: string) {
    if (revealedTokens[providerId]) {
      setRevealedTokens((current) => { const next = { ...current }; delete next[providerId]; return next; });
      return;
    }
    setRevealBusy(providerId);
    try {
      const result = await fetchFromApi(`/scrape/sources/${providerId}/tokens/reveal`, { method: "POST", cache: "no-store" });
      setRevealedTokens((current) => ({ ...current, [providerId]: result.tokens || [] }));
    } catch (error: any) {
      setNotice(error.message || t("Kayıtlı tokenlar yerel ekranda gösterilemedi."));
    } finally { setRevealBusy(null); }
  }

  async function save(providerId: string) {
    const config = configs[providerId];
    if (!config) return;
    setBusy(providerId);
    setNotice("");
    try {
      await fetchFromApi(`/scrape/sources/${providerId}`, {
        method: "PUT",
        body: JSON.stringify({ ...config, api_token: tokens[providerId] || null }),
      });
      setTokens((current) => ({ ...current, [providerId]: "" }));
      setRevealedTokens((current) => { const next = { ...current }; delete next[providerId]; return next; });
      setNotice(t("Kaynak ayarları kaydedildi."));
      await load();
    } catch (error: any) {
      setNotice(error.message || "Kaydetme başarısız.");
    } finally { setBusy(null); }
  }

  async function testConnection(providerId: string) {
    setTestBusy(providerId);
    setTestResults((current) => ({ ...current, [providerId]: "" }));
    try {
      const config = configs[providerId];
      const result = await fetchFromApi(`/scrape/sources/${providerId}/test`, {
        method: "POST",
        body: JSON.stringify({ ...config, api_token: tokens[providerId] || null }),
      });
      setTestResults((current) => ({ ...current, [providerId]: `${t("Bağlantı başarılı")}${result.actor_name ? ` · ${result.actor_name}` : ""}` }));
    } catch (error: any) {
      setTestResults((current) => ({ ...current, [providerId]: error.message || "Bağlantı kurulamadı." }));
    } finally { setTestBusy(null); }
  }

  async function downloadBackup() {
    setBackupBusy(true);
    try {
      const response = await requestFromApi("/system/backup");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = response.headers.get("content-disposition")?.match(/filename="?([^";]+)"?/)?.[1] || "career-agent.sqlite3";
      anchor.click();
      URL.revokeObjectURL(url);
      setNotice(t("Veritabanı yedeği indirildi. Güvenli bir yerde saklayın."));
    } catch (error: any) { setNotice(error.message || "Yedek indirilemedi."); }
    finally { setBackupBusy(false); }
  }

  async function restoreBackup() {
    if (!restoreFile || restoreConfirmation.trim() !== "RESTORE") return;
    setRestoreBusy(true);
    try {
      const body = new FormData();
      body.append("backup_file", restoreFile);
      body.append("confirmation", restoreConfirmation.trim());
      const response = await requestFromApi("/system/backup/restore", { method: "POST", body });
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(result.detail || t("Yedek geri yüklenemedi."));
      }
      const result = await response.json();
      await load();
      setNotice(t("Yedek geri yüklendi. Güvenlik kopyası: {name}", { name: result.safety_backup }));
      setRestoreFile(null);
      setRestoreConfirmation("");
    } catch (error: any) {
      setNotice(error.message || t("Yedek geri yüklenemedi."));
    } finally { setRestoreBusy(false); }
  }

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-6 lg:p-10">
      <SetupSteps />
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
        <p className="text-sm font-semibold uppercase tracking-widest text-blue-400">{t("Kaynak yönetimi")}</p>
        <h1 className="mt-2 text-3xl font-bold text-white">{t("İş ilanı sağlayıcıları")}</h1>
        <p className="mt-2 text-slate-400">{t("Actor kimliğini, erişim anahtarını ve sağlayıcıya özel arama girdisini yapılandır. Kayıtlı anahtarları yerel ekranda açarak görebilirsin.")}</p>
        </div>
        <button onClick={downloadBackup} disabled={backupBusy} className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50">{backupBusy ? t("Yedek hazırlanıyor…") : t("Hesap verisini yedekle")}</button>
      </header>
      <section className="space-y-4 rounded-2xl border border-amber-500/30 bg-amber-950/10 p-5">
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 text-amber-300" size={20} />
          <div><h2 className="font-semibold text-white">{t("Hesap yedeğini geri yükle")}</h2><p className="mt-1 text-sm text-slate-400">{t("Geri yükleme bu hesaptaki mevcut çalışma verilerini seçilen yedekle değiştirir. Önce otomatik güvenlik yedeği alınır.")}</p></div>
        </div>
        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
          <label className="block text-sm text-slate-300">{t("Yedek dosyası")}<input type="file" accept=".sqlite3,.db,.cagbackup,application/octet-stream,application/vnd.sqlite3" onChange={(event) => setRestoreFile(event.target.files?.[0] || null)} className="mt-2 block w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-xs text-slate-300 file:mr-3 file:rounded file:border-0 file:bg-slate-800 file:px-3 file:py-2 file:text-slate-200" /></label>
          <label className="block text-sm text-slate-300">{t("Onaylamak için RESTORE yaz")}<input value={restoreConfirmation} onChange={(event) => setRestoreConfirmation(event.target.value)} autoComplete="off" className="mt-2 block w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" /></label>
          <button onClick={restoreBackup} disabled={restoreBusy || !restoreFile || restoreConfirmation.trim() !== "RESTORE"} className="inline-flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40"><Upload size={16} />{restoreBusy ? t("Geri yükleniyor…") : t("Yedeği geri yükle")}</button>
        </div>
        <p className="text-xs text-slate-400">{t("Yalnızca uygulamanın indirdiği SQLite hesap yedekleri desteklenir. Şifreli otomatik yedekler için aynı uygulama şifreleme anahtarı gerekir.")}</p>
      </section>
      {notice && (
        <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-700 bg-slate-900 p-3 text-sm text-slate-200">
          <span>{notice}</span>
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1 text-xs text-white hover:bg-slate-700"
          >
            {t("Yenile")}
          </button>
        </div>
      )}
      <CompanyBoards />
      <div className="grid gap-5">
        {providers.map((provider) => {
          const config = configs[provider.id];
          const status = health[provider.id];
          if (!config) {
            return (
              <div key={provider.id} className="rounded-2xl border border-slate-800 p-5 text-slate-400">
                {provider.title} {loading ? t("ayarları yükleniyor…") : `· ${t("Yapılandırılmadı")}`}
              </div>
            );
          }
          return <section key={provider.id} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="mb-5 flex items-start justify-between gap-3">
              <div><h2 className="text-lg font-semibold text-white">{provider.title}</h2><p className="mt-1 text-xs text-slate-400">{status?.configured ? t("Yapılandırılmış") : t("Kurulum gerekiyor")} · {status?.runs_7d ?? 0} {t("çalışma / 7 gün")} · {status?.successes_7d ?? 0} {t("başarılı")}</p><p className="mt-1 text-xs text-slate-400">{t("Bugünkü Actor çalışması")}{t(":")}{status?.runs_today ?? 0}/{status?.daily_run_limit ?? 0} · {t("çalışma başına en fazla ilan")}{t(":")}{status?.max_items_per_run ?? 0} · {t("çalışma başına maliyet üst sınırı")}: ${status?.max_charge_per_run_usd ?? 0}</p></div>
              <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs ${status?.status === "success" || status?.status === "ready" ? "bg-emerald-500/10 text-emerald-300" : status?.status === "error" || status?.status === "blocked" ? "bg-red-500/10 text-red-300" : "bg-amber-500/10 text-amber-300"}`}>
                {status?.status === "error" || status?.status === "blocked" ? <XCircle size={14} /> : <CheckCircle2 size={14} />}{status?.status || "bekleniyor"}
              </span>
            </div>
            {status?.last_error && <p className="mb-4 rounded-lg bg-red-950/40 p-3 text-sm text-red-200">{t("Son hata:")}{status.last_error}</p>}
            {config.token_needs_reentry && <p role="alert" className="mb-4 rounded-lg border border-amber-500/30 bg-amber-950/30 p-3 text-sm text-amber-200">{t("Kayıtlı token bu uygulamanın şifreleme anahtarıyla açılamıyor. Taramanın bu hesabı kullanabilmesi için Apify tokenlarını yeniden girip kaydedin.")}</p>}
            <div className="grid gap-4 md:grid-cols-2">
              <label className="text-sm text-slate-300">{t("Apify Actor ID")}<input value={config.actor_id} onChange={(e) => setConfigs((s) => ({ ...s, [provider.id]: { ...config, actor_id: e.target.value } }))} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white" placeholder="username/actor-name" /></label>
              <label className="text-sm text-slate-300">{t("Apify API tokenları")} {config.token_configured && <span className="text-emerald-400">· {config.token_count} {t("kayıtlı")}</span>}<textarea rows={3} autoComplete="off" spellCheck={false} value={tokens[provider.id] || ""} onChange={(e) => setTokens((s) => ({ ...s, [provider.id]: e.target.value }))} className="mt-1 w-full resize-y rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-white" placeholder={config.token_configured ? t("Yenilemek için anahtarları satır satır gir") : "apify_api_…"} /><span className="mt-1 block text-xs text-slate-400">{t("Her satıra bir token gir. Kaydettikten sonra aşağıdaki listeden tokenları görüntüleyebilir; yalnızca doğrulanmış hesapların kullanıldığını görebilirsin.")}</span></label>
            </div>
            {config.token_configured && <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/50 p-3">
              <div className="mb-2 flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-slate-200">{t("Kayıtlı Apify tokenları")}</p>
                <button type="button" onClick={() => toggleReveal(provider.id)} disabled={revealBusy === provider.id} className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-50">
                  {revealedTokens[provider.id] ? <EyeOff size={14} /> : <Eye size={14} />}{revealBusy === provider.id ? t("Yükleniyor…") : revealedTokens[provider.id] ? t("Gizle") : t("Tam tokenları göster")}
                </button>
              </div>
              <p className="mb-3 text-xs text-slate-400">{t("Tokenlar varsayılan olarak maskelenir. Tam değerler yalnızca bu yerel ekranda isteyince görünür ve sayfadan çıkınca temizlenir.")}</p>
              <ul className="space-y-2">{Array.from({ length: Math.max(config.token_count, revealedTokens[provider.id]?.length || 0) }, (_, index) => {
                const account = provider.id === "linkedin" ? quotaAccounts[index] : undefined;
                const token = revealedTokens[provider.id]?.[index];
                return <li key={index} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-900 px-3 py-2 text-xs">
                  <span className="font-mono text-slate-300">{String(index + 1).padStart(2, "0")} · {token || account?.masked || "••••"}</span>
                  <span className={account ? account.valid ? "text-emerald-400" : "text-red-300" : "text-slate-400"}>{account ? account.valid ? `${t("Doğrulandı")} · $${(account.used_usd || 0).toFixed(2)} / $5 · ${t("kalan")} $${(account.remaining_usd || 0).toFixed(2)}` : t("Apify 401 · token reddedildi") : t("Durum kontrol ediliyor")}</span>
                </li>;
              })}</ul>
            </div>}
            <label className="mt-4 block text-sm text-slate-300">{t("Actor input (JSON)")}<textarea rows={4} value={config.input_json} onChange={(e) => setConfigs((s) => ({ ...s, [provider.id]: { ...config, input_json: e.target.value } }))} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-white" /></label>
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <label className="flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={config.enabled} onChange={(e) => setConfigs((s) => ({ ...s, [provider.id]: { ...config, enabled: e.target.checked } }))} />{t("Bu sağlayıcıyı kullan")}</label>
              <div className="flex flex-wrap gap-2">
                <button onClick={() => testConnection(provider.id)} disabled={testBusy === provider.id} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-200 disabled:opacity-50">{testBusy === provider.id ? t("Test ediliyor…") : t("Bağlantıyı test et")}</button>
                <button onClick={() => save(provider.id)} disabled={busy === provider.id} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-50"><Save size={16} />{busy === provider.id ? t("Kaydediliyor…") : t("Kaydet")}</button>
              </div>
            </div>
            {testResults[provider.id] && <p role="status" className="mt-3 text-xs text-slate-300">{testResults[provider.id]}</p>}
          </section>;
        })}
      </div>
      <aside className="flex gap-3 rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-sm text-slate-400"><Activity className="mt-0.5 shrink-0 text-blue-400" size={18} /><p>{t("Remote OK ve Arbeitnow ücretsiz kaynakları otomatik çalışır. Bu panel Apify tabanlı ek kaynakları ve son çalışma hatalarını gösterir.")}</p></aside>
    </main>
  );
}
