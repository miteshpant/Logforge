import { test, expect } from '@playwright/test'

/**
 * Regression: protected pages must not render (or call the API) without a
 * session. Previously an unauthenticated visitor got the full app shell with
 * zeroed widgets while every page fired its API calls, all of them 401.
 *
 * Needs a running stack; credentials as in 05-auth-hydration.spec.ts.
 */
const EMAIL = process.env.E2E_EMAIL || 'dana@acme.example'
const PASSWORD = process.env.E2E_PASSWORD || 'Acme-Demo-Pass-123!'
const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080'

test('unauthenticated deep link redirects to login and returns after sign-in', async ({ page }) => {
  const apiCalls: string[] = []
  page.on('request', r => {
    if (r.url().startsWith(`${API}/v1/`)) apiCalls.push(r.url())
  })

  await page.goto('/security/siem', { waitUntil: 'load' })
  await page.waitForURL(/\/login\?next=%2Fsecurity%2Fsiem/)
  expect(apiCalls, 'no API calls before sign-in').toEqual([])

  await page.fill('[data-testid="email-input"]', EMAIL)
  await page.fill('[data-testid="password-input"]', PASSWORD)
  await page.locator('[data-testid="login-button"]:not([disabled])').click()
  await page.waitForURL(/\/security\/siem$/)
})

for (const hostile of ['//evil.example/x', 'https://evil.example']) {
  test(`login ignores off-site next=${hostile}`, async ({ page }) => {
    await page.goto(`/login?next=${encodeURIComponent(hostile)}`, { waitUntil: 'load' })
    await page.fill('[data-testid="email-input"]', EMAIL)
    await page.fill('[data-testid="password-input"]', PASSWORD)
    await page.locator('[data-testid="login-button"]:not([disabled])').click()
    await page.waitForURL(/\/centrum$/)
    expect(new URL(page.url()).host).toBe('localhost:3001')
  })
}
