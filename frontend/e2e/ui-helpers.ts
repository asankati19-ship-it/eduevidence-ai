import { expect, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const MODE = process.env.EDUEVIDENCE_UI_MODE ?? 'fixture';
export const SAMPLE = fileURLToPath(new URL('../../data/sample_documents/Python Programming Course Handbook.pdf', import.meta.url));
export const captureDirectory = process.env.EDUEVIDENCE_CAPTURE_DIR;

export async function capture(page: Page, name: string, fullPage = false) {
  if (!captureDirectory) return;
  await mkdir(captureDirectory, { recursive: true });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: join(captureDirectory, name + '.png'), animations: 'disabled', fullPage });
}

export async function open(page: Page, name: string) {
  const mainNav = page.getByRole('navigation', { name: 'Workspace navigation' });
  const toggle = page.getByRole('button', { name: 'Open navigation' });
  if (await toggle.isVisible()) await toggle.click();
  await mainNav.getByRole('link', { name, exact: true }).click();
  await expect(page.getByRole('heading', { level: 1, name, exact: true })).toBeVisible();
}

export async function noOverflow(page: Page) {
  const layout = await page.evaluate(() => ({
    width: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
    tableClipped: [...document.querySelectorAll('.table-scroll')].some((table) => table.scrollWidth > table.clientWidth + 1),
  }));
  expect(layout.content).toBeLessThanOrEqual(layout.width + 1);
  expect(layout.tableClipped).toBe(false);
}

