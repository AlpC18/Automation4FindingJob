(() => {
  const DEFAULTS = {
    apiBaseUrl: "http://127.0.0.1:18000/api",
    dashboardUrl: "http://127.0.0.1:13000",
  };

  function normalizeUrl(value, fallback, { api = false } = {}) {
    const url = new URL((value || fallback).trim());
    const isLocal = ["localhost", "127.0.0.1"].includes(url.hostname);
    if (!isLocal || url.protocol !== "http:") {
      throw new Error("Bu eklenti şu an yalnızca bu bilgisayardaki localhost adreslerine bağlanır.");
    }
    if (url.username || url.password || url.search || url.hash) {
      throw new Error("Adres kullanıcı bilgisi, sorgu veya parça içeremez.");
    }
    url.pathname = api ? `${url.pathname.replace(/\/+$/, "") || ""}` : url.pathname.replace(/\/+$/, "");
    return url.toString().replace(/\/$/, "");
  }

  function get() {
    return new Promise((resolve) => {
      chrome.storage.local.get(DEFAULTS, (saved) => {
        let apiBaseUrl = DEFAULTS.apiBaseUrl;
        let dashboardUrl = DEFAULTS.dashboardUrl;
        try { apiBaseUrl = normalizeUrl(saved.apiBaseUrl, DEFAULTS.apiBaseUrl, { api: true }); } catch {}
        try { dashboardUrl = normalizeUrl(saved.dashboardUrl, DEFAULTS.dashboardUrl); } catch {}
        resolve({ apiBaseUrl, dashboardUrl });
      });
    });
  }

  async function save(apiBaseUrl, dashboardUrl) {
    const normalized = {
      apiBaseUrl: normalizeUrl(apiBaseUrl, DEFAULTS.apiBaseUrl, { api: true }),
      dashboardUrl: normalizeUrl(dashboardUrl, DEFAULTS.dashboardUrl),
    };
    await chrome.storage.local.set(normalized);
    return normalized;
  }

  globalThis.CareerAgentExtensionConfig = { get, save, defaults: { ...DEFAULTS } };
})();
