/**
 * Milestone 3 end-to-end smoke test: Controls, Actions, and Governance
 * Health render real seeded data, and a risk owner can link a control and
 * create an action from the risk detail page.
 */
import { expect, test } from "@playwright/test";

test.describe.serial("Controls, Actions, Governance Health", () => {
  test("controls and actions pages show seeded demo data", async ({ page }) => {
    await page.goto("/");
    await page.selectOption("select", "admin@example.com");
    await page.click("button:has-text('Sign in')");
    await page.waitForURL("**/dashboard");

    await page.click("text=Controls");
    await page.waitForURL("**/controls");
    await expect(page.getByText("CTRL-", { exact: false }).first()).toBeVisible();

    await page.click("text=Actions");
    await page.waitForURL("**/actions");
    await expect(page.getByText("ACT-", { exact: false }).first()).toBeVisible();

    await page.click("text=Governance");
    await page.waitForURL("**/governance");
    await expect(page.getByRole("heading", { name: "Governance Health" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Weak Controls" })).toBeVisible();
  });

  test("risk owner can link a control and add an action from risk detail", async ({ page }) => {
    await page.goto("/");
    await page.selectOption("select", "risk.owner@example.com");
    await page.click("button:has-text('Sign in')");
    await page.waitForURL("**/dashboard");

    await page.click("text=Risk Register");
    await page.waitForURL("**/risks");
    await page.locator("table a").first().click();
    await page.waitForURL(/\/risks\/[0-9a-f-]+$/);

    await expect(page.getByText("Controls")).toBeVisible();
    const controlSelect = page.locator("select").first();
    const optionCount = await controlSelect.locator("option").count();
    if (optionCount > 1) {
      await controlSelect.selectOption({ index: 1 });
      await page.click("button:has-text('Link')");
      await expect(page.getByText("Unlink").first()).toBeVisible();
    }

    const actionTitle = `Playwright action ${Date.now()}`;
    await page.fill("input[placeholder='New action title…']", actionTitle);
    await page.click("button:has-text('Add')");
    await expect(page.getByText(actionTitle)).toBeVisible();
  });
});
