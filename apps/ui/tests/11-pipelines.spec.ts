import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * Ingest pipelines (Phase 4): a user onboards a log format Logforge has never
 * seen, end to end in the UI: paste a sample, build a pipeline and test it
 * against the sample, save it, then find the new fields in the Log Explorer.
 * An event the pipeline cannot parse lands in its dead-letter queue with the
 * reason; nothing is lost.
 */

const n = Date.now()
const service = `orders-${n}`
const PROCESSORS = JSON.stringify([
  { grok: { field: 'msg', patterns: ['^order %{INT:order_id:int} %{WORD:action} by %{USERNAME:customer}$'] }, tag: 'parse' },
  { uppercase: { field: 'attrs.action' } },
], null, 2)

test('onboard an unknown log format: sample -> pipeline -> searchable fields', async ({ page, request }) => {
  test.setTimeout(150_000)
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/settings/pipelines', { waitUntil: 'load' })
  await page.getByTestId('pipeline-new').click()

  await page.getByTestId('pipeline-name').fill(service)
  await page.getByTestId('pipeline-services').fill(service)
  await page.getByTestId('pipeline-processors').fill(PROCESSORS)
  await page.getByTestId('pipeline-samples').fill('order 1001 paid by alice')
  await page.getByTestId('pipeline-simulate').click()
  const result = page.getByTestId('pipeline-result').first()
  await expect(result.getByTestId('pipeline-result-status')).toHaveText('ok')
  await expect(result.getByTestId('pipeline-result-changes')).toContainText('+ attrs.order_id = 1001')
  await expect(result.getByTestId('pipeline-result-changes')).toContainText('+ attrs.action = PAID')

  await page.getByTestId('pipeline-save').click()
  await expect(page).toHaveURL(new RegExp(`/settings/pipelines/${service}$`))
  await expect(page.getByTestId('pipeline-title')).toContainText(service)

  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const logs = [{ service, msg: `order ${n % 100000} refunded by bob` }, { service, msg: 'this line is not an order' }]
  const res = await request.post(`${API}/v1/ingest/logs/batch`, { headers, data: { logs } })
  expect(res.ok(), await res.text()).toBeTruthy()

  // The unparseable line waits in the dead-letter queue with the reason.
  await expect(async () => {
    await page.getByTestId('pipeline-tab-dlq').click()
    await expect(page.getByTestId('pipeline-dead-letter')).toHaveCount(1, { timeout: 2_000 })
  }).toPass({ timeout: 60_000, intervals: [2_000] })
  await expect(page.getByTestId('pipeline-dead-letter')).toContainText('no grok pattern matched msg')

  // The parsed field is searchable.
  await page.goto('/observability/logs', { waitUntil: 'load' })
  await page.getByRole('button', { name: 'LogQL' }).click()
  const query = page.getByPlaceholder(/LogforgeQL/)
  await expect(async () => {
    await query.fill(`| where attrs.order_id = ${n % 100000} | last 1h`)
    await page.getByTitle('Run (Cmd/Ctrl+Enter)').click()
    await expect(page.getByText(`order ${n % 100000} refunded by bob`).first()).toBeVisible({ timeout: 3_000 })
  }).toPass({ timeout: 60_000, intervals: [3_000] })

  expect(problems.failedApiCalls).toEqual([])
  expect(problems.pageErrors).toEqual([])
})
