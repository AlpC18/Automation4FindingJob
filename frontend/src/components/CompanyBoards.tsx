"use client";

import { useEffect, useState } from "react";
import { Building2, Plus, Trash2 } from "lucide-react";
import { fetchFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

type Board = { provider: string; slug: string; origin: "env" | "saved" };
type BoardsResponse = { boards: Board[]; open_jobs?: number };

export default function CompanyBoards() {
  const { translate: t } = useLanguage();
  const [boards, setBoards] = useState<Board[]>([]);
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  useEffect(() => {
    fetchFromApi<BoardsResponse>("/scrape/company-boards")
      .then((result) => setBoards(result.boards || []))
      .catch(() => setMessage({ kind: "error", text: t("Şirket sayfaları yüklenemedi.") }));
  }, []);

  async function change(request: Promise<BoardsResponse>, success: (result: BoardsResponse) => string) {
    setBusy(true);
    setMessage(null);
    try {
      const result = await request;
      setBoards(result.boards || []);
      setMessage({ kind: "ok", text: success(result) });
      return true;
    } catch (cause: unknown) {
      setMessage({ kind: "error", text: cause instanceof Error && cause.message ? cause.message : t("İşlem başarısız oldu.") });
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function add() {
    const added = await change(
      fetchFromApi<BoardsResponse>("/scrape/company-boards", { method: "POST", body: JSON.stringify({ board: reference.trim() }) }),
      (result) => t("Eklendi; şu an {count} açık ilan listeliyor.", { count: result.open_jobs ?? 0 }),
    );
    if (added) setReference("");
  }

  function remove(board: Board) {
    return change(
      fetchFromApi<BoardsResponse>(`/scrape/company-boards/${encodeURIComponent(board.provider)}/${encodeURIComponent(board.slug)}`, { method: "DELETE" }),
      () => t("Şirket sayfası kaldırıldı."),
    );
  }

  return (
    <section aria-labelledby="company-boards-title" className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <h2 id="company-boards-title" className="flex items-center gap-2 text-lg font-semibold text-white">
        <Building2 className="h-5 w-5 text-blue-400" /> {t("Takip edilen şirket kariyer sayfaları")}
      </h2>
      <p className="mt-1 text-xs text-slate-400">
        {t("Greenhouse, Lever veya Ashby kullanan şirketlerin ilanları anahtarsız taranır. Kariyer sayfasının adresini yapıştır ya da greenhouse:stripe biçiminde yaz.")}
      </p>
      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <label htmlFor="companyBoardReference" className="sr-only">{t("Kariyer sayfası adresi")}</label>
        <input
          id="companyBoardReference"
          value={reference}
          onChange={(event) => setReference(event.target.value)}
          placeholder="https://jobs.lever.co/spotify"
          className="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
        />
        <button
          type="button"
          onClick={add}
          disabled={busy || !reference.trim()}
          className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:opacity-50"
        >
          <Plus className="h-4 w-4" /> {busy ? t("Kontrol ediliyor…") : t("Şirket ekle")}
        </button>
      </div>
      {message && (
        <div role={message.kind === "error" ? "alert" : "status"} className={`mt-3 rounded-xl border px-4 py-2 text-xs ${message.kind === "error" ? "border-amber-500/25 bg-amber-500/10 text-amber-200" : "border-emerald-500/25 bg-emerald-500/10 text-emerald-200"}`}>
          {message.text}
        </div>
      )}
      {boards.length === 0 ? (
        <p className="mt-4 text-xs text-slate-500">{t("Henüz takip edilen şirket yok.")}</p>
      ) : (
        <ul className="mt-4 space-y-2">
          {boards.map((board) => (
            <li key={`${board.provider}:${board.slug}`} className="flex items-center justify-between gap-3 rounded-xl border border-slate-800 px-4 py-2">
              <span className="text-sm text-white">{board.slug} <span className="text-xs text-slate-400">· {board.provider}</span></span>
              {board.origin === "env" ? (
                <span className="text-[11px] text-slate-500">{t(".env dosyasından")}</span>
              ) : (
                <button
                  type="button"
                  onClick={() => remove(board)}
                  disabled={busy}
                  aria-label={t("{name} şirketini kaldır", { name: board.slug })}
                  className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-800 hover:text-red-300 disabled:opacity-50"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
