import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * Storage and retention (Phase 12): the tiers, retention per data type, the
 * tenant's ingest and cost projection, and the archives (search in place,
 * rehydrate). A tenant admin changes the traces retention and puts it back.
 */

test('tiers, retention, costs and archives', async ({ page, request }) => {
  test.setTimeout(120_000)
  const problems = watchForProblems(page)
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const before = await (await request.get(`${API}/v1/storage/tiers`, { headers })).json()
  const traces = before.data_types.find((d: any) => d.data_type === 'traces')

  await loginViaUi(page)
  await page.goto('/settings/storage', { waitUntil: 'load' })
  await expect(page.getByTestId('storage-tiers')).toContainText('Hot', { timeout: 30_000 })
  await expect(page.getByTestId('storage-tiers')).toContainText('Parquet')
  await expect(page.getByTestId('retention-logs')).toContainText('days searchable')

  // change the traces retention, see it saved, then put it back
  await page.getByTestId('searchable-traces').fill(String(traces.searchable_days + 1))
  await page.getByTestId('save-traces').click()
  await expect(page.getByTestId('storage-message')).toContainText(`Traces ${traces.searchable_days + 1} days searchable`)
  await expect(page.getByTestId('retention-traces')).toContainText('your setting')
  const reset = await request.put(`${API}/v1/storage/tiers/policies/traces`,
    { headers, data: { searchable_days: traces.searchable_days, archive_days: traces.archive_days } })
  expect(reset.ok()).toBeTruthy()

  // costs: ingest by day and source, storage by tier, the projection
  await expect(page.getByTestId('ingest-chart')).toBeVisible()
  await expect(page.getByTestId('ingest-sources').locator('tbody tr').first()).toBeVisible()
  await expect(page.getByTestId('storage-by-tier')).toContainText('Logs')
  await expect(page.getByTestId('cost-projection')).toContainText('Storage per month')

  // an invalid retention is explained, not saved
  await page.getByTestId('searchable-logs').fill('30')
  await page.getByTestId('archive-logs').fill('10')
  await page.getByTestId('save-logs').click()
  await expect(page.getByTestId('storage-error')).toContainText('archive_days')

  // archives: searched in place (this tenant may have none yet), and rehydration answers
  await page.getByTestId('archive-search').click()
  await expect(page.getByTestId('archive-results')).toContainText('archived day(s) read', { timeout: 30_000 })
  await page.getByTestId('rehydrate').click()
  await expect(page.getByTestId('rehydrate-result')).toContainText('back until')

  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls.filter(c => !c.includes('/v1/storage/tiers/policies/logs'))).toEqual([])
})
