document.addEventListener("DOMContentLoaded", async () => {
  const engineStatus = document.getElementById("engineStatus");
  const activeUrlDiv = document.getElementById("activeUrl");
  const feedback = document.getElementById("feedback");
  const apiBaseInput = document.getElementById("apiBaseUrl");
  const dashboardInput = document.getElementById("dashboardUrl");
  const savedConfig = await CareerAgentExtensionConfig.get();
  apiBaseInput.value = savedConfig.apiBaseUrl;
  dashboardInput.value = savedConfig.dashboardUrl;

  document.getElementById("saveConfigBtn").addEventListener("click", async () => {
    try {
      const config = await CareerAgentExtensionConfig.save(apiBaseInput.value, dashboardInput.value);
      apiBaseInput.value = config.apiBaseUrl;
      dashboardInput.value = config.dashboardUrl;
      feedback.innerText = "Adresler kaydedildi.";
      await checkBackend();
    } catch (error) {
      feedback.innerText = error.message || "Adresler kaydedilemedi.";
    }
  });

  function apiRequest(method, endpoint, body) {
    return chrome.runtime.sendMessage({ type: "career-agent-api-request", method, endpoint, body });
  }

  async function checkBackend() {
    const response = await apiRequest("GET", "/scrape/health");
    if (response?.ok) {
      engineStatus.innerText = "● Backend: Bağlı & oturum açık";
      engineStatus.style.color = "#34d399";
      return true;
    }
    engineStatus.innerText = response?.status === 401 ? "○ Panelde oturum aç" : "○ Backend: Çevrimdışı";
    engineStatus.style.color = "#f43f5e";
    return false;
  }

  // 1. Check Backend Connectivity
  await checkBackend();

  // 2. Query Active Tab
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs && tabs[0]) {
      const url = new URL(tabs[0].url);
      activeUrlDiv.innerText = `${url.hostname}${url.pathname.slice(0, 24)}...`;
    }
  });

  // 3. Inject Copilot to Active Tab
  document.getElementById("injectCopilotBtn").addEventListener("click", () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs && tabs[0]) {
        chrome.scripting.executeScript({
          target: { tabId: tabs[0].id },
          files: ["content.js"]
        }, () => {
          feedback.innerText = "✓ Copilot sayfada başlatıldı!";
        });
      }
    });
  });

  // 4. Check LinkedIn Session Status from Backend
  const sessionStatusBadge = document.getElementById("sessionStatusBadge");
  const syncSessionBtn = document.getElementById("syncSessionBtn");

  async function checkSessionStatus() {
    try {
      const response = await apiRequest("GET", "/scrape/linkedin_session_status");
      if (response?.ok) {
        const data = response.data;
        if (data.is_synced && data.has_li_at) {
          sessionStatusBadge.innerText = `● Aktif (${data.cookie_count} çerez)`;
          sessionStatusBadge.style.background = "rgba(16, 185, 129, 0.2)";
          sessionStatusBadge.style.color = "#34d399";
        } else {
          sessionStatusBadge.innerText = "○ Senkronize Değil";
          sessionStatusBadge.style.background = "rgba(244, 63, 94, 0.2)";
          sessionStatusBadge.style.color = "#f43f5e";
        }
      }
    } catch (e) {
      sessionStatusBadge.innerText = "○ Bilinmiyor";
    }
  }
  checkSessionStatus();

  // 5. LinkedIn Session Handshake (Export Cookies to Playwright Backend)
  syncSessionBtn.addEventListener("click", () => {
    syncSessionBtn.disabled = true;
    syncSessionBtn.innerText = "⏳ Çerezler Çekiliyor...";
    feedback.innerText = "LinkedIn çerezleri taranıyor...";

    chrome.cookies.getAll({ domain: "linkedin.com" }, async (cookies) => {
      if (!cookies || cookies.length === 0) {
        feedback.innerText = "❌ LinkedIn çerezi bulunamadı. Lütfen tarayıcıda linkedin.com'a giriş yapın.";
        syncSessionBtn.disabled = false;
        syncSessionBtn.innerText = "🤝 Oturumu Senkronize Et";
        return;
      }

      const hasLiAt = cookies.some(c => c.name === "li_at");
      if (!hasLiAt) {
        feedback.innerText = "⚠️ 'li_at' oturum çerezi bulunamadı. Lütfen LinkedIn hesabınıza giriş yapın.";
        syncSessionBtn.disabled = false;
        syncSessionBtn.innerText = "🤝 Oturumu Senkronize Et";
        return;
      }

      // Format for Playwright stealth worker
      const formatted = cookies.map(c => ({
        name: c.name,
        value: c.value,
        domain: c.domain,
        path: c.path,
        expires: c.expirationDate || Math.floor(Date.now() / 1000) + 86400 * 365,
        httpOnly: c.httpOnly,
        secure: c.secure,
        sameSite: c.sameSite === "no_restriction" ? "None" : (c.sameSite === "lax" ? "Lax" : "Strict")
      }));

      try {
        const response = await apiRequest("POST", "/scrape/sync_linkedin_session", { cookies: formatted });
        const result = response?.data || {};
        if (response?.ok && result.status === "SUCCESS") {
          feedback.innerText = `✓ Başarılı! ${result.cookie_count} çerez Playwright motoruna aktarıldı.`;
          sessionStatusBadge.innerText = `● Aktif (${result.cookie_count} çerez)`;
          sessionStatusBadge.style.background = "rgba(16, 185, 129, 0.2)";
          sessionStatusBadge.style.color = "#34d399";
        } else {
          feedback.innerText = `❌ Hata: ${result.message || "Bilinmeyen hata"}`;
        }
      } catch (err) {
        feedback.innerText = "❌ Backend bağlantısı kurulamadı.";
      } finally {
        syncSessionBtn.disabled = false;
        syncSessionBtn.innerText = "🤝 Oturumu Tekrar Senkronize Et";
      }
    });
  });

  // 6. Open Web Dashboard
  document.getElementById("openDashboardBtn").addEventListener("click", () => {
    chrome.tabs.create({ url: dashboardInput.value || savedConfig.dashboardUrl });
  });

  // 7. Open Telegram Web / Config
  document.getElementById("openTelegramBtn").addEventListener("click", () => {
    chrome.tabs.create({ url: `${dashboardInput.value || savedConfig.dashboardUrl}/inbox` });
  });
});
