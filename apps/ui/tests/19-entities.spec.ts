import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * Entity analytics (Phase 11): the risk ranking, an entity's page (events,
 * risk and why, related entities), and log patterns in the Log Explorer.
 * A burst of failed logins from a unique address gives the entity.
 */

const n = Date.now()
const address = `198.18.${Math.floor(n / 1000) % 250}.${(n + 29) % 250}`
const host = `ent-${n}`

test.beforeAll(async ({ request }) => {
  test.setTimeout(120_000)
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const logs = Array.from({ length: 10 }, (_, i) => ({
    ts: new Date(n + i * 1000).toISOString(), service: 'sshd', level: 'warning', host,
    msg: `Failed password for deploy from ${address} port ${40000 + i} ssh2`,
    src_ip: address, user_id: 'deploy', attrs: { event_type: 'authentication', result: 'failed', user: 'deploy' },
  }))
  const res = await request.post(`${API}/v1/ingest/logs/batch`, { headers, data: { logs } })
  expect(res.ok(), `ingest failed: ${res.status()} ${await res.text()}`).toBeTruthy()
  await expect(async () => {
    const r = await request.get(`${API}/v1/entities/ip/${address}`, { headers })
    expect(r.status()).toBe(200)
  }).toPass({ timeout: 60_000, intervals: [2_000] })
})

test('the risk ranking lists entities and explains each score', async ({ page }) => {
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/security/entities', { waitUntil: 'load' })
  const rows = page.getByTestId('entity-risk-row')
  await expect(rows.first()).toBeVisible({ timeout: 30_000 })
  await expect(rows.first()).toContainText(/\d/)
  await page.getByTestId('entity-search').fill(address)
  await page.getByTestId('entity-search').press('Enter')
  await expect(page.getByTestId('entity-found')).toContainText(address, { timeout: 15_000 })
  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})

test("an entity's page: its events, and the entities seen with it", async ({ page }) => {
  test.setTimeout(90_000)
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto(`/security/entities/ip/${address}`, { waitUntil: 'load' })
  await expect(page.getByTestId('entity-value')).toHaveText(address, { timeout: 30_000 })
  await expect(page.getByTestId('entity-risk')).toBeVisible()
  await expect(page.getByTestId('entity-events').locator('li').first()).toContainText('Failed password', { timeout: 30_000 })
  const related = page.getByTestId('entity-related')
  await expect(related).toContainText(host)
  await expect(related).toContainText('deploy')
  await related.getByRole('link', { name: host }).click()
  await expect(page.getByTestId('entity-value')).toHaveText(host, { timeout: 30_000 })
  await expect(page.getByTestId('copilot-panel')).toBeVisible()
  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})

test('log patterns in the Log Explorer', async ({ page }) => {
  const problems = watchForProblems(page)
  await loginViaUi(page)
  const query = `| where host = "${host}" | patterns`
  const origin = new URL(page.url()).origin
  await page.goto(`/observability/logs?logql=${encodeURIComponent(query)}&since=24h`,
    { waitUntil: 'load', referer: `${origin}/observability/logs` })
  const table = page.getByTestId('query-results-table')
  await expect(table.locator('thead')).toContainText('pattern', { timeout: 30_000 })
  await expect(table.locator('tbody')).toContainText('Failed password for deploy from <*> port <*> ssh2')
  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})
