import { expect, test, type BrowserContext } from "@playwright/test";

const corsHeaders = {
  "access-control-allow-origin": "http://127.0.0.1:3000",
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

test.describe("Connected career workflow", () => {
  test("home lists today's tasks in order and each one opens its step", async ({ page }) => {
    await mockGet(page.context(), "**/api/outcome/today*", {
      total: 9,
      actions: [
        { id: "inbox_reply:1", kind: "inbox_reply", href: "/inbox", title: "Interview invitation", company: "Ada Recruiter" },
        { id: "follow_up_due:j3", kind: "follow_up_due", href: "/follow-up", title: "Data Analyst", company: "Globex", days: 7 },
        { id: "approve_draft:j1", kind: "approve_draft", href: "/kanban", title: "Backend Engineer", company: "Acme Labs" },
        { id: "new_matches:feed", kind: "new_matches", href: "/jobs?scope=current&minMatch=70", title: "", company: "", count: 4 },
      ],
    });

    await page.goto("/");
    const tasks = page.getByRole("region", { name: "Bugünün işleri" }).getByRole("listitem");
    await expect(tasks).toHaveText([
      /E-postayı yanıtla.*Interview invitation — Ada Recruiter/,
      /Takip mesajı gönder \(7\. gün\).*Data Analyst — Globex/,
      /Taslağı incele ve onayla.*Backend Engineer — Acme Labs/,
      /4 yeni yüksek uyumlu ilanı incele/,
    ]);
    await expect(page.getByText("Toplam 9 iş bekliyor; en öncelikliler gösteriliyor.")).toBeVisible();

    await tasks.nth(2).getByRole("link").click();
    await expect(page).toHaveURL(/\/kanban$/);
  });

  test("home says so when nothing is pending (live backend)", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Bugün için bekleyen iş yok. Yeni ilan taraması başlatabilirsin.")).toBeVisible();
  });

  test("an interview-stage card links straight to that job's rehearsal", async ({ page }) => {
    await mockGet(page.context(), "**/api/outcome/kanban*", {
      Interview: [{
        id: "job-9", title: "Platform Engineer", company: "Umbrella", status: "Interview",
        next_steps: [
          { kind: "interview_sim", href: "/interview?job=job-9" },
          { kind: "star_prep", href: "/star-prep" },
        ],
      }],
    });
    let startedFor: string | null = null;
    await mockGet(page.context(), "**/api/scrape/jobs*", { jobs: [
      { id: "job-1", title: "Other Job", company: "Acme" },
      { id: "job-9", title: "Platform Engineer", company: "Umbrella" },
    ] });
    await page.context().route("**/api/interview/start", async (route) => {
      if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: corsHeaders });
      startedFor = route.request().postDataJSON().job_id;
      return route.fulfill({ status: 200, headers: corsHeaders, contentType: "application/json", body: JSON.stringify({ questions: [] }) });
    });

    await page.goto("/kanban");
    await expect(page.getByText("Sıradaki adım")).toBeVisible();
    await expect(page.getByRole("link", { name: "STAR yanıtlarını hazırla" })).toHaveAttribute("href", "/star-prep");
    await page.getByRole("link", { name: "Mülakat provası yap" }).click();

    await expect(page).toHaveURL(/\/interview\?job=job-9$/);
    await expect.poll(() => startedFor).toBe("job-9");
  });

  test("system status explains which features work and where to fix the rest (live backend)", async ({ page }) => {
    await page.goto("/system-status");
    const features = page.getByRole("region", { name: "Hangi özellikler çalışıyor?" });
    await expect(features.getByRole("listitem")).toHaveCount(7);
    for (const title of [
      "CV, niyet mektubu ve mülakat yapay zekâsı", "İlan taraması", "Takip ve tanışma e-postası gönderimi",
      "Gelen kutusu senkronizasyonu", "Karar verici bulma", "Tarayıcı otomasyonu için proxy",
      "Gece taraması ve sabah taslakları",
    ]) {
      await expect(features.getByText(title, { exact: true })).toBeVisible();
    }
    await expect(features.getByRole("link", { name: /Gelen kutusu senkronizasyonu/ })).toHaveAttribute("href", "/inbox");
    await expect(features.getByText("Gmail veya Outlook bağlı değil; yanıtlar otomatik işlenmez.")).toBeVisible();
  });

  test("weekly digest advice reflects recorded activity instead of canned text (live backend)", async ({ page }) => {
    await page.goto("/weekly-digest");
    await expect(page.getByText("Bu hafta yeni ilan taranmadı; tarama başlat veya otomasyon servisini aç.")).toBeVisible();
    await expect(page.getByText(/%24 artış/)).toHaveCount(0);
  });

  test("decision makers: Apollo search lists people and surfaces a missing key", async ({ page }) => {
    let reply: { status: number; body: unknown } = { status: 503, body: { detail: "Apollo API anahtarı ayarlı değil (APOLLO_API_KEY)." } };
    let sent: unknown = null;
    await page.context().route("**/api/decision-makers/search", async (route) => {
      if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: corsHeaders });
      sent = route.request().postDataJSON();
      return route.fulfill({ status: reply.status, headers: corsHeaders, contentType: "application/json", body: JSON.stringify(reply.body) });
    });

    await page.goto("/decision-makers");
    const search = page.getByRole("region", { name: "Apollo ile karar vericileri ara" });
    await search.getByLabel("Şirket alan adı").fill("acme.com");
    await search.getByRole("button", { name: "Karar vericileri ara" }).click();
    await expect(search.getByRole("alert")).toHaveText("Apollo API anahtarı ayarlı değil (APOLLO_API_KEY).");

    reply = { status: 200, body: { people: [
      { first_name: "Ada", last_name_obfuscated: "L***e", title: "Engineering Manager", company: "Acme", has_email: true },
    ] } };
    await search.getByRole("button", { name: "Karar vericileri ara" }).click();
    await expect(search.getByRole("listitem")).toHaveText(/Ada L\*\*\*e.*Engineering Manager — Acme/);
    await expect(search.getByRole("alert")).toHaveCount(0);
    expect(sent).toEqual({ company_domain: "acme.com", location: null });
  });

  test("kanban warns when a draft came from the template engine instead of AI", async ({ page }) => {
    await mockGet(page.context(), "**/api/outcome/kanban*", {
      "Human Review": [
        { id: "job-t", title: "Template Job", company: "Acme", cover_letter: "Hi there, generic text.", is_template_fallback: true },
        { id: "job-a", title: "AI Job", company: "Globex", cover_letter: "Specific letter.", is_template_fallback: false },
      ],
    });
    await mockGet(page.context(), "**/api/outcome/status-history/**", { history: [] });

    await page.goto("/kanban");
    await expect(page.getByText("Şablon metin · yapay zekâ yazmadı")).toHaveCount(1);
    await page.getByRole("button", { name: "İncele & Onayla", exact: true }).first().click();
    await expect(page.getByRole("alert").filter({ hasText: "Bu metni yapay zekâ yazmadı." })).toBeVisible();
  });

  test("home surfaces a closing deadline as a task", async ({ page }) => {
    await mockGet(page.context(), "**/api/outcome/today*", {
      total: 2,
      actions: [
        { id: "closing_soon:a", kind: "closing_soon", href: "/jobs?scope=current&minMatch=70", title: "Python Developer", company: "IMEE", days: 2 },
        { id: "closing_soon:b", kind: "closing_soon", href: "/jobs?scope=current&minMatch=70", title: "Data Engineer", company: "UpBizz", days: 0 },
      ],
    });
    await page.goto("/");
    await expect(page.getByRole("region", { name: "Bugünün işleri" }).getByRole("listitem")).toHaveText([
      /Son başvuruya 2 gün kaldı; başvur.*Python Developer — IMEE/,
      /Son başvuru günü bugün; başvur.*Data Engineer — UpBizz/,
    ]);
  });

  test("sources: a company career page can be added by URL, rejected when unknown, and removed", async ({ page }) => {
    let boards = [{ provider: "ashby", slug: "ramp", origin: "env" }];
    const posted: unknown[] = [];
    await page.context().route("**/api/scrape/company-boards**", async (route) => {
      const method = route.request().method();
      if (method === "OPTIONS") return route.fulfill({ status: 204, headers: { ...corsHeaders, "access-control-allow-methods": "GET, POST, DELETE, OPTIONS" } });
      const reply = (status: number, body: unknown) => route.fulfill({ status, headers: corsHeaders, contentType: "application/json", body: JSON.stringify(body) });
      if (method === "POST") {
        const body = route.request().postDataJSON();
        posted.push(body);
        if (String(body.board).includes("ghost")) return reply(422, { detail: "lever üzerinde 'ghost' adında bir kariyer sayfası bulunamadı." });
        boards = [...boards, { provider: "lever", slug: "spotify", origin: "saved" }];
        return reply(200, { boards, open_jobs: 12 });
      }
      if (method === "DELETE") {
        boards = boards.filter((board) => board.origin === "env");
        return reply(200, { boards });
      }
      return reply(200, { boards, providers: ["greenhouse", "lever", "ashby"] });
    });

    await page.goto("/sources");
    const section = page.getByRole("region", { name: "Takip edilen şirket kariyer sayfaları" });
    await expect(section.getByRole("listitem")).toHaveText([/ramp.*ashby.*\.env dosyasından/]);

    await section.getByLabel("Kariyer sayfası adresi").fill("https://jobs.lever.co/ghost");
    await section.getByRole("button", { name: "Şirket ekle" }).click();
    await expect(section.getByRole("alert")).toHaveText("lever üzerinde 'ghost' adında bir kariyer sayfası bulunamadı.");

    await section.getByLabel("Kariyer sayfası adresi").fill("https://jobs.lever.co/spotify");
    await section.getByRole("button", { name: "Şirket ekle" }).click();
    await expect(section.getByRole("status")).toHaveText("Eklendi; şu an 12 açık ilan listeliyor.");
    await expect(section.getByRole("listitem")).toHaveCount(2);
    expect(posted).toEqual([{ board: "https://jobs.lever.co/ghost" }, { board: "https://jobs.lever.co/spotify" }]);

    await section.getByRole("button", { name: "spotify şirketini kaldır" }).click();
    await expect(section.getByRole("listitem")).toHaveCount(1);
  });

  test("jobs: an AI review shows its verdict, strengths and gaps next to the rule score", async ({ page }) => {
    await mockGet(page.context(), "**/api/scrape/jobs*", { jobs: [{
      id: "job-ai", title: "Junior Backend Developer", company: "Acme", platform: "kosovajob", url: "https://example.test/j",
      location: "Prishtinë, Kosovo", remote_type: "Hybrid", description: "Node.js", status: "Draft", match_score: 84, match_tier: "High",
      ghost_score: 0, ghost_reasons: [], red_flags: [], skill_gaps: {}, salary_benchmark: {}, source_aliases: [],
      ai_review: { score: 84, verdict: "Projeleri role doğrudan uyuyor.", strengths: ["Node.js projeleri"], gaps: ["Profesyonel deneyim yok"], rule_score: 61.7 },
    }] });
    await page.goto("/jobs");
    await expect(page.getByText("Yapay zekâ değerlendirmesi · 84/100")).toBeVisible();
    await expect(page.getByText("Projeleri role doğrudan uyuyor.")).toBeVisible();
    await expect(page.getByText("✓ Node.js projeleri")).toBeVisible();
    await expect(page.getByText("Eksik: Profesyonel deneyim yok")).toBeVisible();
    await expect(page.getByText(/Kural tabanlı puan: 61.7/)).toBeVisible();
  });
});
