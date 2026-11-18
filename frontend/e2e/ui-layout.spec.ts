import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { MODE, capture, noOverflow, open } from './ui-helpers';

const SCREENS = [
  ['Overview', 'overview'], ['Document Library', 'library'], ['Knowledge Assistant', 'assistant'],
  ['Question History', 'history'], ['Feedback & Analytics', 'analytics'], ['Audit Logs', 'audit'], ['System Health', 'settings'],
] as const;
const SIZES = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'mobile', width: 390, height: 844 },
];

for (const size of SIZES) {
  test(size.name + ' screens have usable navigation, no horizontal overflow and no detected accessibility violations', async ({ page }) => {
    test.skip(MODE !== 'fixture');
    test.setTimeout(90000);
    await page.setViewportSize({ width: size.width, height: size.height });
    const pageErrors: string[] = [];
    page.on('pageerror', (error) => pageErrors.push(error.message));
    await page.goto('/');
    for (const [name, slug] of SCREENS) {
      if (slug !== 'overview') await open(page, name);
      await expect(page.getByRole('heading', { name, exact: true, level: 1 })).toBeVisible();
      await expect(page.locator('main .loading')).toHaveCount(0);
      await page.evaluate(() => document.fonts.ready);
      await noOverflow(page);
      const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
      expect(axe.violations.map(({ id, nodes }) => ({ id, elements: nodes.map(({ target }) => target) })), size.name + ' ' + name).toEqual([]);
      if (['overview', 'library', 'assistant'].includes(slug) || size.name === 'desktop') await capture(page, size.name + '-' + slug, size.name === 'mobile');
    }
    expect(pageErrors).toEqual([]);
  });
}

test('keyboard skip, drawer tab order and Escape restore focus', async ({ page }) => {
  test.skip(MODE !== 'fixture');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.keyboard.press('Tab');
  const skip = page.getByRole('link', { name: 'Skip to content' });
  await expect(skip).toBeFocused();
  const focusStyle = await skip.evaluate((node) => getComputedStyle(node).outlineStyle);
  expect(focusStyle).toBe('solid');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('main')).toBeFocused();
  const toggle = page.getByRole('button', { name: 'Open navigation' });
  await toggle.focus();
  await page.keyboard.press('Enter');
  const drawer = page.getByRole('dialog', { name: 'Workspace navigation' });
  const close = drawer.getByRole('button', { name: 'Close navigation' });
  await expect(close).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(drawer.getByRole('link', { name: 'Overview', exact: true })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(close).toBeFocused();
  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(axe.violations.map(({ id }) => id)).toEqual([]);
  await capture(page, 'mobile-navigation');
  await page.keyboard.press('Escape');
  await expect(drawer).toBeHidden();
  await expect(toggle).toBeFocused();
  await page.keyboard.press('Enter');
  const library = drawer.getByRole('link', { name: 'Document Library' });
  await library.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Document Library', level: 1 })).toBeVisible();
  await expect(page.getByRole('main')).toBeFocused();
  await noOverflow(page);
});

