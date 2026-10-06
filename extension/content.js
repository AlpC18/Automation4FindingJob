/**
 * Career Agent v2 — Enhanced On-Page Live Copilot Content Script
 * Injected into LinkedIn, Upwork, Kosovajob, and Indeed pages.
 *
 * NEW in v2:
 * - 1-Click "Track This Job" button (saves to seen_jobs)
 * - Inline ATS score badge on job cards
 * - Ghost job warning banner on old postings
 * - Salary tooltip on company names
 * - Robots.txt compliance check before deep scrape
 */

(function () {
  if (window.__careerAgentCopilotLoaded) return;
  window.__careerAgentCopilotLoaded = true;

  // ===== STYLES =====
  const STYLES = `
    #career-agent-launcher {
      position: fixed; bottom: 24px; right: 24px; z-index: 999999;
      background: linear-gradient(135deg, #2563eb, #4f46e5); color: #fff;
      padding: 10px 16px; border-radius: 30px;
      box-shadow: 0 8px 24px rgba(37, 99, 235, 0.4);
      cursor: pointer; font-family: -apple-system, system-ui, sans-serif;
      font-size: 13px; display: flex; align-items: center; gap: 6px;
      transition: transform 0.2s;
    }
    #career-agent-launcher:hover { transform: scale(1.05); }

    .cac-track-btn {
      background: linear-gradient(135deg, #059669, #10b981);
      color: #fff; border: none; padding: 6px 14px; border-radius: 20px;
      font-size: 11px; font-weight: 600; cursor: pointer;
      font-family: -apple-system, system-ui, sans-serif;
      box-shadow: 0 2px 8px rgba(5, 150, 105, 0.3);
      transition: all 0.2s; display: inline-flex; align-items: center; gap: 4px;
      margin-left: 8px;
    }
    .cac-track-btn:hover { transform: scale(1.05); background: #059669; }
    .cac-track-btn.tracked { background: #334155; color: #94a3b8; cursor: default; }

    .cac-ats-badge {
      display: inline-flex; align-items: center; gap: 3px;
      padding: 3px 10px; border-radius: 12px;
      font-size: 11px; font-weight: 700; font-family: monospace;
      margin-left: 8px; vertical-align: middle;
    }
    .cac-ats-high { background: #dcfce7; color: #166534; }
    .cac-ats-mid { background: #fef3c7; color: #92400e; }
    .cac-ats-low { background: #fecaca; color: #991b1b; }

    .cac-ghost-banner {
      background: linear-gradient(90deg, #7f1d1d, #991b1b);
      color: #fecaca; padding: 8px 16px; border-radius: 10px;
      font-size: 12px; font-weight: 600; margin: 8px 0;
      display: flex; align-items: center; gap: 8px;
      font-family: -apple-system, system-ui, sans-serif;
    }

    .cac-salary-tooltip {
      position: absolute; z-index: 1000001;
      background: #0b101a; color: #e2e8f0; border: 1px solid #334155;
      padding: 8px 14px; border-radius: 10px; font-size: 12px;
      font-family: monospace; box-shadow: 0 8px 20px rgba(0,0,0,0.5);
      pointer-events: none; white-space: nowrap;
    }

    #career-agent-panel {
      position: fixed; top: 20px; right: 20px; width: 380px; max-height: 88vh;
      overflow-y: auto; z-index: 1000000; background: #0b101a; color: #f8fafc;
      border: 1px solid #1e293b; border-radius: 16px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.6);
      font-family: -apple-system, system-ui, sans-serif;
      padding: 16px; display: none; box-sizing: border-box;
    }
  `;

  const styleTag = document.createElement("style");
  styleTag.textContent = STYLES;
  document.head.appendChild(styleTag);

  // ===== API HELPERS =====
  async function apiPost(endpoint, body = {}) {
    try {
      const response = await chrome.runtime.sendMessage({
        type: "career-agent-api-request", method: "POST", endpoint, body,
      });
      if (!response?.ok) throw new Error(response?.error || "Backend isteği başarısız.");
      return response.data;
    } catch (e) {
      console.warn("[CareerAgent]", endpoint, e);
      return null;
    }
  }

  async function apiGet(endpoint) {
    try {
      const response = await chrome.runtime.sendMessage({
        type: "career-agent-api-request", method: "GET", endpoint,
      });
      if (!response?.ok) throw new Error(response?.error || "Backend isteği başarısız.");
      return response.data;
    } catch (e) {
      console.warn("[CareerAgent]", endpoint, e);
      return null;
    }
  }

  // ===== JOB EXTRACTION =====
  function detectPlatform() {
    const host = location.hostname;
    if (host.includes("linkedin")) return "linkedin";
    if (host.includes("upwork")) return "upwork";
    if (host.includes("indeed")) return "indeed";
    if (host.includes("kosovajob")) return "kosovajob";
    if (host.includes("fiverr")) return "fiverr";
    if (host.includes("freelancer")) return "freelancer";
    if (host.includes("toptal")) return "toptal";
    if (host.includes("gjirafa")) return "gjirafawork";
    if (host.includes("kariyer.net")) return "kariyernet";
    if (host.includes("glassdoor")) return "glassdoor";
    if (host.includes("wellfound")) return "wellfound";
    return "unknown";
  }

  function extractPageJobDetails() {
    let title = "", company = "", desc = "", location = "";

    // LinkedIn selectors
    const liTitle = document.querySelector(".job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, h1");
    if (liTitle) title = liTitle.innerText.trim();

    const liComp = document.querySelector(".job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name, .job-details-jobs-unified-top-card__primary-description a");
    if (liComp) company = liComp.innerText.trim();

    const liDesc = document.querySelector(".jobs-description__content, #job-details, .jobs-box__html-content");
    if (liDesc) desc = liDesc.innerText.trim();

    const liLoc = document.querySelector(".job-details-jobs-unified-top-card__bullet, .jobs-unified-top-card__bullet");
    if (liLoc) location = liLoc.innerText.trim();

    return {
      title: title || document.title,
      company: company || "Belirlenemedi",
      description: desc || document.body.innerText.slice(0, 1500),
      location: location || "",
      url: window.location.href,
      portal: detectPlatform(),
    };
  }

  // ===== 1. TRACK THIS JOB BUTTON =====
  function injectTrackButton() {
    const portal = detectPlatform();
    if (portal === "unknown") return;

    // Find the job title container
    let container = null;
    if (portal === "linkedin") {
      container = document.querySelector(".job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, h1");
    } else {
      container = document.querySelector("h1");
    }

    if (!container || container.querySelector(".cac-track-btn")) return;

    const btn = document.createElement("button");
    btn.className = "cac-track-btn";
    btn.innerHTML = "➕ Takip Et";
    btn.onclick = async (e) => {
      e.stopPropagation();
      e.preventDefault();
      btn.innerHTML = "⏳ Kaydediliyor...";
      btn.disabled = true;

      const job = extractPageJobDetails();
      const result = await apiPost("/scrape/seen_jobs/add", {
        company: job.company,
        title: job.title,
        url: job.url,
        portal: job.portal,
        location: job.location,
      });

      if (result) {
        if (result.is_new) {
          btn.innerHTML = "✅ Takibe Alındı";
          btn.className = "cac-track-btn tracked";
        } else {
          btn.innerHTML = "📌 Zaten Takipte";
          btn.className = "cac-track-btn tracked";
        }
      } else {
        btn.innerHTML = "❌ Hata";
        setTimeout(() => { btn.innerHTML = "➕ Takip Et"; btn.disabled = false; }, 2000);
      }
    };

    container.appendChild(btn);
  }

  // ===== 2. INLINE ATS SCORE BADGE =====
  async function injectATSBadge() {
    const job = extractPageJobDetails();
    if (!job.title || job.company === "Belirlenemedi") return;

    const result = await apiPost("/scrape/analyze_on_the_fly", {
      title: job.title, company: job.company, description: job.description,
    });

    if (!result || result.match_score == null) return;

    const score = Math.round(result.match_score);
    const scoreClass = score >= 75 ? "cac-ats-high" : score >= 50 ? "cac-ats-mid" : "cac-ats-low";

    // Add badge next to title
    const titleEl = document.querySelector(".job-details-jobs-unified-top-card__job-title, h1");
    if (titleEl && !titleEl.querySelector(".cac-ats-badge")) {
      const badge = document.createElement("span");
      badge.className = `cac-ats-badge ${scoreClass}`;
      badge.innerHTML = `🎯 Tahmini uyum ≈ %${score}`;
      badge.title = `Skill match: ${result.skill_match_count || "?"} / ${result.total_required_skills || "?"}`;
      titleEl.appendChild(badge);
    }
  }

  // ===== 3. GHOST JOB WARNING BANNER =====
  async function checkGhostJob() {
    const job = extractPageJobDetails();
    const result = await apiPost("/scrape/analyze_on_the_fly", {
      title: job.title, company: job.company, description: job.description,
    });

    if (!result) return;
    const ghostScore = result.ghost_score || 0;
    if (ghostScore < 35) return;

    // Don't inject twice
    if (document.querySelector(".cac-ghost-banner")) return;

    const banner = document.createElement("div");
    banner.className = "cac-ghost-banner";
    banner.innerHTML = `⚠️ <strong>Hayalet İlan Uyarısı</strong> — Bu ilan %${ghostScore} olasılıkla hayalet/eski ilan. Dikkatli olun.`;

    const descEl = document.querySelector(".jobs-description__content, #job-details, .jobs-box__html-content");
    if (descEl) {
      descEl.parentElement.insertBefore(banner, descEl);
    }
  }

  // ===== 4. SALARY TOOLTIP ON COMPANY NAME =====
  function injectSalaryTooltip() {
    const companyEls = document.querySelectorAll(
      ".job-details-jobs-unified-top-card__company-name a, .jobs-unified-top-card__company-name a, .topcard__org-name-link"
    );

    companyEls.forEach((el) => {
      if (el.dataset.cacSalary) return;
      el.dataset.cacSalary = "1";
      el.style.position = "relative";

      let tooltip = null;

      el.addEventListener("mouseenter", async () => {
        const companyName = el.innerText.trim();
        if (!companyName) return;

        const result = await apiPost("/rank/salary/search", { query: companyName });
        if (!result || !result.results || result.results.length === 0) return;

        const entry = result.results[0];
        const text = entry.salary_min && entry.salary_max
          ? `💰 ${entry.currency} ${entry.salary_min.toLocaleString()} – ${entry.salary_max.toLocaleString()} / ${entry.period}`
          : entry.salary_median
            ? `💰 Medyan: ${entry.currency} ${entry.salary_median.toLocaleString()} / ${entry.period}`
            : null;

        if (!text) return;

        tooltip = document.createElement("div");
        tooltip.className = "cac-salary-tooltip";
        tooltip.textContent = text;
        document.body.appendChild(tooltip);

        const rect = el.getBoundingClientRect();
        tooltip.style.top = (rect.top - 40 + window.scrollY) + "px";
        tooltip.style.left = rect.left + "px";
      });

      el.addEventListener("mouseleave", () => {
        if (tooltip) { tooltip.remove(); tooltip = null; }
      });
    });
  }

  // ===== FLOATING LAUNCHER & PANEL (existing, enhanced) =====
  const launcher = document.createElement("div");
  launcher.id = "career-agent-launcher";
  launcher.innerHTML = "🚀 <b>Career Copilot</b>";

  const panel = document.createElement("div");
  panel.id = "career-agent-panel";
  panel.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1e293b; padding-bottom:10px; margin-bottom:12px;">
      <div style="font-weight:700; font-size:14px; color:#38bdf8; display:flex; align-items:center; gap:6px;">
        <span>🤖</span> Career Agent Copilot v2
      </div>
      <button id="cac-close-btn" style="background:transparent; border:none; color:#94a3b8; font-size:16px; cursor:pointer;">✕</button>
    </div>

    <div style="font-size:11px; color:#94a3b8; margin-bottom:10px;">
      İlan analizi, ATS uyumu, hayalet ilan riski, iş takibi ve cover letter üretimi.
    </div>

    <!-- Scraped Job Info -->
    <div style="background:#131c2e; padding:10px; border-radius:10px; border:1px solid #1e293b; margin-bottom:12px;">
      <div id="cac-job-title" style="font-size:12px; font-weight:700; color:#fff;">Taranıyor...</div>
      <div id="cac-job-company" style="font-size:11px; color:#38bdf8; margin-top:2px;">-</div>
      <div id="cac-job-location" style="font-size:10px; color:#94a3b8; margin-top:2px;">-</div>
    </div>

    <!-- Live ATS Diagnostic Card -->
    <div id="cac-diagnostics" style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin-bottom:12px;">
      <div style="background:#0f172a; padding:8px; border-radius:8px; text-align:center; border:1px solid #1e293b;">
        <div style="font-size:10px; color:#94a3b8;">Tahmini uyum (kural tabanlı)</div>
        <div id="cac-ats-score" style="font-size:14px; font-weight:700; color:#34d399; font-family:monospace;">--%</div>
      </div>
      <div style="background:#0f172a; padding:8px; border-radius:8px; text-align:center; border:1px solid #1e293b;">
        <div style="font-size:10px; color:#94a3b8;">Hayalet Risk</div>
        <div id="cac-ghost-score" style="font-size:14px; font-weight:700; color:#f43f5e; font-family:monospace;">--%</div>
      </div>
      <div style="background:#0f172a; padding:8px; border-radius:8px; text-align:center; border:1px solid #1e293b;">
        <div style="font-size:10px; color:#94a3b8;">Takip</div>
        <div id="cac-track-status" style="font-size:14px; font-weight:700; color:#94a3b8; font-family:monospace;">—</div>
      </div>
    </div>

    <!-- Action Buttons -->
    <div style="display:flex; flex-direction:column; gap:8px; margin-bottom:12px;">
      <button id="cac-analyze-btn" style="background:#2563eb; color:#fff; border:none; padding:8px; border-radius:8px; font-size:12px; font-weight:600; cursor:pointer;">
        ⚡ Anlık Analiz Yap
      </button>
      <button id="cac-track-panel-btn" style="background:#059669; color:#fff; border:none; padding:8px; border-radius:8px; font-size:12px; font-weight:600; cursor:pointer;">
        ➕ Bu İlanı Takip Et
      </button>
      <button id="cac-generate-cl-btn" style="background:#4f46e5; color:#fff; border:none; padding:8px; border-radius:8px; font-size:12px; font-weight:600; cursor:pointer;">
        📄 Bu İlana Özel Cover Letter Üret
      </button>
      <button id="cac-autofill-btn" style="background:#ca8a04; color:#fff; border:none; padding:8px; border-radius:8px; font-size:12px; font-weight:600; cursor:pointer;">
        ✍️ Form Alanlarını İncele
      </button>
    </div>

    <div id="cac-autofill-preview" style="display:none; margin:8px 0; padding:10px; background:#0f172a; border:1px solid #334155; border-radius:10px;">
      <div style="font-size:11px; color:#cbd5e1; margin-bottom:8px;">Doldurulacak alanları kontrol edip onayla. Dolu alanlar ve form gönderimi değiştirilmez.</div>
      <div id="cac-autofill-fields" style="display:grid; gap:6px;"></div>
      <button id="cac-autofill-confirm" style="display:none; width:100%; margin-top:8px; background:#15803d; color:white; border:0; border-radius:8px; padding:8px; cursor:pointer;">Seçili alanları doldur</button>
    </div>

    <!-- Cover Letter Preview Area -->
    <div id="cac-cl-container" style="display:none; margin-top:10px;">
      <div style="font-size:11px; font-weight:600; color:#cbd5e1; margin-bottom:4px;">Üretilen Niyet Mektubu:</div>
      <textarea id="cac-cl-text" style="width:100%; height:110px; background:#020617; border:1px solid #1e293b; color:#e2e8f0; font-size:11px; border-radius:8px; padding:6px; resize:none;"></textarea>
      <button id="cac-copy-btn" style="background:#334155; color:#fff; border:none; padding:6px; border-radius:6px; font-size:11px; width:100%; margin-top:4px; cursor:pointer;">
        📋 Panoya Kopyala
      </button>
    </div>

    <div id="cac-status" style="font-size:11px; color:#38bdf8; text-align:center; margin-top:8px;"></div>
  `;

  document.body.appendChild(launcher);
  document.body.appendChild(panel);

  // ===== EVENT HANDLERS =====
  launcher.onclick = () => {
    panel.style.display = "block";
    const job = extractPageJobDetails();
    document.getElementById("cac-job-title").innerText = job.title;
    document.getElementById("cac-job-company").innerText = job.company;
    document.getElementById("cac-job-location").innerText = job.location || job.portal;
  };

  document.getElementById("cac-close-btn").onclick = () => {
    panel.style.display = "none";
  };

  // Analyze Button
  document.getElementById("cac-analyze-btn").onclick = async () => {
    const job = extractPageJobDetails();
    const statusDiv = document.getElementById("cac-status");
    statusDiv.innerText = "FastAPI motoru ile analiz ediliyor...";

    const data = await apiPost("/scrape/analyze_on_the_fly", {
      title: job.title, company: job.company, description: job.description,
    });

    if (data) {
      document.getElementById("cac-ats-score").innerText = data.match_score == null ? "—" : `≈ %${Math.round(data.match_score)}`;
      document.getElementById("cac-ghost-score").innerText = data.ghost_score == null ? "—" : `%${Math.round(data.ghost_score)}`;
      statusDiv.innerText = "✓ Analiz tamamlandı!";
    } else {
      statusDiv.innerText = "Backend erişilemiyor veya oturum açılmamış.";
    }
  };

  // Track from panel
  document.getElementById("cac-track-panel-btn").onclick = async () => {
    const job = extractPageJobDetails();
    const btn = document.getElementById("cac-track-panel-btn");
    btn.innerText = "⏳ Kaydediliyor...";

    const result = await apiPost("/scrape/seen_jobs/add", {
      company: job.company, title: job.title, url: job.url,
      portal: job.portal, location: job.location,
    });

    if (result) {
      btn.innerText = result.is_new ? "✅ Takibe Alındı" : "📌 Zaten Takipte";
      btn.disabled = true;
      btn.style.background = "#334155";
      document.getElementById("cac-track-status").innerText = "✅";
      document.getElementById("cac-track-status").style.color = "#34d399";
    } else {
      btn.innerText = "❌ Hata";
      setTimeout(() => { btn.innerText = "➕ Takip Et"; }, 2000);
    }
  };

  // Generate Cover Letter
  document.getElementById("cac-generate-cl-btn").onclick = async () => {
    const job = extractPageJobDetails();
    const statusDiv = document.getElementById("cac-status");
    statusDiv.innerText = "Yapay zeka ile insansı mektup üretiliyor...";

    const data = await apiPost("/llm/generate", {
      system_prompt: "You are an anti-AI humanized job application generator. Write a 3-paragraph compelling cover letter.",
      user_prompt: `Apply for role: ${job.title} at ${job.company}. Job description: ${job.description.slice(0, 500)}`,
    });

    // A provider failure returns a stock template; it must not be shown as a generated letter.
    if (data && data.text && !data.is_template_fallback) {
      document.getElementById("cac-cl-container").style.display = "block";
      document.getElementById("cac-cl-text").value = data.text;
      statusDiv.innerText = `✓ Üretildi (İnsansı Doku: %${data.human_texture_score})`;
    } else {
      statusDiv.innerText = "Hata: Mektup üretilemedi.";
    }
  };

  // Copy Button
  document.getElementById("cac-copy-btn").onclick = () => {
    const text = document.getElementById("cac-cl-text").value;
    navigator.clipboard.writeText(text);
    document.getElementById("cac-status").innerText = "✓ Panoya kopyalandı!";
  };

  // Suggest, preview and explicitly confirm safe autofill. Never submit a form.
  document.getElementById("cac-autofill-btn").onclick = async () => {
    const statusDiv = document.getElementById("cac-status");
    statusDiv.innerText = "Aday profili çekiliyor...";

    const data = await apiGet("/setup/profile");
    if (!data || !data.profile) {
      statusDiv.innerText = "Profil alınamadı.";
      return;
    }
    const profile = data.profile;
    const normalize = (value) => (value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    const fullName = (profile.full_name || "").trim().split(/\s+/).filter(Boolean);
    const fields = [
      { key: "first_name", label: "Ad", value: fullName[0] || "", matches: ["firstname", "givenname", "vorname", "forename"] },
      { key: "last_name", label: "Soyad", value: fullName.length > 1 ? fullName.slice(1).join(" ") : "", matches: ["lastname", "familyname", "surname", "nachname"] },
      { key: "full_name", label: "Ad soyad", value: profile.full_name || "", matches: ["fullname", "name", "applicantname", "candidate"] },
      { key: "email", label: "E-posta", value: profile.email || "", matches: ["email", "mail"] },
      { key: "phone", label: "Telefon", value: profile.phone || "", matches: ["phone", "mobile", "telephone", "tel"] },
      { key: "location", label: "Konum", value: profile.location || "", matches: ["city", "location", "addresscity", "wohnort"] },
      { key: "linkedin", label: "LinkedIn", value: profile.linkedin_url || "", matches: ["linkedin"] },
      { key: "website", label: "GitHub / Portföy", value: profile.github_url || profile.portfolio_url || "", matches: ["github", "portfolio", "website", "personalurl"] },
    ].filter((field) => field.value);

    const candidates = [...document.querySelectorAll("input:not([type]), input[type='text'], input[type='email'], input[type='tel'], input[type='url'], textarea")]
      .filter((input) => !input.disabled && !input.readOnly && input.getClientRects().length && !input.value.trim());
    const proposed = [];
    for (const input of candidates) {
      const labelText = input.labels ? [...input.labels].map((label) => label.innerText).join(" ") : "";
      const descriptor = normalize([input.name, input.id, input.getAttribute("autocomplete"), input.placeholder, input.getAttribute("aria-label"), labelText].join(" "));
      if (!descriptor || /password|resume|upload|file|coverletter|message|question|search|jobtitle/.test(descriptor)) continue;
      const exact = fields.find((field) => field.matches.some((hint) => descriptor.includes(normalize(hint))));
      if (!exact) continue;
      if (exact.key === "full_name" && /first|given|vorname|forename|last|family|surname|nachname/.test(descriptor)) continue;
      if ((exact.key === "first_name" || exact.key === "last_name") && !/first|given|vorname|forename|last|family|surname|nachname/.test(descriptor)) continue;
      proposed.push({ input, value: exact.value, label: exact.label });
    }

    const preview = document.getElementById("cac-autofill-preview");
    const fieldsContainer = document.getElementById("cac-autofill-fields");
    const confirmButton = document.getElementById("cac-autofill-confirm");
    fieldsContainer.replaceChildren();
    preview.style.display = "block";
    confirmButton.style.display = proposed.length ? "block" : "none";
    if (!proposed.length) {
      statusDiv.innerText = "Boş ve güvenle eşleştirilebilen bir form alanı bulunamadı.";
      return;
    }

    proposed.forEach((item, index) => {
      const row = document.createElement("label");
      row.style.cssText = "display:flex; gap:7px; align-items:flex-start; font-size:11px; color:#e2e8f0; overflow-wrap:anywhere;";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = true;
      checkbox.dataset.index = String(index);
      const detail = document.createElement("span");
      const descriptor = item.input.getAttribute("aria-label") || item.input.labels?.[0]?.innerText || item.input.name || item.input.id || item.label;
      detail.textContent = `${item.label} → ${descriptor}: ${item.value}`;
      row.append(checkbox, detail);
      fieldsContainer.appendChild(row);
    });
    statusDiv.innerText = `${proposed.length} boş alan eşleştirildi. Doldurmadan önce kontrol et.`;

    confirmButton.onclick = () => {
      let filled = 0;
      fieldsContainer.querySelectorAll("input[type='checkbox']:checked").forEach((checkbox) => {
        const item = proposed[Number(checkbox.dataset.index)];
        if (!item || !item.input.isConnected || item.input.disabled || item.input.readOnly || item.input.value.trim()) return;
        const prototype = item.input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
        if (setter) setter.call(item.input, item.value);
        else item.input.value = item.value;
        item.input.dispatchEvent(new Event("input", { bubbles: true }));
        item.input.dispatchEvent(new Event("change", { bubbles: true }));
        filled++;
      });
      statusDiv.innerText = `${filled} seçili alan dolduruldu. Başvuruyu kontrol edip site üzerinden kendin gönder.`;
      preview.style.display = "none";
    };
  };

  // ===== AUTO-INJECT ON PAGE LOAD =====
  function initEnhancements() {
    setTimeout(() => {
      injectTrackButton();
      injectSalaryTooltip();
      // ATS badge and ghost check are async — run in background
      injectATSBadge().catch(() => {});
      checkGhostJob().catch(() => {});
    }, 2000);
  }

  // Run on load
  initEnhancements();

  // Re-run on LinkedIn SPA navigation (URL changes without full page load)
  let lastUrl = location.href;
  const observer = new MutationObserver(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      setTimeout(initEnhancements, 1500);
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();
