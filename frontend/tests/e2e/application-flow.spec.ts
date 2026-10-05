import { expect, test, type BrowserContext, type Route } from "@playwright/test";

const corsHeaders = {
  "access-control-allow-origin": "http://127.0.0.1:3000",
  "access-control-allow-credentials": "true",
  "access-control-allow-headers": "content-type, x-api-key, x-csrf-token",
  "access-control-allow-methods": "GET, POST, PUT, OPTIONS",
};

type Handler = (body: any, route: Route) => unknown;

// Mocks one API endpoint: answers the CORS preflight, then replies with the handler's JSON.
async function mockApi(context: BrowserContext, pattern: string, handler: Handler) {
  await context.route(pattern, async (route) => {
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: corsHeaders });
      return;
    }
    const body = route.request().method() === "GET" ? null : route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      headers: corsHeaders,
      contentType: "application/json",
      body: JSON.stringify(await handler(body, route)),
    });
  });
}

test.describe("Human-in-the-loop application flow", () => {
  test("kanban: generated package is approved, then the portal submission is confirmed separately", async ({ page }) => {
    const job = { id: "job-1", title: "Backend Engineer", company: "Acme Labs", match_score: 88, url: "https://example.test/jobs/1" };
    let stage = "Draft";
    const statusUpdates: any[] = [];
    const confirmations: any[] = [];

    await mockApi(page.context(), "**/api/outcome/kanban*", () => ({ [stage]: [{ ...job, status: stage }] }));
    await mockApi(page.context(), "**/api/outcome/status-history/**", () => ({ history: [] }));
    await mockApi(page.context(), "**/api/apply/generate_package", (body) => {
      expect(body.job_id).toBe("job-1");
      stage = "Human Review";
      return { job_id: "job-1", title: job.title, company: job.company, cover_letter: "I built the billing API at my last job.", human_texture_score: 91 };
    });
    await mockApi(page.context(), "**/api/outcome/update_status", (body) => {
      statusUpdates.push(body);
      stage = body.new_status;
      return { status: "ok" };
    });
    await mockApi(page.context(), "**/api/outcome/confirm_submission", (body) => {
      confirmations.push(body);
      return { status: "confirmed" };
    });

    await page.goto("/kanban");
    await expect(page.getByText("Backend Engineer")).toBeVisible();
    await page.getByRole("button", { name: "Apply Paketi Üret", exact: true }).click();

    // The draft opens for human review before anything is marked as applied.
    await expect(page.getByText("I built the billing API at my last job.")).toBeVisible();
    expect(statusUpdates).toEqual([]);
    await page.getByRole("button", { name: /İnsansı Doku Onaylandı & Başvur/ }).click();

    // Moving the card to Applied is not a verified submission yet.
    await expect(page.getByText("Portal gönderimi doğrulansın mı?")).toBeVisible();
    expect(statusUpdates).toEqual([
      { job_id: "job-1", new_status: "Applied", final_cover_letter: "I built the billing API at my last job." },
    ]);
    expect(confirmations).toEqual([]);

    await page.getByRole("button", { name: "Portal gönderimini doğrula" }).click();
    await expect(page.getByText("Portal gönderimi doğrulansın mı?")).toHaveCount(0);
    expect(confirmations).toHaveLength(1);
    expect(confirmations[0]).toMatchObject({ job_id: "job-1", execution_mode: "live" });
  });

  test("kanban: declining the confirmation never records a live submission", async ({ page }) => {
    let stage = "Human Review";
    let confirmed = false;
    await mockApi(page.context(), "**/api/outcome/kanban*", () => ({
      [stage]: [{ id: "job-2", title: "Data Analyst", company: "Globex", cover_letter: "Draft letter.", status: stage }],
    }));
    await mockApi(page.context(), "**/api/outcome/status-history/**", () => ({ history: [] }));
    await mockApi(page.context(), "**/api/outcome/update_status", (body) => {
      stage = body.new_status;
      return { status: "ok" };
    });
    await mockApi(page.context(), "**/api/outcome/confirm_submission", () => {
      confirmed = true;
      return { status: "confirmed" };
    });

    await page.goto("/kanban");
    await page.getByRole("button", { name: "İncele & Onayla", exact: true }).click();
    await page.getByRole("button", { name: /İnsansı Doku Onaylandı & Başvur/ }).click();
    await expect(page.getByText("Portal gönderimi doğrulansın mı?")).toBeVisible();
    await page.getByRole("button", { name: "Henüz değil" }).click();

    await expect(page.getByText("Portal gönderimi doğrulansın mı?")).toHaveCount(0);
    expect(confirmed).toBe(false);
  });

  test("auto-apply: a draft needs approval, a submit step and an explicit confirmation", async ({ page }) => {
    const item: Record<string, unknown> = {
      job_key: "acme-backend",
      title: "Platform Engineer",
      company: "Acme Labs",
      location: "Remote",
      match_score: 84,
      prepared_at: "2026-10-01T09:00:00Z",
      status: "pending_approval",
      draft_result: { cover_letter: "Tailored letter.", cv: {}, review: {} },
    };
    const calls: string[] = [];
    let todayApplied = 0;
    const step = (name: string, nextStatus: string | null) => (body: any) => {
      expect(body.job_key).toBe("acme-backend");
      calls.push(name);
      if (nextStatus) item.status = nextStatus;
      else todayApplied = 1;
      return { status: "ok", handoff_required: false };
    };

    await mockApi(page.context(), "**/api/apply/auto/queue*", () => ({
      queue: todayApplied ? [] : [item],
      today_applied_count: todayApplied,
    }));
    await mockApi(page.context(), "**/api/apply/auto/approve", step("approve", "approved"));
    await mockApi(page.context(), "**/api/apply/auto/submit", step("submit", "awaiting_user_submission"));
    await mockApi(page.context(), "**/api/apply/auto/confirm-submission", step("confirm", null));
    page.on("dialog", (dialog) => dialog.accept());

    await page.goto("/auto-apply");
    await expect(page.getByText("Platform Engineer")).toBeVisible();
    await expect(page.getByText("0 / 5 Günlük Limit")).toBeVisible();

    await page.getByRole("button", { name: "Taslağı Onayla" }).click();
    await expect(page.getByText("Bu sekmede başvuru bulunmuyor.")).toBeVisible();

    await page.getByRole("button", { name: /^Onaylanan \(/ }).click();
    await page.getByRole("button", { name: "Başvuru adımına geç" }).click();
    // Starting the browser step alone must not count as an application.
    await expect(page.getByRole("button", { name: "Gönderimi yaptım" })).toBeVisible();
    await expect(page.getByText("0 / 5 Günlük Limit")).toBeVisible();

    await page.getByRole("button", { name: "Gönderimi yaptım" }).click();
    await expect(page.getByText("1 / 5 Günlük Limit")).toBeVisible();
    expect(calls).toEqual(["approve", "submit", "confirm"]);
  });

  test("sources: every portal from the product spec can be configured (live backend)", async ({ page }) => {
    await page.goto("/sources");
    for (const portal of [
      "LinkedIn", "Upwork", "KosovaJob", "Fiverr", "Freelancer.com", "Toptal",
      "GjirafaWork", "Kariyer.net", "Indeed", "Glassdoor", "Wellfound",
    ]) {
      await expect(page.getByRole("heading", { name: portal, exact: true })).toBeVisible();
    }
  });
});
