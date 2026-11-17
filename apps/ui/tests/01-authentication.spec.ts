import { test, expect } from '@playwright/test'
import { PASSWORD, TENANT_NAME, loginViaUi } from './support/session'

/**
 * Authentication against a live stack (scripts/bootstrap_demo.py user).
 *
 * The invalid-login test uses a random, non-existent account so repeated runs
 * never trip the per-account lockout of the real test user.
 */

test('valid login opens Centrum for the user\'s tenant', async ({ page }) => {
  await loginViaUi(page)

  await expect(page.getByTestId('centrum-container')).toBeVisible()
  await expect(page.getByTestId('current-tenant')).toContainText(TENANT_NAME)
  const token = await page.evaluate(() => localStorage.getItem('auth_token'))
  expect(token).toBeTruthy()
})

test('invalid credentials show the server\'s message and do not sign in', async ({ page }) => {
  await page.goto('/login', { waitUntil: 'load' })
  await page.fill('[data-testid="email-input"]', `nobody-${Date.now()}@example.com`)
  await page.fill('[data-testid="password-input"]', 'Wrong-Password-123!')
  await page.locator('[data-testid="login-button"]:not([disabled])').click()

  await expect(page.getByTestId('error-message')).toContainText('Invalid email or password')
  expect(new URL(page.url()).pathname).toBe('/login')
  expect(await page.evaluate(() => localStorage.getItem('auth_token'))).toBeNull()
})

test('the session survives a page reload', async ({ page }) => {
  await loginViaUi(page)
  await page.reload({ waitUntil: 'load' })

  expect(new URL(page.url()).pathname).toBe('/centrum')
  await expect(page.getByTestId('current-tenant')).toContainText(TENANT_NAME)
})

test('logout clears the session and protected pages redirect to login', async ({ page }) => {
  await loginViaUi(page)
  await page.getByTestId('user-menu').click()
  await page.getByTestId('logout-button').click()
  await page.waitForURL(/\/login/)

  expect(await page.evaluate(() => localStorage.getItem('auth_token'))).toBeNull()
  await page.goto('/security/siem', { waitUntil: 'load' })
  await page.waitForURL(/\/login/)
})

test('an expired or forged session is sent back to login', async ({ page }) => {
  await page.goto('/login', { waitUntil: 'load' })
  await page.evaluate(() => {
    localStorage.setItem('auth_token', 'not-a-valid-token')
    localStorage.setItem('refresh_token', 'not-a-valid-refresh-token')
    localStorage.setItem('tenant_id', 'some-tenant')
  })

  await page.goto('/centrum', { waitUntil: 'load' })
  await page.waitForURL(/\/login/, { timeout: 15_000 })
})

test('credentials are sent only to the login endpoint, never in a URL', async ({ page }) => {
  const leaks: string[] = []
  page.on('request', (r) => {
    if (r.url().includes(encodeURIComponent(PASSWORD)) || r.url().includes(PASSWORD)) leaks.push(r.url())
  })
  await loginViaUi(page)
  expect(leaks).toEqual([])
})
