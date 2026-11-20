import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * Dashboards from queries (Phase 6): an analyst writes a LogforgeQL query,
 * adds it to a new dashboard as a chart, and filters the dashboard with a
 * variable.
 */

const n = Date.now()
const services = [`dq-api-${n}`, `dq-web-${n}`]

test.beforeAll(async ({ request }) => {
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const logs = Array.from({ length: 9 }, (_, i) => ({
    service: services[i % 3 === 0 ? 1 : 0], level: 'error', msg: `dashboard query ${n}-${i}`,
  }))
  const res = await request.post(`${API}/v1/ingest/logs/batch`, { headers, data: { logs } })
  expect(res.ok(), await res.text()).toBeTruthy()
  await expect(async () => {
    const r = await request.post(`${API}/v1/query/logql`, {
      headers, data: { query: `"dashboard query ${n}" | stats count() as n | last 1h` } })
    expect((await r.json()).logs?.[0]?.n).toBe(9)
  }).toPass({ timeout: 60_000, intervals: [2_000] })
})

test('a query becomes a dashboard panel, filtered by a variable', async ({ page, request }) => {
  test.setTimeout(150_000)
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/observability/logs', { waitUntil: 'load' })
  await page.getByRole('button', { name: 'LogQL', exact: true }).click()
  const query = `"dashboard query ${n}" | where service = $service | stats count() as errors by service`

  // The panel's query uses $service, so the dashboard needs the variable first.
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const created = await request.post(`${API}/v1/dashboards`, {
    headers, data: { name: `Errors ${n}`, widgets: [], variables: [
      { name: 'service', label: 'Service', type: 'custom', values: services, include_all: true, default: '*' }] } })
  expect(created.ok(), await created.text()).toBeTruthy()
  const dashboardId = (await created.json()).dashboard_id

  await page.getByPlaceholder(/LogforgeQL/).fill(query)
  await page.getByTestId('add-to-dashboard').click()
  await page.getByTestId('panel-dashboard').selectOption(dashboardId)
  await page.getByTestId('panel-name').fill('Errors by service')
  await expect(page.getByTestId('panel-type')).toHaveValue('table')  // no result yet: a table
  await page.getByTestId('panel-type').selectOption('bar_chart')
  await page.getByTestId('panel-save').click()
  await page.getByTestId('open-dashboard').click()

  await expect(page.getByRole('heading', { name: `Errors ${n}` })).toBeVisible()
  await expect(page.getByText('Errors by service')).toBeVisible()
  const bars = page.locator('.recharts-bar-rectangle')
  await expect(bars).toHaveCount(2, { timeout: 30_000 })   // All: both services

  await page.getByTestId('dashboard-variable-service').selectOption(services[1])
  await expect(bars).toHaveCount(1, { timeout: 30_000 })
  await bars.first().hover()
  await expect(page.locator('.recharts-tooltip-wrapper')).toContainText(services[1])

  expect(problems.failedApiCalls).toEqual([])
  expect(problems.pageErrors).toEqual([])
})
