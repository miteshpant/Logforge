import { test, expect } from '@playwright/test'
import { API, apiSession, watchForProblems } from './support/session'

/**
 * Centrum, the landing page, for every built-in role below tenant admin:
 * it shows only the widgets the role can read, so no request is refused.
 * (It called usage, advanced-query, stream and security endpoints for
 * everyone, and a viewer got nine 403s on sign-in.)
 */

const expected: Record<string, { shows: string[]; hides: string[] }> = {
  viewer: { shows: ['logs'], hides: ['security', 'alerts', 'usage'] },
  security_analyst: { shows: ['logs', 'security', 'alerts'], hides: ['usage'] },
  devops_engineer: { shows: ['logs', 'alerts'], hides: ['security', 'usage'] },
  compliance_officer: { shows: ['logs'], hides: ['security', 'alerts', 'usage'] },
}

for (const [role, widgets] of Object.entries(expected)) {
  test(`Centrum as ${role} makes no refused requests`, async ({ page, request }) => {
    test.setTimeout(120_000)
    const { token, tenantId } = await apiSession(request)
    const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
    const email = `e2e-centrum-${role.replace('_', '-')}-${Date.now()}@example.invalid`
    const password = 'E2e-Centrum-Passw0rd!'
    const made = await request.post(`${API}/v1/users`, { headers, data: { name: `E2E ${role}`, email, password, status: 'active' } })
    expect(made.ok(), await made.text()).toBeTruthy()
    const granted = await request.post(`${API}/v1/users/${(await made.json()).id}/roles`, { headers, data: { tenant_id: tenantId, role } })
    expect(granted.ok(), await granted.text()).toBeTruthy()

    const problems = watchForProblems(page)
    await page.goto('/login', { waitUntil: 'load' })
    await page.fill('[data-testid="email-input"]', email)
    await page.fill('[data-testid="password-input"]', password)
    await page.locator('[data-testid="login-button"]:not([disabled])').click()
    await page.waitForURL(/\/centrum$/)
    await expect(page.getByTestId('centrum-container')).toBeVisible()
    for (const w of widgets.shows) await expect(page.getByTestId(`centrum-${w}`)).toBeVisible({ timeout: 30_000 })
    for (const w of widgets.hides) await expect(page.getByTestId(`centrum-${w}`)).toHaveCount(0)
    await page.waitForTimeout(4_000)  // widgets load in stages; let the last ones ask
    expect(problems.pageErrors).toEqual([])
    expect(problems.failedApiCalls).toEqual([])
  })
}
