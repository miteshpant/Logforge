import { test, expect } from '@playwright/test'
import { loginViaUi, watchForProblems } from './support/session'

/**
 * Every page in the sidebar loads for a tenant user without uncaught page
 * errors or failed API calls (>= 400).
 *
 * Pages keep event streams open, so "network idle" never happens; each page
 * gets a fixed settling time after load instead.
 */
const ROUTES = [
  '/centrum',
  '/observability/service-map',
  '/observability/traces',
  '/observability/apm',
  '/observability/metrics',
  '/observability/logs',
  '/dashboards',
  '/dashboards/system',
  '/anomaly-detection',
  '/alerts/rules',
  '/alerts/instances',
  '/alerts/channels',
  '/security/siem',
  '/security/cases',
  '/security/events',
  '/security/rules',
  '/security/threat-intel',
  '/security/threat-hunting',
  '/ai/alert-correlation',
  '/ai/predictive-analytics',
  '/ai/investigations',
  '/ai/ml-models',
  '/settings/authentication',
  '/settings/integrations',
  '/settings/roles',
  '/settings/costs',
  '/settings/compliance',
  '/settings/pipelines',
  '/settings/packs',
  '/settings/packs/linux',
  '/settings/ai',
]

const SETTLE_MS = 3_000

for (const route of ROUTES) {
  test(`${route} loads without errors`, async ({ page }) => {
    await loginViaUi(page)
    const problems = watchForProblems(page)

    await page.goto(route, { waitUntil: 'load' })
    await page.waitForTimeout(SETTLE_MS)

    expect(new URL(page.url()).pathname, 'redirected away from the page').toBe(route)
    await expect(page.getByTestId('main-navigation')).toBeVisible()
    expect(problems.pageErrors, 'uncaught page errors').toEqual([])
    expect(problems.failedApiCalls, 'failed API calls').toEqual([])
  })
}
