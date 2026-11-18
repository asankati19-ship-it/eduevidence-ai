import { expect, test, type Page } from '@playwright/test';
import { readFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SAMPLE = fileURLToPath(new URL('../../data/sample_documents/Python Programming Course Handbook.pdf', import.meta.url));
const QUESTION = 'What are the Python Programming course completion requirements?';
const captureDir = process.env.EDUEVIDENCE_CAPTURE_DIR;

async function capture(page: Page, name: string) {
  if (!captureDir) return;
  await mkdir(captureDir, { recursive: true });
  await page.screenshot({ path: join(captureDir, name + '.png'), animations: 'disabled', fullPage: true });
}

async function ask(page: Page, text = QUESTION) {
  await page.getByRole('textbox', { name: 'Your question' }).fill(text);
  await page.getByRole('button', { name: 'Send question' }).click();
}

test('overview reads database metrics and seven navigation destinations load', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible();
  await expect(page.getByText('3 indexed · 0 with errors')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Recent activity' })).toBeVisible();
  await capture(page, 'overview');
  const menu = page.getByRole('navigation', { name: 'Workspace navigation' });
  for (const name of ['Document Library', 'Knowledge Assistant', 'Question History', 'Feedback & Analytics', 'Audit Logs', 'System Health', 'Overview']) {
    await menu.getByRole('link', { name, exact: true }).click();
    await expect(page.getByRole('heading', { name, exact: true, level: 1 })).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test('document filtering and keyboard modal controls render the correct PDF page', async ({ page }) => {
  await page.goto('/documents');
  await page.getByRole('textbox', { name: 'Search documents' }).fill('Python');
  await expect(page.getByRole('row')).toHaveCount(2);
  const details = page.getByRole('button', { name: 'View details for Python Programming Course Handbook' });
  await details.focus();
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog', { name: 'Document details' });
  await expect(dialog.getByRole('img', { name: 'PDF page 1' })).toBeVisible();
  await dialog.getByRole('button', { name: 'Next PDF page' }).click();
  await expect(dialog.getByRole('img', { name: 'PDF page 2' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(details).toBeFocused();
  await page.getByRole('combobox', { name: 'Filter by course' }).selectOption('2');
  await expect(page.getByRole('heading', { name: 'No matching documents' })).toBeVisible();
  const nav = page.getByRole('navigation', { name: 'Workspace navigation' });
  await nav.getByRole('link', { name: 'Overview', exact: true }).click();
  await nav.getByRole('link', { name: 'Document Library', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Search documents' })).toHaveValue('Python');
  await expect(page.getByRole('combobox', { name: 'Filter by course' })).toHaveValue('2');
});

test('upload rejection, duplicate detection, indexing, reindex and confirmed removal', async ({ page }) => {
  await page.goto('/documents');
  await page.getByRole('button', { name: 'Upload PDF' }).click();
  const upload = page.getByRole('dialog', { name: 'Upload a course PDF' });
  const input = upload.getByLabel('PDF file');
  await upload.getByLabel('Course', { exact: true }).selectOption('1');
  await input.setInputFiles({ name: 'fake.pdf', mimeType: 'application/pdf', buffer: Buffer.from('not a PDF') });
  await upload.getByRole('button', { name: 'Upload and index' }).click();
  await expect(upload.getByRole('alert')).toContainText('valid PDF signature');
  await input.setInputFiles({ name: 'corrupt.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.7\nInvalid cross-reference and page data') });
  await upload.getByRole('button', { name: 'Upload and index' }).click();
  await expect(upload.getByRole('alert')).toContainText(/could not be read|damaged/);
  await input.setInputFiles(SAMPLE);
  await upload.getByRole('button', { name: 'Upload and index' }).click();
  await expect(upload.getByRole('alert')).toContainText('already in the library');
  const variant = Buffer.concat([await readFile(SAMPLE), Buffer.from('\n% Playwright upload variant\n')]);
  await input.setInputFiles({ name: 'upload-verification.pdf', mimeType: 'application/pdf', buffer: variant });
  await upload.getByLabel('Display title').fill('UI Upload Verification');
  await upload.getByRole('button', { name: 'Upload and index' }).click();
  const details = page.getByRole('dialog', { name: 'Document details' });
  await expect(details.getByRole('heading', { name: 'UI Upload Verification' })).toBeVisible();
  await expect(details.getByText('Indexed', { exact: true })).toBeVisible({ timeout: 10000 });
  const reindex = page.waitForResponse((response) => response.url().endsWith('/reindex') && response.status() === 202);
  await details.getByRole('button', { name: 'Reindex', exact: true }).click();
  await reindex;
  await expect(details.getByRole('button', { name: 'Reindex', exact: true })).toBeEnabled();
  await expect(details.locator('dl div').filter({ hasText: 'Index revision' })).toHaveText('Index revision1');
  await details.getByRole('button', { name: 'Remove', exact: true }).click();
  await details.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(details.getByRole('heading', { name: 'UI Upload Verification' })).toBeVisible();
  await details.getByRole('button', { name: 'Remove', exact: true }).click();
  await details.getByRole('button', { name: 'Confirm removal' }).click();
  await expect(details).toBeHidden();
  await page.getByRole('textbox', { name: 'Search documents' }).fill('UI Upload Verification');
  await expect(page.getByRole('heading', { name: 'No matching documents' })).toBeVisible();
});

test('offline fixture answer opens a real citation and PDF, persists feedback and survives reload', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('/assistant');
  await expect(page.getByText('Offline test fixture', { exact: true })).toBeVisible();
  await page.getByLabel('Course', { exact: true }).selectOption('1');
  await page.getByLabel('Document', { exact: true }).selectOption('1');
  await ask(page);
  await expect(page.getByText('Answered', { exact: true })).toBeVisible();
  await expect(page.locator('.answer-body')).toContainText('at least 70% overall');
  await capture(page, 'assistant-offline-fixture');
  await page.getByRole('button', { name: /Python Programming Course Handbook Page 4 · Chunk/ }).click();
  const evidence = page.getByRole('dialog', { name: 'Source evidence' });
  await expect(evidence.getByRole('img', { name: 'PDF page 4' })).toBeVisible();
  await expect(evidence.locator('blockquote')).toContainText('all four graded labs');
  await capture(page, 'citation-offline-fixture');
  await evidence.getByRole('button', { name: 'Close dialog' }).click();
  await page.getByRole('button', { name: 'Copy answer' }).click();
  await expect(page.getByText('Answer copied.')).toBeVisible();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toContain('Python Programming Course Handbook.pdf — Page 4');
  await page.getByRole('button', { name: 'Helpful', exact: true }).click();
  await expect(page.getByText('Feedback saved.')).toBeVisible();
  await page.reload();
  await expect(page.getByText(QUESTION, { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Helpful', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('link', { name: 'Question History', exact: true }).click();
  await page.getByRole('button', { name: 'View trace for ' + QUESTION }).click();
  await expect(page.getByRole('dialog', { name: 'Question trace' })).toBeVisible();
  await page.getByRole('link', { name: 'View correlated audit events' }).click();
  await expect(page.getByRole('heading', { name: 'Audit Logs', exact: true })).toBeVisible();
  await expect(page.getByRole('row')).toHaveCount(5);
});

test('unsupported question abstains and is filterable in persisted history', async ({ page }) => {
  await page.goto('/assistant');
  await page.getByLabel('Course', { exact: true }).selectOption('1');
  await ask(page, 'What is the cafeteria menu on Tuesday?');
  await expect(page.getByText('Abstained', { exact: true })).toBeVisible();
  await expect(page.getByText('The selected documents do not contain enough matching evidence for this question.')).toBeVisible();
  await expect(page.getByRole('region', { name: 'Verified citations' })).toHaveCount(0);
  await page.getByRole('link', { name: 'Question History', exact: true }).click();
  await page.getByRole('combobox', { name: 'Filter by question outcome' }).selectOption('abstained');
  await expect(page.getByText('What is the cafeteria menu on Tuesday?', { exact: true })).toBeVisible();
});

test('recoverable provider failure can be retried with the same scope and recorded as a new turn', async ({ page }) => {
  await page.goto('/assistant');
  await page.getByLabel('Course', { exact: true }).selectOption('1');
  await page.getByLabel('Document', { exact: true }).selectOption('1');
  await ask(page, 'What are the Python Programming course completion requirements for learners in the handbook?');
  await expect(page.getByText('API timeout', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Retry question' }).click();
  await expect(page.getByText('Answered', { exact: true })).toBeVisible();
  await expect(page.getByText('API timeout', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /Python Programming Course Handbook Page 4/ })).toBeVisible();
});

test('mobile drawer and assistant fit a narrow viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByText('3 indexed · 0 with errors')).toBeVisible();
  await capture(page, 'overview-mobile');
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await page.getByRole('link', { name: 'Knowledge Assistant', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Knowledge Assistant' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await expect(page.getByRole('textbox', { name: 'Your question' })).toBeVisible();
});

