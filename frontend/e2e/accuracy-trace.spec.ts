import { expect, test, type Page } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { Document, Page as ApiPage, Question, SystemStatus } from '../src/types';
import { MODE, capture, captureDirectory, open } from './ui-helpers';

const COMPLETION = 'For the course audit, what are the Python Programming course completion requirements?';
const UNSUPPORTED = 'What is the cafeteria menu on Tuesday?';
const UNSTATED_POLICY = 'Do the assessment review rules grant an automatic grade increase?';
const TIMEOUT = 'What are the Python Programming course completion requirements for learners in the handbook?';

async function ask(page: Page, question: string) {
  const submitted = page.waitForResponse(
    (response) => response.url().endsWith('/api/questions') && response.request().method() === 'POST',
    { timeout: 100000 },
  );
  await page.getByRole('textbox', { name: 'Your question' }).fill(question);
  await page.getByRole('button', { name: 'Send question' }).click();
  const response = await submitted;
  expect(response.status()).toBe(201);
  const trace = await response.json() as Question;
  expect(response.headers()['x-request-id']).toBe(trace.request_id);
  return trace;
}

test('functional trace matches React, FastAPI, and one SQLite workspace for each outcome', async ({ page }) => {
  test.skip(!process.env.EDUEVIDENCE_TRACE_DB_DIR || !['live', 'fixture'].includes(MODE));
  test.setTimeout(120000);
  const system = await (await page.request.get('/api/system/status')).json() as SystemStatus;
  expect(system.provider.name).toBe(MODE === 'live' ? 'openai' : 'offline_fixture');
  const listed = await (await page.request.get('/api/documents?limit=100')).json() as ApiPage<Document>;
  const document = listed.items.find((item) => item.original_filename === 'Python Programming Course Handbook.pdf');
  expect(document).toBeDefined();
  await page.goto('/assistant');
  await page.getByLabel('Course', { exact: true }).selectOption(String(document!.course_id));
  await page.getByLabel('Document', { exact: true }).selectOption(String(document!.id));
  const answered = await ask(page, COMPLETION);
  expect(answered.status, answered.answer?.reason ?? '').toBe('answered');
  expect(answered.answer?.verification_passed).toBe(true);
  if (MODE === 'live') expect(answered.answer?.provider_response_id).toMatch(/^resp_/);
  expect(answered.citations.map(({ document_id, page_number }) => [document_id, page_number])).toEqual([[document!.id, 4]]);
  const answerCard = page.getByRole('article', { name: 'Assistant response' });
  await expect(answerCard.locator('.answer-body')).toContainText(/(?:all four|all 4) graded labs/i);
  await expect(answerCard.locator('.answer-body')).toContainText('70%');
  await expect(answerCard.locator('.answer-body')).toContainText(/pass.{0,30}capstone/i);
  await page.getByRole('button', { name: /Python Programming Course Handbook Page 4/ }).click();
  const citation = page.getByRole('dialog', { name: 'Source evidence' });
  await expect(citation.getByRole('img', { name: 'PDF page 4' })).toBeVisible();
  await expect(citation.locator('blockquote')).toContainText('70%');
  await capture(page, 'accuracy-' + MODE + '-citation');
  await citation.getByRole('button', { name: 'Close dialog' }).click();

  const abstained = await ask(page, UNSUPPORTED);
  expect(abstained.status).toBe('abstained');
  expect(abstained.answer?.api_outcome).toBe('skipped');
  expect(abstained.citations).toHaveLength(0);
  expect(abstained.sources).toHaveLength(0);
  const abstention = page.getByRole('article', { name: 'Assistant response' }).filter({ hasText: 'Abstained' });
  await expect(abstention.locator('.answer-reason')).toContainText('matching evidence');
  await expect(abstention.getByRole('region', { name: 'Verified citations' })).toHaveCount(0);
  await capture(page, 'accuracy-' + MODE + '-abstention');

  const rows = [answered, abstained];
  if (MODE === 'live') {
    const policy = listed.items.find((item) => item.original_filename === 'LMS Assessment and Attendance Policy.pdf');
    expect(policy).toBeDefined();
    await page.getByLabel('Course', { exact: true }).selectOption(String(policy!.course_id));
    await page.getByLabel('Document', { exact: true }).selectOption(String(policy!.id));
    const missingPolicy = await ask(page, UNSTATED_POLICY);
    expect(missingPolicy.status, missingPolicy.answer?.body ?? '').toBe('abstained');
    expect(missingPolicy.answer?.provider_response_id).toMatch(/^resp_/);
    expect(missingPolicy.answer?.body).toBeNull();
    expect(missingPolicy.citations).toHaveLength(0);
    const latestTurn = page.getByRole('article', { name: 'Assistant response' }).last();
    await expect(latestTurn.locator('.answer-reason')).toBeVisible();
    await expect(latestTurn.getByRole('region', { name: 'Verified citations' })).toHaveCount(0);
    await capture(page, 'accuracy-live-unstated-policy');
    rows.push(missingPolicy);
  } else {
    const failure = await ask(page, TIMEOUT);
    expect(failure.status).toBe('provider_error');
    expect(failure.answer?.error_code).toBe('timeout');
    expect(failure.answer?.provider_response_id).toBeNull();
    expect(failure.answer?.body).toBeNull();
    expect(failure.citations).toHaveLength(0);
    await expect(page.getByText('API timeout', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Retry question' })).toBeEnabled();
    await capture(page, 'accuracy-fixture-timeout');
    rows.push(failure);
  }

  await open(page, 'Question History');
  for (const trace of rows) {
    await expect(page.getByRole('button', { name: 'View trace for ' + trace.question_text })).toBeVisible();
    const persisted = await (await page.request.get('/api/questions/' + trace.id)).json() as Question;
    expect(persisted).toEqual(trace);
  }
  if (captureDirectory) {
    await writeFile(join(captureDirectory, 'browser-' + MODE + '-trace.json'), JSON.stringify({
      mode: MODE, document, cases: rows,
    }, null, 2) + '\n');
  }
});

