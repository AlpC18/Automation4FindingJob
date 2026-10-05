"use client";
import { useLanguage } from "@/lib/i18n";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { fetchFromApi } from "@/lib/api";

export default function ResetPasswordPage() {
  const { translate: t } = useLanguage();
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token") || "");
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setError("");
    if (token && password !== confirmation) {
      setError(t("Parola tekrarı eşleşmiyor."));
      return;
    }
    setBusy(true);
    try {
      if (token) {
        const result = await fetchFromApi("/auth/password-reset", {
          method: "POST",
          body: JSON.stringify({ token, new_password: password }),
        });
        setMessage(result.message || "Parola güncellendi. Giriş ekranına dönebilirsiniz.");
        setToken("");
      } else {
        const result = await fetchFromApi("/auth/password-reset-request", {
          method: "POST",
          body: JSON.stringify({ email }),
        });
        setMessage(result.message || "Adres kayıtlıysa sıfırlama talimatları gönderildi.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "İstek tamamlanamadı.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen grid place-items-center bg-[#070b12] px-4 text-slate-100">
      <form onSubmit={submit} className="w-full max-w-md space-y-5 rounded-2xl border border-slate-800 bg-slate-900/80 p-7">
        <div>
          <h1 className="text-xl font-bold">{token ? "Yeni parola belirle" : t("Parola sıfırlama")}</h1>
          <p className="mt-1 text-sm text-slate-400">{token ? t("Yeni parolanız en az 12 karakter olmalı.") : t("E-posta adresinizi girin; adres kayıtlıysa size güvenli bağlantı gönderelim.")}</p>
        </div>
        {!token ? (
          <label className="block text-xs text-slate-400">{t("E-posta")}<input required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white" />
          </label>
        ) : (
          <>
            <label className="block text-xs text-slate-400">{t("Yeni parola")}<input required minLength={12} type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white" />
            </label>
            <label className="block text-xs text-slate-400">{t("Parolayı tekrar girin")}<input required minLength={12} type="password" autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white" />
            </label>
          </>
        )}
        {message && <p role="status" className="text-xs text-emerald-300">{message}</p>}
        {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}
        <button disabled={busy} className="w-full rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold disabled:opacity-50">{busy ? t("Lütfen bekleyin…") : token ? t("Parolayı güncelle") : t("Sıfırlama bağlantısı gönder")}</button>
        <Link href="/" className="block text-center text-xs text-slate-400 hover:text-blue-300">{t("Giriş ekranına dön")}</Link>
      </form>
    </main>
  );
}
