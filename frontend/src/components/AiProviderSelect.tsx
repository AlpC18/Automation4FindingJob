"use client";

import { useEffect, useState } from "react";
import { Cpu } from "lucide-react";
import { fetchFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

type Provider = { id: string; name: string; model: string; is_configured: boolean };

/** Lets the user pick which configured AI the next search (role matching and scoring) runs on. */
export default function AiProviderSelect({ onChange }: { onChange?: (provider: string) => void }) {
  const { translate: t } = useLanguage();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [active, setActive] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchFromApi<{ effective_provider: string; providers: Provider[] }>("/llm/providers")
      .then((res) => {
        setProviders((res.providers || []).filter((provider) => provider.is_configured));
        setActive(res.effective_provider || "");
        onChange?.(res.effective_provider || "");
      })
      .catch((cause: any) => setError(cause?.message || t("Yapay zekâ listesi alınamadı.")));
  }, []);

  async function choose(provider: string) {
    const previous = active;
    setActive(provider);
    setError("");
    try {
      await fetchFromApi("/llm/set_provider", { method: "POST", body: JSON.stringify({ provider }) });
      onChange?.(provider);
    } catch (cause: any) {
      setActive(previous);
      setError(cause?.message || t("Yapay zekâ değiştirilemedi."));
    }
  }

  return (
    <label className="flex items-center gap-2 rounded-xl border border-slate-700 px-3 py-2 text-xs font-semibold text-slate-200" title={t("Bu aramada rol eşleştirme ve puanlama için kullanılacak yapay zekâ")}>
      <Cpu className="h-4 w-4 shrink-0 text-sky-400" />
      <span className="hidden sm:inline">{t("Arama için yapay zekâ")}</span>
      <select value={active} onChange={(event) => void choose(event.target.value)} disabled={!providers.length} aria-label={t("Arama için yapay zekâ")} className="max-w-[13rem] rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-white disabled:opacity-50">
        {providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name} · {provider.model}</option>)}
      </select>
      {error && <span role="status" className="text-red-400">{error}</span>}
    </label>
  );
}
