import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * Query builder and results (Phase 6): an analyst builds a stats query from
 * a form, sees the LogforgeQL it writes, and gets the answer as a table;
 * a timechart shows as a chart.
 */

const n = Date.now()
const service = `qb-${n}`

test.beforeAll(async ({ request }) => {
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const logs = [
    ...Array.from({ length: 5 }, (_, i) => ({ service, level: 'error', msg: `builder ${n} failure ${i}` })),
    ...Array.from({ length: 2 }, (_, i) => ({ service, level: 'warn', msg: `builder ${n} warning ${i}` })),
  ]
  const res = await request.post(`${API}/v1/ingest/logs/batch`, { headers, data: { logs } })
  expect(res.ok(), await res.text()).toBeTruthy()
  await expect(async () => {
    const r = await request.post(`${API}/v1/query/logql`, {
      headers, data: { query: `| where service = "${service}" | stats count() as n | last 1h` } })
    expect((await r.json()).logs?.[0]?.n).toBe(7)
  }).toPass({ timeout: 60_000, intervals: [2_000] })
})

test('build a query from the form and read the answer as a table and a chart', async ({ page }) => {
  test.setTimeout(120_000)
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/observability/logs', { waitUntil: 'load' })
  await page.getByRole('button', { name: 'LogQL', exact: true }).click()
  await page.getByTestId('builder-toggle').click()

  await page.getByTestId('builder-filter-field').fill('service')
  await page.getByTestId('builder-filter-value').fill(service)
  await page.getByTestId('builder-agg-as').fill('events')
  await page.getByTestId('builder-group-by').fill('level')
  await page.getByTestId('builder-sort').fill('-events')
  const expected = `| where service = "${service}" | stats count() as events by level | sort -events`
  await expect(page.getByTestId('builder-query')).toHaveText(expected)
  await page.getByTestId('builder-use').click()

  await expect(page.getByPlaceholder(/LogforgeQL/)).toHaveValue(expected)
  const table = page.getByTestId('query-results-table')
  await expect(table.locator('tbody tr')).toHaveCount(2, { timeout: 30_000 })
  await expect(table.locator('thead')).toContainText('events')
  await expect(table.locator('tbody tr').first()).toContainText('error')
  await expect(table.locator('tbody tr').first()).toContainText('5')

  // A timechart of the same events shows as a chart above its table.
  await page.getByPlaceholder(/LogforgeQL/).fill(`| where service = "${service}" | timechart span=5m count() by level`)
  await page.getByTestId('logs-refresh').click()
  await expect(page.getByTestId('query-results-chart').locator('.recharts-line')).toHaveCount(2, { timeout: 30_000 })

  expect(problems.failedApiCalls).toEqual([])
  expect(problems.pageErrors).toEqual([])
})
