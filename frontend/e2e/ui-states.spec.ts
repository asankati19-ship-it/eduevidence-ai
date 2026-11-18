import { expect, test, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import type { Document, Question } from '../src/types';
import { MODE, SAMPLE, capture, noOverflow, open } from './ui-helpers';

async function pythonScope(page: Page, document = '1') {
  await page.getByLabel('Course', { exact: true }).selectOption('1');
  await page.getByLabel('Document', { exact: true }).selectOption(document);
}

async function ask(page: Page, question: string) {
  await page.getByRole('textbox', { name: 'Your question' }).fill(question);
  await page.getByRole('button', { name: 'Send question' }).click();
}

function blankPdf() {
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Count 1 /Kids [3 0 R] >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>',
  ];
  let file = '%PDF-1.4\n';
  const offsets = objects.map((body, index) => {
    const offset = file.length;
    file += (index + 1) + ' 0 obj\n' + body + '\nendobj\n';
    return offset;
  });
  const start = file.length;
  file += 'xref\n0 4\n0000000000 65535 f \n' + offsets.map((value) => String(value).padStart(10, '0') + ' 00000 n \n').join('');
  return Buffer.from(file + 'trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n' + start + '\n%%EOF\n');
}

test('empty library shows the first-upload path', async ({ page }) => {
  test.skip(MODE !== 'empty');
  await page.goto('/documents');
  await expect(page.getByRole('heading', { name: 'No PDFs in the library' })).toBeVisible();
  await capture(page, 'empty-library');
  await page.getByRole('button', { name: 'Upload your first PDF' }).click();
  await expect(page.getByRole('dialog', { name: 'Upload a course PDF' })).toBeVisible();
});

test('missing credentials are displayed and a grounded lookup reports the backend outcome', async ({ page }) => {
  test.skip(MODE !== 'unconfigured');
  await page.goto('/assistant');
  await expect(page.getByText('OpenAI setup required')).toBeVisible();
  await pythonScope(page);
  await ask(page, 'What are the Python Programming course completion requirements?');
  await expect(page.getByText('Missing credentials', { exact: true })).toBeVisible();
  await expect(page.locator('.answer-reason')).toContainText('Set OPENAI_API_KEY');
  await capture(page, 'missing-credentials');
  await page.getByRole('link', { name: 'Open system health' }).click();
  await expect(page.getByText('Missing API key')).toBeVisible();
});

test('SQLite failure shows the correlated API message and retry restores system health', async ({ page }) => {
  test.skip(MODE !== 'database-error');
  const statusResponse = page.waitForResponse((response) => response.url().endsWith('/api/system/status'));
  await page.goto('/settings');
  const response = await statusResponse;
  expect(response.status()).toBe(503);
  const failure = (await response.json()).error;
  expect(failure.code).toBe('database_error');
  const alert = page.getByRole('alert');
  await expect(alert).toContainText(failure.message);
  await expect(alert).toContainText(failure.request_id);
  await capture(page, 'database-error');
  await alert.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByRole('heading', { name: 'SQLite database' })).toBeVisible();
  await expect(page.getByText('reachable', { exact: true })).toBeVisible();
});

test('initial loading, upload, indexing and indexing failure are visible with delayed responses', async ({ page }) => {
  test.skip(MODE !== 'fixture');
  let releaseList: () => void = () => {};
  const holdList = new Promise<void>((resolve) => { releaseList = resolve; });
  await page.route('**/api/documents?*', async (route) => { await holdList; await route.continue(); }, { times: 1 });
  await page.goto('/documents');
  await expect(page.getByRole('status').filter({ hasText: 'Loading documents…' })).toBeVisible();
  releaseList();
  await expect(page.getByRole('table', { name: 'Course PDFs' })).toBeVisible();

  let releaseUpload: () => void = () => {};
  let releasePoll: () => void = () => {};
  const holdUpload = new Promise<void>((resolve) => { releaseUpload = resolve; });
  const holdPoll = new Promise<void>((resolve) => { releasePoll = resolve; });
  await page.route('**/api/documents/upload', async (route) => { await holdUpload; await route.continue(); });
  await page.route(/\/api\/documents\/\d+$/, async (route) => { await holdPoll; await route.continue(); });
  await page.getByRole('button', { name: 'Upload PDF', exact: true }).click();
  const form = page.getByRole('dialog', { name: 'Upload a course PDF' });
  await form.getByLabel('Course', { exact: true }).selectOption('1');
  await form.getByLabel('PDF file').setInputFiles({ name: 'test-empty-page.pdf', mimeType: 'application/pdf', buffer: blankPdf() });
  let uploads = 0;
  page.on('request', (request) => { if (request.url().endsWith('/api/documents/upload') && request.method() === 'POST') uploads++; });
  const submitted = page.waitForResponse((response) => response.url().endsWith('/api/documents/upload'));
  await form.getByRole('button', { name: 'Upload and index' }).click();
  await expect(form.getByRole('status').filter({ hasText: 'Uploading PDF…' })).toBeVisible();
  await expect(form.getByRole('button', { name: 'Uploading…', exact: true })).toBeDisabled();
  await capture(page, 'upload-in-progress');
  await page.keyboard.press('Escape');
  await expect(form).toBeVisible();
  releaseUpload();
  const accepted = await (await submitted).json() as Document;
  expect(uploads).toBe(1);
  const details = page.getByRole('dialog', { name: 'Document details' });
  await expect(details.getByRole('status').filter({ hasText: 'PDF uploaded' })).toBeVisible();
  await expect(details.getByRole('status').filter({ hasText: 'Indexing the PDF…' })).toBeVisible();
  releasePoll();
  await expect(details.getByRole('alert')).toContainText('No extractable text');
  await capture(page, 'indexing-failed');
  expect((await page.request.delete('/api/documents/' + accepted.id)).status()).toBe(204);
});

test('blank and duplicate asks are blocked, generation waits on backend, and scope and draft resume', async ({ page }) => {
  test.skip(MODE !== 'fixture');
  await page.goto('/assistant');
  await pythonScope(page);
  const box = page.getByRole('textbox', { name: 'Your question' });
  const send = page.getByRole('button', { name: 'Send question' });
  let posts = 0;
  page.on('request', (request) => { if (request.url().endsWith('/api/questions') && request.method() === 'POST') posts++; });
  await box.fill('   ');
  await expect(send).toBeDisabled();
  await box.press('Control+Enter');
  expect(posts).toBe(0);
  await box.fill('Keep this unsent draft.');
  await open(page, 'Overview');
  await open(page, 'Knowledge Assistant');
  await expect(box).toHaveValue('Keep this unsent draft.');
  await expect(page.getByLabel('Document', { exact: true })).toHaveValue('1');
  const question = 'Which course completion requirements are listed in the Python Programming handbook?';
  await box.fill(question);
  await box.press('Control+Enter');
  await expect(send).toBeDisabled();
  await expect(box).toHaveAttribute('readonly', '');
  await box.press('Control+Enter');
  await expect(page.getByRole('status').filter({ hasText: 'Generating an answer…' })).toBeVisible();
  await open(page, 'Overview');
  await open(page, 'Knowledge Assistant');
  await expect(page.getByText(question, { exact: true })).toBeVisible();
  await expect(page.getByText('Answered', { exact: true })).toBeVisible();
  expect(posts).toBe(1);
  await page.reload();
  await expect(page.locator('.answer-body')).toContainText('70%');
  await page.getByRole('button', { name: 'New conversation', exact: true }).click();
  await expect(box).toHaveValue('');
  await expect(page.getByLabel('Document', { exact: true })).toHaveValue('');
  await expect(page.locator('.answer-body')).toHaveCount(0);
});

test('Markdown lists persist and the answer renderer ignores raw HTML, links and images', async ({ page }) => {
  test.skip(MODE !== 'fixture');
  await page.goto('/assistant');
  await pythonScope(page);
  await ask(page, 'List the Python Programming course completion requirements as Markdown.');
  const body = page.locator('.answer-body');
  await expect(body.getByRole('listitem')).toHaveCount(3);
  await expect(body.locator('strong')).toHaveText('Completion requirements');
  await page.reload();
  await expect(body.getByRole('listitem')).toHaveCount(3);

  // Intercept answer text only to exercise the renderer with untrusted Markdown. Provenance remains the real trace.
  await page.route('**/api/questions/history?*', async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.items[0].answer.body += '\n\n<strong data-test-raw>Raw HTML test</strong>\n\n[Untrusted link](javascript:alert%281%29)\n\n![Untrusted image](/unexpected-ui-image.png)';
    await route.fulfill({ response, json: data });
  });
  await page.reload();
  await expect(body.getByText('Untrusted link')).toBeVisible();
  await expect(body.locator('a, img, script, [data-test-raw]')).toHaveCount(0);
});

test('a long answer with many real citations and long filenames stays inside the mobile viewport', async ({ page }) => {
  test.skip(MODE !== 'fixture');
  test.setTimeout(50000);
  const fixture = await readFile(SAMPLE);
  const padded = 'Course-Handbook-'.repeat(8);
  const uploaded: number[] = [];
  try {
    for (let index = 0; index < 4; index++) {
      const result = await page.request.post('/api/documents/upload', { multipart: {
        file: { name: padded + index + '.pdf', mimeType: 'application/pdf', buffer: Buffer.concat([fixture, Buffer.from('\n% layout fixture ' + index + '\n')]) },
        title: padded + index, course_id: '1',
      } });
      expect(result.status()).toBe(202);
      uploaded.push((await result.json()).id);
    }
    await expect.poll(async () => {
      const states = await Promise.all(uploaded.map(async (id) => (await (await page.request.get('/api/documents/' + id)).json()).status));
      return states.every((status) => status === 'indexed');
    }).toBe(true);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/documents');
    await expect(page.getByRole('button', { name: 'View details for ' + padded + '0' })).toBeVisible();
    await noOverflow(page);
    await open(page, 'Knowledge Assistant');
    await page.getByLabel('Course', { exact: true }).selectOption('1');
    const answer = page.waitForResponse((response) => response.url().endsWith('/api/questions') && response.request().method() === 'POST');
    await ask(page, 'What are the course completion requirements across the Python Programming handbooks?');
    const record = await (await answer).json() as Question;
    expect(record.answer?.body?.length).toBeGreaterThan(2000);
    expect(record.citations).toHaveLength(5);
    expect(record.citations.every((citation) => citation.page_number === 4)).toBe(true);
    await expect(page.getByRole('region', { name: 'Verified citations' }).getByRole('button')).toHaveCount(5);
    await noOverflow(page);
    await page.getByRole('button', { name: new RegExp(padded + '0 Page 4') }).click();
    const evidence = page.getByRole('dialog', { name: 'Source evidence' });
    await expect(evidence.getByRole('img', { name: 'PDF page 4' })).toBeVisible();
    await evidence.getByText('Full document name and filename').click();
    await expect(evidence.getByText(padded + '0.pdf', { exact: true })).toBeVisible();
    await evidence.getByText('Full document name and filename').click();
    await noOverflow(page);
    await capture(page, 'mobile-long-filename-citation');
  } finally {
    for (const id of uploaded) await page.request.delete('/api/documents/' + id);
  }
});

