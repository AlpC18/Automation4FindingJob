"use client";
import { useEffect, useRef, useState } from "react";
import { Bell, X, CheckCircle2, Clock, Sparkles, AlertCircle, Trash2 } from "lucide-react";
import { getApiAuthToken, getWebSocketUrl, isMultiTenantEnabled } from "@/lib/runtime-config";
import { fetchFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

export interface NotificationItem {
  id: string;
  title: string;
  message: string;
  type: "success" | "warning" | "info";
  timestamp: string;
  persisted?: boolean;
}

export default function NotificationDrawer() {
  const { locale, translate: t } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [toast, setToast] = useState<NotificationItem | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);

  function playDing() {
    try {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      const context = audioContextRef.current || new AudioContextClass();
      audioContextRef.current = context;
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(880, context.currentTime);
      oscillator.frequency.exponentialRampToValueAtTime(1320, context.currentTime + 0.08);
      gain.gain.setValueAtTime(0.0001, context.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.12, context.currentTime + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.22);
      oscillator.connect(gain).connect(context.destination);
      oscillator.start();
      oscillator.stop(context.currentTime + 0.24);
    } catch {
      // Browsers can block Web Audio until a user gesture; toast still appears.
    }
  }

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem("career-agent-notifications");
      if (saved) {
        const parsed = JSON.parse(saved) as NotificationItem[];
        setNotifications(parsed.filter((item) => item.id !== "init-1"));
        setUnreadCount(0);
      }
    } catch (_) {}
  }, []);

  useEffect(() => {
    if (!isMultiTenantEnabled()) return;
    fetchFromApi("/notifications").then((result) => {
      const saved = (result.notifications || []).map((item: any) => ({
        id: item.id, title: item.title, message: item.body, type: "info" as const,
        timestamp: new Date(item.created_at).toLocaleString(locale === "en" ? "en-US" : "tr-TR"), persisted: true,
      }));
      setNotifications(saved);
      setUnreadCount((result.notifications || []).filter((item: any) => !item.read_at).length);
    }).catch(() => {});
  }, [locale]);

  useEffect(() => {
    try {
      window.localStorage.setItem("career-agent-notifications", JSON.stringify(notifications.slice(0, 25)));
    } catch (_) {}
  }, [notifications]);

  useEffect(() => {
    // Listen to global WebSocket if available
    let ws: WebSocket | null = null;
    try {
      const wsUrl = getWebSocketUrl();
      const apiToken = getApiAuthToken();
      const securedWsUrl = apiToken ? `${wsUrl}?api_key=${encodeURIComponent(apiToken)}` : wsUrl;

      ws = new WebSocket(securedWsUrl);

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          let newNotif: NotificationItem | null = null;

          if (payload.type === "auto_apply_draft_ready") {
            newNotif = {
              id: `notif-${Date.now()}`,
              title: "Yeni Başvuru Onayı Bekliyor",
              message: `${payload.data?.company} — ${payload.data?.title} (%${payload.data?.score} Uyum)`,
              type: "warning",
              timestamp: new Date().toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })
            };
          } else if (payload.type === "kanban_auto_move") {
            newNotif = {
              id: `notif-${Date.now()}`,
              title: "Kanban Aşaması Güncellendi",
              message: `${payload.data?.company} başvurusu '${payload.data?.new_status}' aşamasına taşındı.`,
              type: "success",
              timestamp: new Date().toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })
            };
          } else if (payload.type === "kanban_stage_changed") {
            const isAppliedStage = payload.data?.new_status === "Applied";
            newNotif = {
              id: `notif-${Date.now()}`,
              title: "Kanban kartı taşındı",
              message: isAppliedStage
                ? "Kart Applied aşamasına alındı; dış başvuru doğrulaması bekleniyor."
                : `Kart '${payload.data?.new_status}' aşamasına alındı.`,
              type: isAppliedStage ? "warning" : "success",
              timestamp: new Date().toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })
            };
          } else if (payload.type === "submission_confirmed") {
            newNotif = {
              id: `notif-${Date.now()}`,
              title: "Başvuru doğrulandı",
              message: "Portal gönderimi gerçek başvuru olarak kaydedildi.",
              type: "success",
              timestamp: new Date().toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })
            };
          } else if (payload.type === "daemon_event") {
            newNotif = {
              id: `notif-${Date.now()}`,
              title: "Arka Plan Görevi Tamamlandı",
              message: payload.data?.action === "morning_prep_completed" ? `${payload.data?.prepared_count} ilan hazırlandı.` : "Gece taraması tamamlandı.",
              type: "info",
              timestamp: new Date().toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })
            };
          }

          if (newNotif) {
            setNotifications((prev) => [newNotif!, ...prev.slice(0, 25)]);
            setUnreadCount((c) => c + 1);
            setToast(newNotif);
            window.setTimeout(() => setToast(null), 4500);
            playDing();
            if ("Notification" in window && Notification.permission === "granted") {
              new Notification(newNotif.title, { body: newNotif.message });
            }
          }
        } catch (e) {}
      };
    } catch (e) {}

    return () => {
      if (ws) ws.close();
    };
  }, []);

  function toggleOpen() {
    void audioContextRef.current?.resume();
    setIsOpen(!isOpen);
    if (!isOpen) {
      setUnreadCount(0);
      if (isMultiTenantEnabled()) {
        notifications.filter((item) => item.persisted).forEach((item) => {
          void fetchFromApi(`/notifications/${item.id}/read`, { method: "POST", body: "{}" });
        });
      }
      if ("Notification" in window && Notification.permission === "default") {
        void Notification.requestPermission();
      }
    }
  }

  function clearAll() {
    setNotifications([]);
    setUnreadCount(0);
  }

  return (
    <>
      {/* Bell Button */}
      <button
        onClick={toggleOpen}
        className="relative p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-white hover:border-slate-700 transition-colors"
        title={t("Canlı Bildirimler")}
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-rose-500 text-white text-[10px] font-bold flex items-center justify-center animate-pulse">
            {unreadCount}
          </span>
        )}
      </button>

      {/* Slide-over Drawer */}
      {isOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/60 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="absolute inset-y-0 right-0 max-w-sm w-full bg-slate-900 border-l border-slate-800 shadow-2xl p-5 flex flex-col space-y-4">
            {/* Drawer Header */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2 text-sm font-bold text-white">
                <Bell className="w-4 h-4 text-blue-400" />
                <span>{t("Canlı Bildirim Merkezi")}</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={clearAll}
                  className="text-slate-500 hover:text-slate-300 p-1 text-xs"
                  title={t("Tümünü Temizle")}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setIsOpen(false)}
                  className="text-slate-400 hover:text-white p-1"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Notification Items List */}
            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {notifications.length === 0 ? (
                <div className="text-center py-16 text-xs text-slate-500">{t("Bildirim bulunmuyor.")}</div>
              ) : (
                notifications.map((item) => (
                  <div
                    key={item.id}
                    className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-white flex items-center gap-1.5">
                        {item.type === "warning" && <Clock className="w-3.5 h-3.5 text-amber-400" />}
                        {item.type === "success" && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                        {item.type === "info" && <Sparkles className="w-3.5 h-3.5 text-blue-400" />}
                    {t(item.title)}
                      </span>
                      <span className="text-[10px] text-slate-500 font-mono">{item.timestamp}</span>
                    </div>
                    <p className="text-[11px] text-slate-400 leading-relaxed">{t(item.message)}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {toast && !isOpen && (
        <div className="fixed bottom-5 right-5 z-40 w-80 rounded-xl border border-blue-500/30 bg-slate-900/95 p-3 shadow-2xl shadow-blue-950/40 backdrop-blur animate-in slide-in-from-right-4 duration-200">
          <div className="text-xs font-semibold text-white">{t(toast.title)}</div>
          <div className="mt-1 text-[11px] leading-relaxed text-slate-400">{t(toast.message)}</div>
        </div>
      )}
    </>
  );
}
