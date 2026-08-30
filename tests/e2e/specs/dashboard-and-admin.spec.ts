/**
 * Milestone 2 end-to-end smoke test: the Executive Dashboard renders real
 * aggregated data, and scoring-config administration is gated to
 * Administrators only (RBAC enforced in the UI, and independently on the
 * API per apps/api/tests/test_scoring_config_api.py).
 */
import { expect, test } from "@playwright/test";

test.describe.serial("Executive Dashboard + Scoring Config admin", () => {
  test("executive sees the dashboard populated with seeded risks", async ({ page }) => {
    await page.goto("/");
    await page.selectOption("select", "executive@example.com");
    await page.click("button:has-text('Sign in')");
    await page.waitForURL("**/dashboard");

    await expect(page.getByText("Executive Dashboard")).toBeVisible();
    await expect(page.getByText("TOTAL RISKS")).toBeVisible();
    await expect(page.getByText("5×5 Risk Heatmap (residual)")).toBeVisible();
    await expect(page.getByText("Top Risks Requiring Leadership Attention")).toBeVisible();

    // Executives don't get an Administration link.
    await expect(page.getByText("Administration")).toHaveCount(0);
  });

  test("administrator can publish a new scoring config version", async ({ page }) => {
    await page.goto("/");
    await page.selectOption("select", "admin@example.com");
    await page.click("button:has-text('Sign in')");
    await page.waitForURL("**/dashboard");

    await page.click("text=Administration");
    await page.waitForURL("**/admin/scoring-config");
    await expect(page.getByText("v1")).toBeVisible();

    await page.click("button:has-text('Publish new version')");
    await expect(page.getByText("v2")).toBeVisible({ timeout: 10_000 });
  });
});
