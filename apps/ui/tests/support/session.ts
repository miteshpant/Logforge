import { APIRequestContext, Page, expect } from '@playwright/test'

/**
 * Shared helpers for specs that run against a live stack seeded by
 * scripts/bootstrap_demo.py (tenant "Acme", user dana@acme.example).
 */
export const EMAIL = process.env.E2E_EMAIL || 'dana@acme.example'
export const PASSWORD = process.env.E2E_PASSWORD || 'Acme-Demo-Pass-123!'
export const TENANT_NAME = process.env.E2E_TENANT_NAME || 'Acme'
export const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080'

/** Log in through the UI and wait for the landing page. */
export async function loginViaUi(page: Page): Promise<void> {
  await page.goto('/login', { waitUntil: 'load' })
  await page.fill('[data-testid="email-input"]', EMAIL)
  await page.fill('[data-testid="password-input"]', PASSWORD)
  await page.locator('[data-testid="login-button"]:not([disabled])').click()
  await page.waitForURL(/\/centrum$/)
}

/** Access token and tenant id for direct API calls (test data setup). */
export async function apiSession(request: APIRequestContext): Promise<{ token: string; tenantId: string }> {
  const res = await request.post(`${API}/v1/auth/login`, { data: { email: EMAIL, password: PASSWORD } })
  expect(res.ok(), `login failed: ${res.status()}`).toBeTruthy()
  const body = await res.json()
  const payload = JSON.parse(Buffer.from(body.access_token.split('.')[1], 'base64url').toString())
  return { token: body.access_token, tenantId: payload.tenant_id }
}

/** Collect failed API calls (>= 400) and uncaught page errors while a page runs. */
export function watchForProblems(page: Page) {
  const failedApiCalls: string[] = []
  const pageErrors: string[] = []
  page.on('response', (r) => {
    if (r.url().startsWith(`${API}/`) && r.status() >= 400) {
      failedApiCalls.push(`${r.status()} ${r.request().method()} ${r.url().replace(API, '').split('?')[0]}`)
    }
  })
  page.on('pageerror', (e) => pageErrors.push(e.message.slice(0, 200)))
  return { failedApiCalls, pageErrors }
}
