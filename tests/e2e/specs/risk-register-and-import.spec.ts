/**
 * Milestone 1 end-to-end smoke test (docs/architecture/milestone-1-plan.md):
 * "create a risk, see it in the list" and "import a fixture file end-to-end".
 *
 * Requires the full stack running locally: apps/api on :8000, apps/web on
 * :3000, and apps/worker polling the background_jobs table — see
 * docker-compose.yml, or run each service directly for local development.
 */
import { expect, test } from "@playwright/test";
import path from "node:path";

const FIXTURE_PATH = path.resolve(
  __dirname,
  "../../../database/seed/fixtures/risk_register_fixture.xlsx",
);

test.describe.serial("Risk Register + Import Wizard golden path", () => {
  test("sign in, create a risk, and see it in the list", async ({ page }) => {
    await page.goto("/");
    await page.selectOption("select", "risk.manager@example.com");
    await page.click("button:has-text('Sign in')");
    await page.waitForURL("**/risks");
    await expect(page.locator("h1")).toHaveText("Risk Register");

    await page.click("text=New risk");
    await page.waitForURL("**/risks/new");
    await page.fill("input", "Playwright smoke test risk");
    await page.click("button:has-text('Create risk')");
    await page.waitForURL(/\/risks\/[0-9a-f-]+$/);
    await expect(page.locator("h1")).toHaveText("Playwright smoke test risk");

    await page.click("text=Risk Register");
    await page.waitForURL("**/risks");
    await expect(page.getByText("Playwright smoke test risk")).toBeVisible();
  });

  test("import the fixture spreadsheet end-to-end", async ({ page }) => {
    await page.goto("/");
    await page.selectOption("select", "risk.manager@example.com");
    await page.click("button:has-text('Sign in')");
    await page.waitForURL("**/risks");

    await page.click("text=Import Wizard");
    await page.waitForURL("**/imports");

    const [fileChooser] = await Promise.all([
      page.waitForEvent("filechooser"),
      page.click("input[type=file]"),
    ]);
    await fileChooser.setFiles(FIXTURE_PATH);
    await expect(page.getByText("Suggested mapping")).toBeVisible();

    await page.click("text=Confirm mapping and validate");
    await expect(page.getByText(/blocking error\(s\)/)).toBeVisible();
    await expect(page.getByText("0 blocking error(s)")).toBeVisible();

    await page.click("text=Preview rows");
    await expect(page.getByText(/Showing .* of .* rows/)).toBeVisible();

    await page.click("text=Commit import");
    await expect(page.getByText("Import committed successfully")).toBeVisible({
      timeout: 15_000,
    });
  });
});
