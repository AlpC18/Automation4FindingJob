"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Plus, Trash2, User, UserPlus, X } from "lucide-react";
import { fetchFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { notify } from "@/lib/notify";

type ProfileItem = {
  id: string;
  name: string;
  is_active: boolean;
  full_name?: string;
  target_role?: string;
  location?: string;
};

export default function CandidateHeader({ compact = false, dense = false }: { compact?: boolean; dense?: boolean }) {
  const { translate: t } = useLanguage();
  const [profiles, setProfiles] = useState<ProfileItem[]>([]);
  const [activeProfile, setActiveProfile] = useState<ProfileItem | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [newModalOpen, setNewModalOpen] = useState(false);
  const [newProfileName, setNewProfileName] = useState("");
  const [newTargetRole, setNewTargetRole] = useState("");
  const [newFullName, setNewFullName] = useState("");
  const [busy, setBusy] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  async function loadProfiles() {
    try {
      const res = await fetchFromApi<{ profiles?: ProfileItem[] }>("/setup/profiles");
      const list = res.profiles || [];
      setProfiles(list);
      const active = list.find((p) => p.is_active) || list[0] || null;
      setActiveProfile(active);
    } catch {
      // Fallback to legacy single profile
      try {
        const legacy = await fetchFromApi<any>("/setup/profile");
        const prof = legacy.profile || {};
        setActiveProfile({
          id: "default",
          name: prof.full_name || t("Ana Profil"),
          is_active: true,
          full_name: prof.full_name,
          target_role: prof.target_role,
        });
      } catch {}
    }
  }

  useEffect(() => {
    void loadProfiles();
  }, []);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function handleSwitchProfile(profileId: string) {
    if (activeProfile?.id === profileId) {
      setMenuOpen(false);
      return;
    }
    try {
      setBusy(true);
      await fetchFromApi(`/setup/profiles/${encodeURIComponent(profileId)}/activate`, { method: "POST" });
      await loadProfiles();
      setMenuOpen(false);
      notify(t("Aktif profil başarıyla değiştirildi. Uyum tahminleri güncellendi."));
      window.location.reload();
    } catch (err: any) {
      notify(err?.message || t("Profil değiştirilemedi."));
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateProfile() {
    if (!newProfileName.trim()) {
      notify(t("Lütfen bir profil adı giriniz."));
      return;
    }
    try {
      setBusy(true);
      await fetchFromApi("/setup/profiles", {
        method: "POST",
        body: JSON.stringify({
          name: newProfileName.trim(),
          target_role: newTargetRole.trim(),
          full_name: newFullName.trim(),
        }),
      });
      setNewModalOpen(false);
      setNewProfileName("");
      setNewTargetRole("");
      setNewFullName("");
      await loadProfiles();
      notify(t("Yeni aday profili oluşturuldu."));
    } catch (err: any) {
      notify(err?.message || t("Profil oluşturulamadı."));
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteProfile(profileId: string, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      setBusy(true);
      await fetchFromApi(`/setup/profiles/${encodeURIComponent(profileId)}`, { method: "DELETE" });
      await loadProfiles();
      notify(t("Profil silindi."));
    } catch (err: any) {
      notify(err?.message || t("Aktif profil silinemez."));
    } finally {
      setBusy(false);
    }
  }

  const name = activeProfile?.name || activeProfile?.full_name?.trim() || t("Aday");
  const role = activeProfile?.target_role?.trim() || t("Profil henüz doldurulmadı");
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase() || "A";

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        onClick={() => setMenuOpen(!menuOpen)}
        className={`flex items-center gap-2.5 rounded-xl border border-slate-800/80 bg-slate-900/60 p-1.5 pr-2.5 text-left transition hover:border-slate-700 hover:bg-slate-850 ${
          menuOpen ? "border-blue-500/50 bg-slate-800" : ""
        }`}
        title={t("Aday profilini değiştir veya yeni profil ekle")}
      >
        <div className={`candidate-avatar flex shrink-0 items-center justify-center rounded-lg font-bold text-white shadow-sm ${
          dense ? "h-7 w-7 text-xs" : "h-8 w-8 text-xs"
        }`}>
          {initials}
        </div>
        <div className={compact ? "min-w-0" : "hidden min-w-0 text-left sm:block"}>
          <div className="flex items-center gap-1">
            <span className={`truncate font-semibold text-white ${dense ? "text-xs" : "text-xs"}`}>{name}</span>
            <ChevronDown className="h-3 w-3 text-slate-400" />
          </div>
          <div className={`muted truncate text-slate-400 ${dense ? "text-[10px]" : "text-[11px]"}`}>{role}</div>
        </div>
      </button>

      {/* Profile Switcher Dropdown */}
      {menuOpen && (
        <div className="absolute right-0 top-full z-50 mt-2 w-72 rounded-2xl border border-slate-700 bg-slate-950 p-2 shadow-2xl backdrop-blur-xl">
          <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2 text-xs font-semibold text-slate-400">
            <span>{t("Aday / Profil Seçici")}</span>
            <span className="font-mono text-[10px] text-blue-400">{profiles.length} {t("profil")}</span>
          </div>

          <div className="max-h-60 overflow-y-auto py-1 space-y-1">
            {profiles.map((p) => {
              const isCurrent = p.is_active;
              return (
                <div
                  key={p.id}
                  onClick={() => void handleSwitchProfile(p.id)}
                  className={`flex items-center justify-between gap-2 rounded-xl p-2.5 text-xs transition cursor-pointer select-none ${
                    isCurrent
                      ? "bg-blue-950/40 border border-blue-500/40 text-blue-200"
                      : "hover:bg-slate-900 text-slate-300"
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg font-bold text-[11px] ${
                      isCurrent ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-400"
                    }`}>
                      {p.name.slice(0, 1).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <div className="font-semibold truncate text-white">{p.name}</div>
                      <div className="text-[10px] text-slate-400 truncate">{p.target_role || t("Rol belirtilmedi")}</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    {isCurrent ? (
                      <span className="rounded-full bg-blue-500/20 px-2 py-0.5 text-[10px] font-semibold text-blue-300">
                        {t("Aktif")}
                      </span>
                    ) : (
                      profiles.length > 1 && (
                        <button
                          type="button"
                          onClick={(e) => void handleDeleteProfile(p.id, e)}
                          className="p-1 text-slate-500 hover:text-rose-400 transition"
                          title={t("Profili sil")}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      )
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="border-t border-slate-800/80 pt-1.5 mt-1">
            <button
              type="button"
              onClick={() => {
                setMenuOpen(false);
                setNewModalOpen(true);
              }}
              className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-slate-700 bg-slate-900/60 p-2 text-xs font-semibold text-blue-300 transition hover:border-blue-500/60 hover:bg-blue-950/20"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>{t("Yeni Profil Ekle (Abla, Arkadaş...)")}</span>
            </button>
          </div>
        </div>
      )}

      {/* New Profile Modal */}
      {newModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true">
          <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-950 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <UserPlus className="h-5 w-5 text-blue-400" />
                <h3 className="text-sm font-bold text-white">{t("Yeni Aday Profili Ekle")}</h3>
              </div>
              <button
                type="button"
                onClick={() => setNewModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="text-xs text-slate-400">
              {t("Kendiniz, ablanız veya arkadaşınız için ayrı bir profil oluşturun. Her profilin hedef ünvanları ve CV'si bağımsız saklanır.")}
            </p>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-slate-300 mb-1">
                  {t("Profil Etiketi / İsmi")} *
                </label>
                <input
                  type="text"
                  value={newProfileName}
                  onChange={(e) => setNewProfileName(e.target.value)}
                  placeholder={t("Örn: Ablam (Mimarlık), Arkadaşım (Ekonomi), Alp (Yazılım)")}
                  className="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-white placeholder:text-slate-500 focus:border-blue-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-300 mb-1">
                  {t("Aday Adı Soyadı")}
                </label>
                <input
                  type="text"
                  value={newFullName}
                  onChange={(e) => setNewFullName(e.target.value)}
                  placeholder={t("Örn: Zeynep Yılmaz")}
                  className="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-white placeholder:text-slate-500 focus:border-blue-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-300 mb-1">
                  {t("Hedef Pozisyon / Meslek")}
                </label>
                <input
                  type="text"
                  value={newTargetRole}
                  onChange={(e) => setNewTargetRole(e.target.value)}
                  placeholder={t("Örn: Interior Architect, Economist, Graphic Designer")}
                  className="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-white placeholder:text-slate-500 focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setNewModalOpen(false)}
                className="rounded-xl border border-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-900"
              >
                {t("İptal")}
              </button>
              <button
                type="button"
                disabled={busy || !newProfileName.trim()}
                onClick={() => void handleCreateProfile()}
                className="rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-blue-500 disabled:opacity-50 shadow-md shadow-blue-600/30"
              >
                {busy ? t("Kaydediliyor...") : t("Profili Oluştur")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
