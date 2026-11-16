import { test, expect, Request } from '@playwright/test'

/**
 * Regression: a full page load must not send API requests without auth.
 *
 * React runs child effects before parent effects, so on a reload or deep link
 * each page's data fetch fired before AuthContext restored the session. Those
 * requests had no Authorization / X-Customer-ID header and came back 401,
 * triggering a token refresh: 59 avoidable 401s across 28 routes in the QA run.
 * lib/api.ts now hydrates its auth headers from storage before every request.
 *
 * Needs a running stack and an active tenant user:
 *   E2E_EMAIL / E2E_PASSWORD (defaults: the README quick-start user).
 */
const EMAIL = process.env.E2E_EMAIL || 'dana@acme.example'
const PASSWORD = process.env.E2E_PASSWORD || 'Acme-Demo-Pass-123!'
const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080'

const ROUTES = ['/centrum', '/observability/logs', '/alerts/rules', '/security/siem', '/settings/roles']

const isApiCall = (r: Request) =>
  r.url().startsWith(`${API}/v1/`) &&
  r.method() !== 'OPTIONS' &&
  !r.url().includes('/v1/auth/login') &&
  !r.url().includes('/v1/auth/refresh') && // authenticates with the refresh token in the body
  !r.url().includes('/v1/stream/') // SSE authenticates via query params

test('full page loads send every API request authenticated', async ({ page }) => {
  await page.goto('/login', { waitUntil: 'networkidle' })
  await page.fill('[data-testid="email-input"]', EMAIL)
  await page.fill('[data-testid="password-input"]', PASSWORD)
  await page.locator('[data-testid="login-button"]:not([disabled])').click()
  await page.waitForURL(/\/centrum/, { timeout: 30_000 })

  const unauthenticated: string[] = []
  const unauthorized: string[] = []
  page.on('request', r => {
    if (isApiCall(r) && !r.headers()['authorization']) unauthenticated.push(r.url())
  })
  page.on('response', r => {
    if (isApiCall(r.request()) && r.status() === 401) unauthorized.push(r.url())
  })

  for (const route of ROUTES) {
    // Full load, not client-side navigation. Not 'networkidle': live SSE
    // streams keep the network busy, so give the page's fetches time instead.
    await page.goto(route, { waitUntil: 'load' })
    await page.waitForTimeout(3000)
  }

  expect(unauthenticated, 'requests sent without Authorization').toEqual([])
  expect(unauthorized, 'requests rejected with 401').toEqual([])
})
