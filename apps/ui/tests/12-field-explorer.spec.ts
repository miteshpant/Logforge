import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * Field explorer (Phase 5): a user finds a field they never configured in
 * the Log Explorer's field sidebar, sees its top values, and adds one to the
 * query with a click.
 */

const n = Date.now()
const region = `eu-test-${n}`

test.beforeAll(async ({ request }) => {
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const logs = Array.from({ length: 6 }, (_, i) => ({
    service: 'fx-checkout', msg: `checkout ${n}-${i} in ${i < 4 ? region : 'us-east'}`,
    attrs: { deployment: { region: i < 4 ? region : 'us-east' }, order_total: 10 + i },
  }))
  const res = await request.post(`${API}/v1/ingest/logs/batch`, { headers, data: { logs } })
  expect(res.ok(), await res.text()).toBeTruthy()
  await expect(async () => {
    const r = await request.post(`${API}/v1/query/logql`, {
      headers, data: { query: `| where attrs.deployment.region = "${region}" | last 1h` } })
    expect((await r.json()).logs?.length).toBe(4)
  }).toPass({ timeout: 60_000, intervals: [2_000] })
})

test('find a field, see its values, add one to the query', async ({ page }) => {
  test.setTimeout(120_000)
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/observability/logs', { waitUntil: 'load' })
  await page.getByTestId('fields-toggle').click()
  await expect(page.getByTestId('field-sidebar')).toBeVisible()
  await page.getByTestId('field-search').fill('deployment.region')
  const field = page.locator('[data-testid="field-row"][data-field="attrs.deployment.region"]')
  await expect(field).toBeVisible({ timeout: 70_000 })  // the catalogue is cached for up to 60 s
  await field.getByRole('button').first().click()
  const value = field.getByTestId('field-value').filter({ hasText: region })
  await expect(value).toContainText('4')
  await value.getByTestId('field-value-add').click()

  await expect(page.getByPlaceholder(/LogforgeQL/)).toHaveValue(`| where attrs.deployment.region = "${region}"`)
  await expect(page.getByText(`checkout ${n}-0 in ${region}`)).toBeVisible()
  await expect(page.getByText(`checkout ${n}-5 in us-east`)).toHaveCount(0)
  expect(problems.failedApiCalls).toEqual([])
  expect(problems.pageErrors).toEqual([])
})
