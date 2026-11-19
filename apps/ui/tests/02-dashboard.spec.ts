import { test, expect, Request } from '@playwright/test'
import { API, loginViaUi, watchForProblems } from './support/session'

/**
 * Centrum (the landing dashboard) against a live stack.
 *
 * Centrum keeps an event stream open, so "network idle" never happens; tests
 * wait for the widgets' own data requests instead.
 */
const WIDGET_ENDPOINTS = [
  '/v1/query/advanced',
  '/v1/alerts/stats/overview',
  '/v1/security/dashboard',
  '/v1/observability/overview/stats',
  '/v1/usage/overview/stats',
]

function widgetResponses(page: import('@playwright/test').Page) {
  return Promise.all(WIDGET_ENDPOINTS.map((path) =>
    page.waitForResponse((r) => r.url().split('?')[0] === `${API}${path}` && r.request().method() !== 'OPTIONS')))
}

test('Centrum loads its widgets without errors or failed API calls', async ({ page }) => {
  const problems = watchForProblems(page)
  const loaded = widgetResponses(page)
  await loginViaUi(page)
  await expect(page.getByTestId('centrum-container')).toBeVisible()
  await loaded

  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})

test('changing the time range refetches data for the new window', async ({ page }) => {
  const loaded = widgetResponses(page)
  await loginViaUi(page)
  await loaded
  await expect(page.getByTestId('current-time-range')).toHaveText('Last 24 hours')

  const refetch = page.waitForRequest((r: Request) =>
    r.url() === `${API}/v1/query/advanced` && r.method() === 'POST')
  await page.getByTestId('time-range-button').click()
  await page.getByTestId('time-range-7d').click()

  await expect(page.getByTestId('current-time-range')).toHaveText('Last 7 days')
  const body = (await refetch).postDataJSON()
  const windowMs = Date.parse(body.end_time) - Date.parse(body.start_time)
  const days = windowMs / 86_400_000
  expect(days).toBeGreaterThan(6.9)
  expect(days).toBeLessThan(7.1)
})
