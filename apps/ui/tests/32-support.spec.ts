import { test, expect } from '@playwright/test'
import { API, loginViaUi, watchForProblems } from './support/session'

/**
 * Support: a tenant member opens a ticket from the Support page, the platform
 * admin answers it (admin API, as the admin UI does), and the member sees the
 * answer on the ticket and under the bell.
 */

const ADMIN = { email: process.env.E2E_ADMIN_EMAIL || 'admin@example.com', password: process.env.E2E_ADMIN_PASSWORD || 'Change-Me-Now-123!' }

test('a ticket opened in the UI is answered by support and the asker is told', async ({ page, request }) => {
  test.setTimeout(120_000)
  const subject = `E2E support ${Date.now()}`
  await loginViaUi(page)
  const problems = watchForProblems(page)
  await page.goto('/support', { waitUntil: 'load' })
  await page.getByTestId('ticket-new').click()
  await page.getByTestId('ticket-subject').fill(subject)
  await page.getByTestId('ticket-text').fill('Batches of 1000 events take 5 s since Monday.')
  await page.getByTestId('ticket-submit').click()
  await expect(page.getByTestId('ticket-row').first()).toContainText(subject)
  await expect(page.getByTestId('ticket-row').first().getByTestId('ticket-status')).toHaveText('open')

  const login = await request.post(`${API}/v1/auth/login`, { data: ADMIN })
  expect(login.ok(), await login.text()).toBeTruthy()
  const admin = { Authorization: `Bearer ${(await login.json()).access_token}`, 'X-Customer-ID': 'platform' }
  const queue = await (await request.get(`${API}/v1/admin/support/tickets?status=open`, { headers: admin })).json()
  const ticket = queue.tickets.find((t: any) => t.subject === subject)
  expect(ticket, 'the ticket is in the admin queue').toBeTruthy()
  const answered = await request.post(`${API}/v1/admin/support/tickets/${ticket.id}/messages`,
    { headers: admin, data: { text: 'We added API workers; it should be back under 100 ms.' } })
  expect(answered.ok(), await answered.text()).toBeTruthy()

  await page.reload({ waitUntil: 'load' })
  await expect(page.getByTestId('ticket-row').first().getByTestId('ticket-status')).toHaveText('answered')
  await page.getByTestId('ticket-row').first().click()
  await expect(page.getByTestId('ticket-messages')).toContainText('We added API workers')
  await expect(page.getByTestId('inbox-unread')).toBeVisible()
  await page.getByTestId('ticket-close').click()
  await expect(page.getByTestId('ticket-row').first().getByTestId('ticket-status')).toHaveText('closed')
  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})
