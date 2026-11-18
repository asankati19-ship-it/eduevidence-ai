import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { chromium } from '@playwright/test';

const origin = process.env.EDUEVIDENCE_PREVIEW_URL ?? 'http://127.0.0.1:5173';
const output = resolve(process.env.EDUEVIDENCE_CAPTURE_DIR ?? '../runtime/live-browser');
const question = 'What are the Python Programming course completion requirements?';
const browser = await chromium.launch({ channel: process.env.EDUEVIDENCE_BROWSER_CHANNEL });
try {
  await mkdir(output, { recursive: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 980 } });
  const api = page.request;
  const health = await api.get(origin + '/api/health');
  assert.equal(health.status(), 200);
  const status = await api.get(origin + '/api/system/status');
  const configuration = (await status.json()).provider;
  assert.equal(configuration.name, 'openai');
  assert.equal(configuration.configured, true);
  await page.goto(origin + '/assistant');
  await page.getByRole('combobox', { name: 'Course', exact: true }).selectOption({ label: 'Python Programming' });
  await page.getByRole('combobox', { name: 'Document', exact: true }).selectOption({ label: 'Python Programming Course Handbook' });
  await page.getByRole('textbox', { name: 'Your question' }).fill(question);
  const submitted = page.waitForResponse((response) => response.url().endsWith('/api/questions') && response.request().method() === 'POST', { timeout: 120000 });
  await page.getByRole('button', { name: 'Send question' }).click();
  const response = await submitted;
  assert.equal(response.status(), 201);
  const item = await response.json();
  assert.equal(item.status, 'answered', item.answer?.reason);
  assert.equal(item.answer.api_outcome, 'completed');
  assert.equal(item.answer.provider, 'openai');
  assert.ok(item.answer.provider_response_id);
  assert.match(item.answer.body, /(?:four|4) graded labs/i);
  assert.match(item.answer.body, /70%/);
  assert.match(item.answer.body, /pass.{0,24}capstone/i);
  await page.getByText('Answered', { exact: true }).waitFor();
  await page.screenshot({ path: join(output, 'assistant-live.png') });
  const citation = item.citations.find((source) => source.page_number === 4 && source.document_title === 'Python Programming Course Handbook');
  assert.ok(citation);
  await page.getByRole('button', { name: /Python Programming Course Handbook Page 4 · Chunk/ }).click();
  const evidence = page.getByRole('dialog', { name: 'Source evidence' });
  await evidence.getByRole('img', { name: 'PDF page 4' }).waitFor();
  assert.ok((await evidence.locator('blockquote').textContent()).includes('70%'));
  await page.screenshot({ path: join(output, 'citation-live.png') });
  await evidence.getByRole('button', { name: 'Close dialog' }).click();
  await page.getByRole('button', { name: 'Helpful', exact: true }).click();
  await page.getByText('Feedback saved.').waitFor();
  const persisted = await (await api.get(origin + '/api/questions/' + item.id)).json();
  assert.equal(persisted.answer.rating, 'helpful');
  const events = await (await api.get(origin + '/api/audit/events?request_id=' + item.request_id)).json();
  assert.equal(events.total, 4);
  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  await page.getByText('Verified answers', { exact: true }).waitFor();
  await page.screenshot({ path: join(output, 'overview-live.png') });
  await writeFile(join(output, 'live-browser.json'), JSON.stringify({
    mode: 'real_openai_via_browser', health: await health.json(), trace: persisted, audit: events.items,
  }, null, 2) + '\n');
  console.log('Live Edge journey passed: answered, cited page 4, rendered original PDF, persisted feedback and audit.');
} finally {
  await browser.close();
}

