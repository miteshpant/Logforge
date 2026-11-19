import { test, expect } from '@playwright/test'
import { loginViaUi, watchForProblems } from './support/session'

/**
 * AI foundation (Phase 8), as the stack ships: AI is off for the deployment
 * (config/ai.yml), so the AI page says why, a question gets the rule-based
 * answer marked as such, and nothing claims a model answered. Citation links
 * are deep links: the Log Explorer opens on the cited query.
 */

test('with AI off, the page says why and questions get the rule-based answer', async ({ page }) => {
  test.setTimeout(120_000)
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/settings/ai', { waitUntil: 'load' })

  await expect(page.getByRole('heading', { level: 1, name: 'AI' })).toBeVisible()
  await expect(page.getByTestId('ai-status-text')).toHaveText('AI answers are off')
  await expect(page.getByTestId('ai-status-reason')).toContainText('switched off for this deployment')
  // a tenant admin sees the settings, but there is no provider to choose
  await expect(page.getByTestId('ai-settings')).toBeVisible()
  await expect(page.getByTestId('ai-provider')).toBeDisabled()
  await expect(page.getByTestId('ai-enabled')).toBeDisabled()

  await expect(page.getByTestId('ai-audit')).toBeVisible()
  const requestsBefore = await page.getByTestId('ai-audit').locator('details').count()
  await page.getByTestId('ai-question').fill('How many errors were logged in the last hour?')
  await page.getByTestId('ai-ask').click()
  await expect(page.getByTestId('ai-answer')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('ai-provider-notice')).toHaveText('No model: rule-based answer')
  await expect(page.getByTestId('ai-fallback-reason')).toContainText('switched off')
  await expect(page.getByTestId('ai-answer-text')).not.toBeEmpty()
  await expect(page.getByTestId('ai-citation')).toHaveCount(0)
  // nothing went to a model, so the audit log gained no request
  await expect(page.getByTestId('ai-audit').locator('details')).toHaveCount(requestsBefore)
  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})

test('a citation link opens the Log Explorer on its query', async ({ page }) => {
  const problems = watchForProblems(page)
  await loginViaUi(page)
  const query = '| where level = "error" | stats count() as errors by service'
  const link = `/observability/logs?logql=${encodeURIComponent(query)}&since=24h`
  // from another site: the query is filled in but not run
  await page.goto(link, { waitUntil: 'load', referer: 'https://elsewhere.example/' })
  await expect(page.getByPlaceholder(/LogforgeQL/)).toHaveValue(query)
  await page.waitForTimeout(1500)
  await expect(page.getByTestId('query-results-table')).toHaveCount(0)
  // from Logforge (an AI citation): it runs
  const origin = new URL(page.url()).origin
  await page.goto(link, { waitUntil: 'load', referer: `${origin}/settings/ai` })
  await expect(page.getByPlaceholder(/LogforgeQL/)).toHaveValue(query)
  const table = page.getByTestId('query-results-table')
  await expect(table.locator('thead')).toContainText('errors', { timeout: 30_000 })
  await expect(table.locator('tbody tr').first()).toBeVisible()
  expect(problems.pageErrors).toEqual([])
})
