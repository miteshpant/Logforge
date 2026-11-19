import { test, expect } from '@playwright/test'

/**
 * Regression: pages must not scroll horizontally at a 1440px desktop width.
 *
 * The main content column was a flex item with the default min-width:auto, so
 * wide content (the 14-tactic MITRE row on SIEM, the rules table) stretched it
 * past the viewport and cut off page headers and actions. Needs a running stack.
 */
const EMAIL = process.env.E2E_EMAIL || 'dana@acme.example'
const PASSWORD = process.env.E2E_PASSWORD || 'Acme-Demo-Pass-123!'
const ROUTES = ['/centrum', '/security/siem', '/security/rules', '/security/cases', '/observability/logs', '/observability/apm', '/dashboards/system']

test.use({ viewport: { width: 1440, height: 900 } })

test('no page is wider than the viewport', async ({ page }) => {
  await page.goto('/login', { waitUntil: 'load' })
  await page.fill('[data-testid="email-input"]', EMAIL)
  await page.fill('[data-testid="password-input"]', PASSWORD)
  await page.locator('[data-testid="login-button"]:not([disabled])').click()
  await page.waitForURL(/\/centrum/)

  const tooWide: string[] = []
  for (const route of ROUTES) {
    await page.goto(route, { waitUntil: 'load' })
    await page.waitForTimeout(3000)
    const { scroll, client } = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      client: document.documentElement.clientWidth,
    }))
    if (scroll > client) tooWide.push(`${route}: ${scroll}px > ${client}px`)
  }
  expect(tooWide).toEqual([])
})

test('the Log Explorer fits in LogQL mode, with its extra buttons', async ({ page }) => {
  // Found with the Phase 6 screenshots: Builder and Add to dashboard pushed the
  // toolbar past 1440 px, so the page scrolled sideways and Filters was cut off.
  await page.goto('/login', { waitUntil: 'load' })
  await page.fill('[data-testid="email-input"]', EMAIL)
  await page.fill('[data-testid="password-input"]', PASSWORD)
  await page.locator('[data-testid="login-button"]:not([disabled])').click()
  await page.waitForURL(/\/centrum/)
  await page.goto('/observability/logs', { waitUntil: 'load' })
  await page.getByRole('button', { name: 'LogQL', exact: true }).click()
  await page.getByTestId('add-to-dashboard').waitFor()
  const { scroll, client } = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }))
  expect(scroll).toBeLessThanOrEqual(client)
})
