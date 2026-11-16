import { test, expect } from '@playwright/test'

/**
 * Regression: the header plan badge shows the tenant's subscription tier, not
 * its organisation type. A tenant created as "startup" and upgraded to
 * "enterprise" kept showing "startup". Needs a running stack.
 */
const EMAIL = process.env.E2E_EMAIL || 'dana@acme.example'
const PASSWORD = process.env.E2E_PASSWORD || 'Acme-Demo-Pass-123!'
const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080'

test('plan badge matches the subscription tier from the API', async ({ page, request }) => {
  await page.goto('/login', { waitUntil: 'load' })
  await page.fill('[data-testid="email-input"]', EMAIL)
  await page.fill('[data-testid="password-input"]', PASSWORD)
  await page.locator('[data-testid="login-button"]:not([disabled])').click()
  await page.waitForURL(/\/centrum/)

  const { token, tenantId } = await page.evaluate(() => ({
    token: localStorage.getItem('auth_token'),
    tenantId: localStorage.getItem('tenant_id'),
  }))
  const res = await request.get(`${API}/v1/tenants/${tenantId}/subscription`, {
    headers: { Authorization: `Bearer ${token}`, 'X-Customer-ID': String(tenantId) },
  })
  expect(res.ok()).toBeTruthy()
  const { subscription_tier } = await res.json()

  await expect(page.locator('header').first()).toContainText(subscription_tier)
})
