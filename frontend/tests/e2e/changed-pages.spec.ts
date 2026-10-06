import { expect, test } from "@playwright/test";

// These run against the live backend, like the "(live backend)" tests in the other files.
test.describe("Pages changed by the review fixes (live backend)", () => {
  test("English is downloaded only when it is chosen, and then translates the menu", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("navigation", { name: "Ana menü" }).getByRole("link", { name: "İş ilanları" })).toBeVisible();

    await page.getByLabel("Dil").selectOption("en");

    await expect(page.getByRole("link", { name: "Job listings" }).first()).toBeVisible();
    await page.reload();
    await expect(page.getByRole("link", { name: "Job listings" }).first()).toBeVisible();
  });

  test("the AI page no longer has a model-router tab and system status has no test centre", async ({ page }) => {
    await page.goto("/llm");
    await expect(page.getByText("API anahtarı güvenliği")).toBeVisible();
    await expect(page.getByText("Model yönlendirici")).toHaveCount(0);

    await page.goto("/system-status");
    await expect(page.getByRole("region", { name: "Hangi özellikler çalışıyor?" })).toBeVisible();
    await expect(page.getByText("Test merkezi")).toHaveCount(0);

    expect((await page.goto("/llm-router"))?.status()).toBe(404);
    expect((await page.goto("/testsprite"))?.status()).toBe(404);
  });

  test("the career map invents nothing for an empty profile", async ({ page }) => {
    await page.goto("/career-map");
    await expect(page.getByText("Önce yönünü belirleyelim")).toBeVisible();
    await expect(page.getByText(/\/100/)).toHaveCount(0);
    await expect(page.getByText("Autonomous Agent Systems Architect")).toHaveCount(0);
  });

  test("the dashboard shows feed totals from the server", async ({ page }) => {
    const feed = page.waitForResponse((response) => response.url().includes("/api/scrape/jobs?include_history=false&limit=5"));
    await page.goto("/");
    const body = await (await feed).json();
    expect(body).toHaveProperty("current_feed_total");
    expect(body).toHaveProperty("ghost_total");
    expect(body.jobs.length).toBeLessThanOrEqual(5);
  });
});
