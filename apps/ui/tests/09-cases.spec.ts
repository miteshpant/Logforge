import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * Cases (Phase 2): an analyst goes from alert to case to evidence to
 * resolution without leaving the product.
 *
 * A burst of failed logins from a unique source address is ingested; the
 * detection engine raises alerts and case grouping opens a case for that
 * source on its own. The analyst then works the case in the UI.
 */

const n = Date.now()
const sourceIp = `198.18.${Math.floor(n / 1000) % 250}.${n % 250}`

test.beforeAll(async ({ request }) => {
  test.setTimeout(120_000)
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const start = Date.now()
  const logs = Array.from({ length: 10 }, (_, i) => ({
    ts: new Date(start + i * 1000).toISOString(), service: 'sshd', level: 'warning', msg: 'authentication attempt',
    src_ip: sourceIp, attrs: { event_type: 'authentication', result: 'failed', user: 'deploy' },
  }))
  const res = await request.post(`${API}/v1/ingest/logs/batch`, { headers, data: { logs } })
  expect(res.ok(), `ingest failed: ${res.status()} ${await res.text()}`).toBeTruthy()
  // Detection and grouping run asynchronously after ingest.
  await expect(async () => {
    const r = await request.get(`${API}/v1/security/cases?q=${sourceIp}`, { headers })
    expect((await r.json()).total).toBeGreaterThan(0)
  }).toPass({ timeout: 90_000, intervals: [2_000] })
})

test('an alert becomes a case the analyst investigates and resolves', async ({ page }) => {
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/security/cases', { waitUntil: 'load' })
  await expect(page.getByTestId('case-overview')).toBeVisible()
  await page.getByTestId('cases-search').fill(sourceIp)
  const row = page.getByTestId('case-row').filter({ hasText: sourceIp })
  await expect(row).toHaveCount(1)
  await row.getByRole('link').click()

  await expect(page.getByTestId('case-title')).toContainText(sourceIp)
  await expect(page.getByTestId('case-alert').first()).toContainText('Failed Login')
  await expect(page.getByTestId('case-entities')).toContainText(sourceIp)

  await page.getByTestId('comment-input').fill('@dana checking the source; looks like a password guess')
  await page.getByTestId('comment-post').click()
  await expect(page.locator('[data-kind="comment"]')).toContainText('password guess')

  await page.getByTestId('evidence-ref').fill(sourceIp)
  await page.getByTestId('evidence-title').fill('All logs from the source')
  await page.getByTestId('evidence-pin').click()
  const pinned = page.locator('[data-kind="evidence_pinned"]')
  await expect(pinned).toContainText('All logs from the source')
  await expect(pinned.getByRole('link')).toHaveAttribute('href', `/observability/logs?q=${encodeURIComponent(sourceIp)}`)

  await page.getByTestId('status-investigating').click()
  await expect(page.getByTestId('case-status')).toHaveText('investigating')
  await page.getByTestId('status-resolved').click()
  await page.getByTestId('close-reason').fill('Source blocked at the firewall; no successful login')
  await page.getByTestId('confirm-status').click()
  await expect(page.getByTestId('case-status')).toHaveText('resolved')
  await expect(page.getByTestId('case-close-reason')).toContainText('Source blocked')
  await expect(page.locator('[data-kind="status_changed"]')).toHaveCount(2)

  // The verdict reached the alerts.
  await expect(page.getByTestId('case-alert').first()).toContainText('resolved')
  expect(problems.failedApiCalls).toEqual([])
  expect(problems.pageErrors).toEqual([])
})

test('a case can be opened from an alert and from a log search', async ({ page }) => {
  const problems = watchForProblems(page)
  await loginViaUi(page)

  await page.goto('/security/events', { waitUntil: 'load' })
  await page.getByTestId('security-event-row').first().click()
  await page.getByTestId('create-case-from-alert').click()
  await expect(page).toHaveURL(/\/security\/cases\/[0-9a-f-]+$/)
  await expect(page.getByTestId('case-alert')).toHaveCount(1)

  await page.goto(`/observability/logs?q=${encodeURIComponent(sourceIp)}`, { waitUntil: 'load' })
  await expect(page.getByPlaceholder('Filter loaded logs by message, service, trace ID, or metadata...')).toHaveValue(sourceIp)
  await page.getByTestId('create-case-from-search').click()
  await expect(page).toHaveURL(/\/security\/cases\/[0-9a-f-]+$/)
  await expect(page.getByTestId('case-title')).toContainText(sourceIp)
  await expect(page.locator('[data-kind="evidence_pinned"]')).toContainText('Log Explorer search')

  expect(problems.failedApiCalls).toEqual([])
  expect(problems.pageErrors).toEqual([])
})
