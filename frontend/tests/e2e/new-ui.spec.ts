import { expect, test, type BrowserContext, type Page } from "@playwright/test";

const origin = new URL(process.env.E2E_BASE_URL || "http://127.0.0.1:3000").origin;
const corsHeaders = {
  "access-control-allow-origin": origin,
  "access-control-allow-credentials": "true",
  "access-control-allow-headers": "content-type, x-api-key, x-csrf-token",
  "access-control-allow-methods": "GET, POST, OPTIONS",
};

async function mockGet(context: BrowserContext, pattern: string, body: unknown) {
  await context.route(pattern, async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: corsHeaders });
    return route.fulfill({ status: 200, headers: corsHeaders, contentType: "application/json", body: JSON.stringify(body) });
  });
}

const locationPresets = [
  { id: "remote_global", title: "Remote · Worldwide", location_filter: "", remote_filter: "Remote" },
  { id: "remote_germany", title: "Germany · Remote", location_filter: "Germany", remote_filter: "Remote" },
];

// Mocks everything the jobs page loads; roles decide whether a scan can start.
async function mockJobsPage(page: Page, roles: unknown[]) {
  const context = page.context();
  await mockGet(context, "**/api/setup/profile*", { profile: { full_name: "", skills: [], target_roles: [], target_categories: [] } });
  await mockGet(context, "**/api/scrape/apify-quota*", { used_usd: 0, budget_usd: 0, remaining_usd: 0, valid_keys: 0, configured_keys: 0, invalid_keys: 0 });
  await mockGet(context, "**/api/setup/discovered_roles*", { roles, location_presets: locationPresets });
  await mockGet(context, "**/api/scrape/jobs*", { jobs: [] });
  await mockGet(context, "**/api/scrape/saved-searches*", { searches: [] });
  await mockGet(context, "**/api/scrape/runs*", { runs: [] });
  await mockGet(context, "**/api/llm/providers*", {
    effective_provider: "custom",
    providers: [
      { id: "custom", name: "Custom AI", model: "model-a", is_configured: true },
      { id: "openai", name: "OpenAI", model: "model-b", is_configured: true },
    ],
  });
}

test.describe("New UI: tabs, sidebar, jobs controls, toast", () => {
  // Single-user mode: no login screen in front of the pages under test.
  test.beforeEach(async ({ page }) => {
    await mockGet(page.context(), "**/auth/mode", { authentication_required: false });
  });

  test("cv-analysis tabs switch to the selected screen", async ({ page }) => {
    await page.goto("/cv-analysis");
    const tabs = page.getByRole("tablist");
    for (const name of ["CV'yi analiz et", "CV analiz haritası", "Profil optimizasyonu"]) {
      await expect(tabs.getByRole("tab", { name })).toBeVisible();
    }
    await expect(tabs.getByRole("tab", { name: "CV'yi analiz et" })).toHaveAttribute("aria-selected", "true");
    await tabs.getByRole("tab", { name: "CV analiz haritası" }).click();
    await expect(tabs.getByRole("tab", { name: "CV analiz haritası" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("heading", { name: "CV analiz haritası" })).toBeVisible();
  });

  test("sidebar: the collapsed 'Daha fazla' section opens and reveals Analitik", async ({ page }) => {
    await page.goto("/jobs");
    const nav = page.getByRole("navigation", { name: "Ana menü" }).first();
    const analytics = nav.getByRole("link", { name: "Analitik" });
    await expect(analytics).toBeHidden();
    await nav.getByText("Daha fazla", { exact: true }).click();
    await expect(analytics).toBeVisible();
  });

  test("jobs: location presets drive the scan request", async ({ page }) => {
    await mockJobsPage(page, [{ id: "backend-role", title: "Backend Engineer", default_checked: true }]);
    let sent: any = null;
    await page.context().route("**/api/scrape/run", async (route) => {
      if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: corsHeaders });
      sent = route.request().postDataJSON();
      return route.fulfill({ status: 200, headers: corsHeaders, contentType: "application/json", body: JSON.stringify({ status: "COMPLETED", current_total: 0, total_scraped: 0, newly_saved_count: 0, errors: [] }) });
    });
    await mockGet(page.context(), "**/api/rank/evaluate_all", { processed_count: 0 });

    await page.goto("/jobs");
    await expect(page.getByRole("button", { name: "Remote · Worldwide" })).toBeVisible();
    await page.getByRole("button", { name: "Germany · Remote" }).click();
    await expect(page.getByRole("button", { name: "Germany · Remote" })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: /Tarama başlat/ }).click();
    await expect.poll(() => sent).not.toBeNull();
    expect(sent).toMatchObject({ queries: ["Backend Engineer"], location_preference: "Germany", remote_type: "Remote" });
  });

  test("jobs: choosing another AI saves it as the provider", async ({ page }) => {
    await mockJobsPage(page, []);
    let sent: any = null;
    await page.context().route("**/api/llm/set_provider", async (route) => {
      if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: corsHeaders });
      sent = route.request().postDataJSON();
      return route.fulfill({ status: 200, headers: corsHeaders, contentType: "application/json", body: JSON.stringify({ status: "ok" }) });
    });

    await page.goto("/jobs");
    const select = page.getByLabel("Arama için yapay zekâ");
    await expect(select).toHaveValue("custom");
    await select.selectOption("openai");
    await expect.poll(() => sent?.provider).toBe("openai");
    await expect(select).toHaveValue("openai");
  });

  test("toast: notify() messages render in a role=status region instead of an alert dialog", async ({ page }) => {
    await mockJobsPage(page, [{ id: "backend-role", title: "Backend Engineer", default_checked: false }]);
    let dialogs = 0;
    page.on("dialog", (dialog) => { dialogs += 1; void dialog.dismiss(); });

    await page.goto("/jobs");
    // With no role selected the scan button is disabled, so the "Lütfen taranacak..." guard in
    // handleExecuteCustomSearch cannot be reached from the UI; fire the same event notify() sends.
    await expect(page.getByRole("button", { name: /Tarama başlat/ })).toBeDisabled();
    const message = "Lütfen taranacak en az bir rol veya ünvan seçiniz.";
    await page.evaluate((detail) => window.dispatchEvent(new CustomEvent("app-notify", { detail })), message);
    await expect(page.getByRole("status").filter({ hasText: message })).toBeVisible();
    await page.getByRole("button", { name: "Kapat" }).click();
    await expect(page.getByRole("status").filter({ hasText: message })).toHaveCount(0);
    expect(dialogs).toBe(0);
  });
});
