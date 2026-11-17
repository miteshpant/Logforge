import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * Log Explorer against a live stack: logs sent through the ingest API are
 * searchable, filterable by level, and expandable.
 *
 * Each run ingests logs under a unique service name, so runs never see each
 * other's data.
 */

const marker = `e2e-logs-${Date.now()}`

test.beforeAll(async ({ request }) => {
  const { token, tenantId } = await apiSession(request)
  const res = await request.post(`${API}/v1/ingest/logs/batch`, {
    headers: { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId },
    data: [
      { service: marker, level: 'info', msg: `${marker} checkout completed`, attrs: { order_id: `${marker}-42` } },
      { service: marker, level: 'error', msg: `${marker} payment declined`, attrs: { order_id: `${marker}-43` } },
    ],
  })
  expect(res.ok(), `ingest failed: ${res.status()} ${await res.text()}`).toBeTruthy()
})

async function openExplorerWithMarker(page: import('@playwright/test').Page) {
  await page.goto('/observability/logs', { waitUntil: 'load' })
  const search = page.getByPlaceholder('Filter loaded logs by message, service, trace ID, or metadata...')
  // Ingestion is asynchronous; refresh until the marked logs are searchable.
  await expect(async () => {
    await page.getByTestId('logs-refresh').click()
    await search.fill(marker)
    await expect(page.getByText(`${marker} payment declined`)).toBeVisible({ timeout: 2_000 })
  }).toPass({ timeout: 30_000 })
  return search
}

test('ingested logs are searchable in the Log Explorer', async ({ page }) => {
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await openExplorerWithMarker(page)

  await expect(page.getByText(`${marker} checkout completed`)).toBeVisible()
  await expect(page.getByText(`${marker} payment declined`)).toBeVisible()
  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})

test('the level filter narrows results to the selected level', async ({ page }) => {
  await loginViaUi(page)
  await openExplorerWithMarker(page)

  await page.getByRole('button', { name: 'error', exact: true }).click()

  await expect(page.getByText(`${marker} payment declined`)).toBeVisible()
  await expect(page.getByText(`${marker} checkout completed`)).toHaveCount(0)
})

test('expanding a log shows its attributes', async ({ page }) => {
  await loginViaUi(page)
  await openExplorerWithMarker(page)

  await page.getByText(`${marker} payment declined`).click()
  await expect(page.getByText(`${marker}-43`).first()).toBeVisible()
})
