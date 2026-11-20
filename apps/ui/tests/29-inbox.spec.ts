import { test, expect } from '@playwright/test'
import { API, apiSession, watchForProblems } from './support/session'

/**
 * Case @mentions reach the person: an analyst mentions a colleague in a case
 * comment; the colleague's bell shows it, and opening it leads to the case
 * and marks it read.
 */

const email = `e2e-inbox-${Date.now()}@example.invalid`
const password = 'E2e-Inbox-Passw0rd!'

test('a case @mention shows under the mentioned user\'s bell', async ({ page, request }) => {
  test.setTimeout(120_000)
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const made = await request.post(`${API}/v1/users`, { headers, data: { name: 'E2E Inbox', email, password, status: 'active' } })
  expect(made.ok(), await made.text()).toBeTruthy()
  const role = await request.post(`${API}/v1/users/${(await made.json()).id}/roles`,
    { headers, data: { tenant_id: tenantId, role: 'security_analyst' } })
  expect(role.ok(), await role.text()).toBeTruthy()

  const created = await request.post(`${API}/v1/security/cases`, { headers, data: { title: `Inbox e2e ${Date.now()}`, severity: 'high' } })
  expect(created.ok(), await created.text()).toBeTruthy()
  const caseId = (await created.json()).id
  const comment = await request.post(`${API}/v1/security/cases/${caseId}/comments`,
    { headers, data: { text: `@${email.split('@')[0]} can you check the source address?` } })
  expect(comment.ok(), await comment.text()).toBeTruthy()

  await page.goto('/login', { waitUntil: 'load' })
  await page.fill('[data-testid="email-input"]', email)
  await page.fill('[data-testid="password-input"]', password)
  await page.locator('[data-testid="login-button"]:not([disabled])').click()
  await page.waitForURL(/\/centrum$/)
  const problems = watchForProblems(page)

  await expect(page.getByTestId('inbox-unread')).toHaveText('1', { timeout: 30_000 })
  await page.getByTestId('inbox-bell').click()
  const item = page.getByTestId('inbox-item').first()
  await expect(item).toContainText('mentioned you in case Inbox e2e')
  await item.click()
  await page.waitForURL(new RegExp(`/security/cases/${caseId}$`))
  await expect(page.getByTestId('inbox-unread')).toHaveCount(0)

  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})
