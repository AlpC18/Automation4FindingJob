"use client";

import { FormEvent, ReactNode, useEffect, useState } from "react";
import { getApiBaseUrl } from "@/lib/runtime-config";
import { fetchFromApi, getApiCsrfToken, requestFromApi, setApiCsrfToken } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

type SessionUser = { id: string; email: string };

export default function SessionGate({ children }: { children: ReactNode }) {
  const { translate: t } = useLanguage();
  const [ready, setReady] = useState(false);
  const [required, setRequired] = useState(false);
  const [user, setUser] = useState<SessionUser | null>(null);
  const [registering, setRegistering] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  async function readJson(response: Response) {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
    return payload;
  }

  async function loadSession() {
    const base = getApiBaseUrl();
    try {
      const modeResponse = await fetch(`${base}/auth/mode`, { credentials: "include" });
      const mode = await readJson(modeResponse);
      if (typeof window !== "undefined") {
        window.__CAREER_AGENT_CONFIG__ = {
          ...(window.__CAREER_AGENT_CONFIG__ || {}),
          multiTenantEnabled: Boolean(mode.authentication_required),
        };
      }
      setRequired(Boolean(mode.authentication_required));
      if (!mode.authentication_required) {
        setApiCsrfToken(null);
        setReady(true);
        return;
      }
      const sessionResponse = await fetch(`${base}/auth/me`, { credentials: "include" });
      const session = await readJson(sessionResponse);
      setUser(session.user);
      setApiCsrfToken(session.csrf_token || session.user?.csrf_token || null);
    } catch {
      setUser(null);
      setApiCsrfToken(null);
    } finally {
      setReady(true);
    }
  }

  useEffect(() => { void loadSession(); }, []);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("verified") === "1") {
      setNotice("E-posta adresiniz doğrulandı. Şimdi giriş yapabilirsiniz.");
    }
  }, []);

  useEffect(() => {
    const handleExpiredSession = () => { setUser(null); setApiCsrfToken(null); };
    window.addEventListener("career-agent:session-expired", handleExpiredSession);
    return () => window.removeEventListener("career-agent:session-expired", handleExpiredSession);
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const endpoint = registering ? "register" : "login";
      const response = await fetch(`${getApiBaseUrl()}/auth/${endpoint}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const payload = await readJson(response);
      if (payload.verification_required) {
        setError(payload.message || "Giriş öncesi e-posta doğrulaması gerekiyor.");
        setRegistering(false);
        return;
      }
      setApiCsrfToken(payload.csrf_token || null);
      setUser(payload.user);
      setPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Oturum açılamadı.");
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    await fetch(`${getApiBaseUrl()}/auth/logout`, {
      method: "POST",
      credentials: "include",
      headers: getApiCsrfToken() ? { "X-CSRF-Token": getApiCsrfToken() as string } : {},
    });
    setApiCsrfToken(null);
    setUser(null);
  }

  async function resendVerification() {
    if (!email) {
      setError("Önce kayıt sırasında kullandığınız e-posta adresini girin.");
      return;
    }
    try {
      const result = await fetchFromApi("/auth/resend-verification", {
        method: "POST", body: JSON.stringify({ email }),
      });
      setNotice(result.message || "Adres uygunsa doğrulama talimatları gönderildi.");
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "E-posta gönderilemedi.");
    }
  }

  async function deleteAccount() {
    if (!user) return;
    const confirmation = window.prompt(t("Hesabı ve tüm verileri kalıcı silmek için {email} yazın.", { email: user.email }));
    if (confirmation !== user.email) return;
    const currentPassword = window.prompt(t("Onay için mevcut parolanızı girin."));
    if (!currentPassword) return;
    const response = await requestFromApi("/auth/account", {
      method: "DELETE",
      body: JSON.stringify({ email: user.email, password: currentPassword }),
    });
    if (response.ok) {
      setApiCsrfToken(null);
      setUser(null);
    }
  }

  if (!ready) return <div className="min-h-screen grid place-items-center bg-[#070b12] text-slate-400">{t("Oturum kontrol ediliyor…")}</div>;
  if (required && !user) {
    return (
      <main className="min-h-screen grid place-items-center bg-[#070b12] px-4 text-slate-100">
        <form onSubmit={handleSubmit} className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/80 p-7 space-y-5">
          <div>
            <h1 className="text-xl font-bold">Career Agent</h1>
            <p className="mt-1 text-sm text-slate-400">{t("Profilinize özel güvenli oturum açın.")}</p>
          </div>
          {notice && <p role="status" className="rounded-lg border border-emerald-500/20 bg-emerald-950/30 p-3 text-xs text-emerald-300">{t(notice)}</p>}
          <label className="block text-xs text-slate-400">{t("E-posta")}
            <input required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white" />
          </label>
          <label className="block text-xs text-slate-400">{t("Parola")}
            <input required type="password" minLength={registering ? 12 : 1} autoComplete={registering ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white" />
            {registering && <span className="mt-1 block text-xs text-slate-400">{t("En az 12 karakter")}</span>}
          </label>
          {error && <p role="alert" className="text-xs text-rose-300">{t(error)}</p>}
          <button disabled={busy} className="w-full rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold disabled:opacity-50">
            {busy ? t("Lütfen bekleyin…") : registering ? t("Hesap oluştur") : t("Giriş yap")}
          </button>
          <button type="button" onClick={() => { setRegistering(!registering); setError(""); }} className="w-full text-xs text-blue-300">
            {registering ? t("Zaten hesabınız var mı? Giriş yapın") : t("Yeni hesap oluştur")}
          </button>
          {!registering && <a href="/reset-password" className="block text-center text-xs text-slate-400 hover:text-blue-300">{t("Parolamı unuttum")}</a>}
          {!registering && <button type="button" onClick={resendVerification} className="w-full text-xs text-slate-400 hover:text-blue-300">{t("Doğrulama e-postasını yeniden gönder")}</button>}
        </form>
      </main>
    );
  }

  return (
    <>
      {required && user && (
        <div className="fixed bottom-3 right-3 z-50 flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/90 p-1.5 text-xs">
          <span className="px-1.5 text-slate-300">{user.email}</span>
          <button onClick={signOut} className="rounded px-2 py-1 text-slate-300 hover:bg-slate-800">{t("Çıkış")}</button>
          <button onClick={deleteAccount} className="rounded px-2 py-1 text-rose-300 hover:bg-rose-950/40">{t("Hesabı sil")}</button>
        </div>
      )}
      {children}
    </>
  );
}
