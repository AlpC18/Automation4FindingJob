import { expect, test } from "@playwright/test";

test.describe("Career Agent critical navigation", () => {
  test("loads the CV analysis workflow", async ({ page }) => {
    await page.goto("/cv-analysis");
    await expect(page).toHaveTitle(/Career|Autonomous/i);
    await expect(page.getByText("CV'ni analiz et ve geliştir")).toBeVisible();
    await expect(page.getByText("CV yükle ve analiz et")).toBeVisible();
  });

  test("loads the live jobs workspace without demo-only failure UI", async ({ page }) => {
    await page.goto("/jobs");
    await expect(page.getByText("İş ilanları").first()).toBeVisible();
    await expect(page.getByText("Demo ilanı")).toHaveCount(0);
  });

  test("loads analytics and profile version surface", async ({ page }) => {
    await page.goto("/analytics");
    await expect(page.getByText("Gerçek başvuru analitiği")).toBeVisible();
    await expect(page.getByText("Profil sürüm geçmişi")).toBeVisible();
  });

  test("requires a session in multi-tenant mode and opens the app after login", async ({ page }) => {
    const corsHeaders = {
      "access-control-allow-origin": "http://127.0.0.1:3000",
      "access-control-allow-credentials": "true",
      "access-control-allow-headers": "content-type",
      "access-control-allow-methods": "GET, POST, OPTIONS",
    };
    await page.route("**/auth/mode", (route) => route.fulfill({
      status: 200,
      headers: corsHeaders,
      contentType: "application/json",
      body: JSON.stringify({ authentication_required: true }),
    }));
    await page.route("**/auth/me", (route) => route.fulfill({
      status: 401,
      headers: corsHeaders,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Valid account session required." }),
    }));
    await page.route("**/auth/login", async (route) => {
      if (route.request().method() === "OPTIONS") {
        await route.fulfill({ status: 204, headers: corsHeaders });
        return;
      }
      expect(route.request().postDataJSON()).toEqual({ email: "candidate@example.test", password: "correct-horse-battery" });
      await route.fulfill({
        status: 200,
        headers: corsHeaders,
        contentType: "application/json",
        body: JSON.stringify({ user: { id: "candidate-1", email: "candidate@example.test" }, csrf_token: "csrf-test-token" }),
      });
    });

    await page.goto("/jobs");
    await expect(page.getByText("Profilinize özel güvenli oturum açın.")).toBeVisible();
    await expect(page.getByRole("heading", { name: "1.2 & 1.3 Çoklu Platform İlan Akışı & Algoritmik Eşleşme" })).toHaveCount(0);
    await page.getByLabel("E-posta").fill("candidate@example.test");
    await page.getByLabel("Parola").fill("correct-horse-battery");
    await page.getByRole("button", { name: "Giriş yap" }).click();
    await expect(page.getByRole("heading", { name: "1.2 & 1.3 Çoklu Platform İlan Akışı & Algoritmik Eşleşme" })).toBeVisible();
  });

  test("lets the candidate opt in to personal follow-up emails", async ({ page }) => {
    const corsHeaders = {
      "access-control-allow-origin": "http://127.0.0.1:3000",
      "access-control-allow-credentials": "true",
      "access-control-allow-headers": "content-type",
      "access-control-allow-methods": "GET, PUT, OPTIONS",
    };
    await page.route("**/setup/profile", (route) => route.fulfill({
      status: 200,
      headers: corsHeaders,
      contentType: "application/json",
      body: JSON.stringify({ profile: { email: "candidate@example.test", skills: [], target_roles: [], target_categories: [] } }),
    }));
    await page.route("**/setup/notification-preferences", async (route) => {
      if (route.request().method() === "OPTIONS") {
        await route.fulfill({ status: 204, headers: corsHeaders });
        return;
      }
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          headers: corsHeaders,
          contentType: "application/json",
          body: JSON.stringify({ follow_up_email_reminders: false, smtp_configured: true, recipient_configured: true }),
        });
        return;
      }
      expect(route.request().postDataJSON()).toEqual({ enabled: true });
      await route.fulfill({
        status: 200,
        headers: corsHeaders,
        contentType: "application/json",
        body: JSON.stringify({ follow_up_email_reminders: true, smtp_configured: true, recipient_configured: true }),
      });
    });

    await page.goto("/preferences");
    const emailOptIn = page.getByRole("checkbox", { name: /Başvuru takip zamanı geldiğinde bana e-posta gönder/ });
    await expect(emailOptIn).toBeEnabled();
    await expect(emailOptIn).not.toBeChecked();
    await emailOptIn.click();
    await expect(emailOptIn).toBeChecked();
    await expect(page.getByText("E-posta takip hatırlatmaları açıldı.")).toBeVisible();
    await expect(page.getByText("E-posta yalnızca sana gelir; hiçbir başvuru veya takip mesajı işverene otomatik gönderilmez.")).toBeVisible();
  });

  test("tracks a queued scrape until the worker returns its result", async ({ page }) => {
    const corsHeaders = {
      "access-control-allow-origin": "http://127.0.0.1:3000",
      "access-control-allow-credentials": "true",
      "access-control-allow-headers": "content-type",
      "access-control-allow-methods": "GET, POST, OPTIONS",
    };
    const jsonApi = (body: unknown) => async (route: import("@playwright/test").Route) => {
      if (route.request().method() === "OPTIONS") {
        await route.fulfill({ status: 204, headers: corsHeaders });
        return;
      }
      await route.fulfill({
        status: 200,
        headers: corsHeaders,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    };
    await page.context().route("**/api/setup/profile*", jsonApi({ profile: { full_name: "", skills: [], target_roles: [], target_categories: [] } }));
    await page.context().route("**/api/scrape/apify-quota*", jsonApi({
      used_usd: 0, budget_usd: 0, remaining_usd: 0, valid_keys: 0, configured_keys: 0, invalid_keys: 0,
    }));
    await page.context().route("**/api/setup/discovered_roles*", jsonApi({
        roles: [{ id: "backend-role", title: "Backend Engineer", default_checked: true }],
        location_presets: [{ id: "remote", title: "Remote", location_filter: "Remote", remote_filter: "Remote" }],
    }));
    await page.context().route("**/api/scrape/jobs*", jsonApi({ jobs: [] }));
    await page.context().route("**/api/scrape/saved-searches*", jsonApi({ searches: [] }));
    await page.context().route("**/api/scrape/runs*", jsonApi({ runs: [] }));
    await page.route("**/scrape/run", (route) => {
      if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: corsHeaders });
      return route.fulfill({
        status: 200,
        headers: corsHeaders,
        contentType: "application/json",
        body: JSON.stringify({ dispatch_mode: "CELERY_REDIS", status: "QUEUED", job_id: "scan-job-1" }),
      });
    });
    let polls = 0;
    await page.context().route("**/tasks/jobs/**", (route) => {
      if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: corsHeaders });
      polls += 1;
      return route.fulfill({
        status: 200,
        headers: corsHeaders,
        contentType: "application/json",
        body: JSON.stringify({ job: polls === 1
          ? { status: "queued", result: null }
          : { status: "succeeded", result: { current_total: 3, total_scraped: 3, newly_saved_count: 3, errors: [] } } }),
      });
    });
    await page.route("**/rank/evaluate_all", (route) => {
      if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: corsHeaders });
      return route.fulfill({
        status: 200,
        headers: corsHeaders,
        contentType: "application/json",
        body: JSON.stringify({ processed_count: 3 }),
      });
    });

    await page.goto("/jobs");
    await page.getByRole("button", { name: /Tarama başlat/ }).click();
    await expect(page.getByText(/Tarama tamamlandı/)).toBeVisible({ timeout: 10_000 });
    expect(polls).toBeGreaterThanOrEqual(2);
  });

  test("extension autofill previews profile values and never submits the external form", async ({ page }) => {
    await page.setContent(`
      <form id="application-form">
        <label for="first_name">First Name</label><input id="first_name" name="first_name">
        <label for="email">Email address</label><input id="email" name="email" type="email">
        <button type="submit">Submit application</button>
      </form>
      <script>document.querySelector("form").addEventListener("submit", (event) => { event.preventDefault(); window.__submitted = true; });</script>
    `);
    await page.evaluate(() => {
      Object.defineProperty(window, "chrome", { configurable: true, value: {
        runtime: {
          sendMessage: async (message: { method?: string; endpoint?: string }) => {
            if (message.method === "GET" && message.endpoint === "/setup/profile") {
              return { ok: true, data: { profile: { full_name: "Taylor Candidate", email: "taylor@example.test" } } };
            }
            return { ok: true, data: { match_score: 82, ghost_score: 8, is_new: true } };
          },
        },
      } });
    });
    await page.addScriptTag({ path: "../extension/content.js" });

    await page.locator("#career-agent-launcher").click();
    await page.locator("#cac-autofill-btn").click();
    await expect(page.getByText("2 boş alan eşleştirildi. Doldurmadan önce kontrol et.")).toBeVisible();
    await expect(page.locator("#first_name")).toHaveValue("");
    await expect(page.locator("#email")).toHaveValue("");

    await page.locator("#cac-autofill-confirm").click();
    await expect(page.locator("#first_name")).toHaveValue("Taylor");
    await expect(page.locator("#email")).toHaveValue("taylor@example.test");
    expect(await page.evaluate(() => (window as any).__submitted || false)).toBe(false);
  });
});
