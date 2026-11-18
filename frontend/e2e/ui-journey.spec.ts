import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { Document, Overview, Question, SystemStatus } from '../src/types';
import { MODE, SAMPLE, capture, captureDirectory, open } from './ui-helpers';

test('full journey uploads a PDF, answers from its page, saves feedback and verifies SQLite metrics after refresh', async ({ page }) => {
  test.skip(!['fixture', 'live'].includes(MODE));
  test.setTimeout(85000);
  const label = MODE === 'live' ? 'live' : 'fixture';
  const title = 'Full Journey Python Handbook';
  const filename = 'full-journey-course-handbook.pdf';
  const question = 'For this uploaded Python Programming handbook, what are the course completion requirements?';
  await page.goto('/');
  const system = await (await page.request.get('/api/system/status')).json() as SystemStatus;
  expect(system.provider.name).toBe(MODE === 'live' ? 'openai' : 'offline_fixture');
  expect(system.provider.configured).toBe(true);
  const before = await (await page.request.get('/api/analytics/overview')).json() as Overview;
  await open(page, 'Document Library');
  await page.getByRole('button', { name: 'Upload PDF', exact: true }).click();
  const form = page.getByRole('dialog', { name: 'Upload a course PDF' });
  await form.getByLabel('Course', { exact: true }).selectOption('1');
  await form.getByLabel('Display title').fill(title);
  await form.getByLabel('PDF file').setInputFiles({
    name: filename, mimeType: 'application/pdf',
    buffer: Buffer.concat([await readFile(SAMPLE), Buffer.from('\n% Original sample used for the full UI journey\n')]),
  });
  const submitted = page.waitForResponse((response) => response.url().endsWith('/api/documents/upload') && response.request().method() === 'POST');
  await form.getByRole('button', { name: 'Upload and index' }).click();
  const upload = await submitted;
  expect(upload.status()).toBe(202);
  const accepted = await upload.json() as Document;
  const details = page.getByRole('dialog', { name: 'Document details' });
  await expect(details.getByRole('status').filter({ hasText: 'PDF uploaded' })).toBeVisible();
  await expect(details.getByRole('status').filter({ hasText: /^Indexed$/ })).toBeVisible();
  await expect(details.getByRole('img', { name: 'PDF page 1' })).toBeVisible();
  await capture(page, label + '-indexed-upload');
  await details.getByRole('button', { name: 'Close dialog' }).click();

  await open(page, 'Knowledge Assistant');
  await page.getByLabel('Course', { exact: true }).selectOption({ label: 'Python Programming' });
  await page.getByLabel('Document', { exact: true }).selectOption({ label: title });
  await page.getByRole('textbox', { name: 'Your question' }).fill(question);
  const answered = page.waitForResponse((response) => response.url().endsWith('/api/questions') && response.request().method() === 'POST', { timeout: 60000 });
  await page.getByRole('button', { name: 'Send question' }).click();
  const response = await answered;
  expect(response.status()).toBe(201);
  const trace = await response.json() as Question;
  expect(trace.status, trace.answer?.reason ?? '').toBe('answered');
  expect(trace.document_id).toBe(accepted.id);
  expect(trace.answer?.provider).toBe(system.provider.name);
  if (MODE === 'live') expect(trace.answer?.provider_response_id).toMatch(/^resp_/);
  await expect(page.locator('.answer-body')).toContainText(/(?:four|4) graded labs/i);
  await expect(page.locator('.answer-body')).toContainText('70%');
  await expect(page.locator('.answer-body')).toContainText(/pass.{0,30}capstone/i);
  await capture(page, label + '-grounded-answer');

  const citation = trace.citations.find((item) => item.document_id === accepted.id && item.page_number === 4);
  expect(citation?.original_filename).toBe(filename);
  const source = page.getByRole('button', { name: /Full Journey Python Handbook Page 4/ });
  await source.click();
  const viewer = page.getByRole('dialog', { name: 'Source evidence' });
  await expect(viewer.getByRole('heading', { name: title })).toBeVisible();
  await expect(viewer.getByRole('img', { name: 'PDF page 4' })).toBeVisible();
  await expect(viewer.locator('blockquote')).toContainText('70%');
  const sourcePage = await page.request.get('/api/documents/' + accepted.id + '/pages/4');
  expect(sourcePage.headers()['content-type']).toContain('image/png');
  await viewer.getByText('Read full retrieved passage').click();
  await expect(viewer.locator('details p')).toContainText('all four graded labs');
  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(axe.violations.map(({ id, nodes }) => ({ id, elements: nodes.map(({ target }) => target) }))).toEqual([]);
  await capture(page, label + '-source-evidence');
  await page.keyboard.press('Escape');
  await expect(source).toBeFocused();
  await page.getByRole('button', { name: 'Helpful', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Feedback saved.' })).toBeVisible();

  await open(page, 'Question History');
  const outcome = page.getByRole('table', { name: 'Saved question traces' })
    .getByRole('row').filter({ hasText: question }).getByText('Answered', { exact: true });
  await expect(outcome).toBeVisible();
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await page.evaluate(() => document.fonts.ready);
    await capture(page, label + '-history-with-answer-' + viewport.width);
    const textLines = await outcome.evaluate((badge) => {
      const text = document.createRange();
      text.selectNode(badge.lastChild!);
      return text.getClientRects().length;
    });
    expect(textLines, 'History outcome at ' + viewport.width + ' pixels').toBe(1);
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole('button', { name: 'View trace for ' + question }).click();
  const stored = page.getByRole('dialog', { name: 'Question trace' });
  await expect(stored.locator('.answer-body')).toContainText('70%');
  await expect(stored.getByRole('button', { name: 'Helpful', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.keyboard.press('Escape');
  await open(page, 'Overview');
  const after = await (await page.request.get('/api/analytics/overview')).json() as Overview;
  expect(after.documents.indexed).toBe(before.documents.indexed + 1);
  expect(after.questions.answered).toBe(before.questions.answered + 1);
  expect(after.feedback.helpful).toBe(before.feedback.helpful + 1);
  const metrics = page.getByRole('article').filter({ hasText: 'Verified answers' }).locator('.metric-number');
  await expect(metrics).toHaveText(String(after.questions.answered));
  await page.reload();
  await expect(metrics).toHaveText(String(after.questions.answered));
  await open(page, 'Question History');
  await expect(page.getByRole('button', { name: 'View trace for ' + question })).toBeVisible();
  const persisted = await (await page.request.get('/api/questions/' + trace.id)).json() as Question;
  expect(persisted.answer?.rating).toBe('helpful');
  expect(persisted.citations).toEqual(trace.citations);
  if (captureDirectory) {
    await writeFile(join(captureDirectory, label + '-journey.json'), JSON.stringify({
      provider: system.provider.name, before, after, uploadedDocument: accepted, persisted,
    }, null, 2) + '\n');
  }

  // Only the uploaded variant is removed from this temporary workspace.
  expect((await page.request.delete('/api/documents/' + accepted.id)).status()).toBe(204);
});

