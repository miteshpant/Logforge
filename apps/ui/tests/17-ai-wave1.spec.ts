import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * AI wave 1 (Phase 9), as the stack ships: AI is off for the deployment, so
 * every feature gives its reduced answer, marked as made without a model.
 *
 * * Log Explorer: a question becomes a rule-based LogforgeQL draft the user
 *   runs; any event can be explained (reference, rules, fields, queries).
 * * Cases and alerts: a triage summary built from the evidence, every
 *   sentence citing it.
 * * Pipeline editor: a pipeline drafted from pasted lines, simulated first.
 *
 * A burst of failed logins from a unique address gives the events to explain
 * and, through detection and case grouping, the case to triage.
 */

const n = Date.now()
const sourceIp = `198.18.${Math.floor(n / 1000) % 250}.${(n + 7) % 250}`
let caseId = ''

test.beforeAll(async ({ request }) => {
  test.setTimeout(120_000)
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const logs = Array.from({ length: 10 }, (_, i) => ({
    ts: new Date(n + i * 1000).toISOString(), service: 'sshd', level: 'warning', msg: 'authentication attempt',
    src_ip: sourceIp, attrs: { event_type: 'authentication', result: 'failed', user: 'deploy' },
  }))
  const res = await request.post(`${API}/v1/ingest/logs/batch`, { headers, data: { logs } })
  expect(res.ok(), `ingest failed: ${res.status()} ${await res.text()}`).toBeTruthy()
  await expect(async () => {
    const r = await request.get(`${API}/v1/security/cases?q=${sourceIp}`, { headers })
    const body = await r.json()
    expect(body.total).toBeGreaterThan(0)
    caseId = (body.cases || body.items)[0].id
  }).toPass({ timeout: 90_000, intervals: [2_000] })
})

test('a plain-English question becomes a query the user runs', async ({ page }) => {
  test.setTimeout(120_000)
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/observability/logs', { waitUntil: 'load' })
  await page.getByTestId('ask-query-input').fill('How many events did each service log in the last 24 hours?')
  await page.getByTestId('ask-query-run').click()
  const draft = page.getByTestId('ask-query-draft')
  await expect(draft).toBeVisible({ timeout: 30_000 })
  await expect(draft.getByTestId('ai-fallback')).toHaveText('Rule-based draft (AI off)')
  await expect(draft.getByTestId('ask-query-text')).toHaveText('| last 24h | stats count() as count by service')
  await expect(draft.getByTestId('ask-query-explanation')).not.toBeEmpty()
  await draft.getByTestId('ask-query-use').click()
  await expect(page.getByPlaceholder(/LogforgeQL/)).toHaveValue('| last 24h | stats count() as count by service')
  const table = page.getByTestId('query-results-table')
  await expect(table.locator('thead')).toContainText('count', { timeout: 30_000 })
  await expect(table.locator('tbody tr').first()).toBeVisible()
  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})

test('an event is explained, with fields and follow-up queries', async ({ page }) => {
  test.setTimeout(120_000)
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/observability/logs', { waitUntil: 'load' })
  await page.getByTestId('log-explain').first().click({ timeout: 30_000 })
  const panel = page.getByTestId('explain-panel')
  await panel.getByTestId('explain-run').click()
  await expect(panel.getByTestId('ai-sections')).toBeVisible({ timeout: 30_000 })
  await expect(panel.getByTestId('ai-fallback')).toHaveText('Built from the evidence, without AI')
  await expect(panel.getByTestId('ai-section-what')).toContainText('C1')
  await expect(panel.getByTestId('ai-sources').locator('li').first()).toContainText('event')
  await expect(panel.getByTestId('explain-queries').locator('li').first()).toBeVisible()
  // a follow-up query runs in the explorer
  await panel.getByTestId('explain-query').first().click()
  await expect(page.getByPlaceholder(/LogforgeQL/)).not.toHaveValue('')
  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})

test('a case gets a cited triage summary', async ({ page }) => {
  test.setTimeout(120_000)
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto(`/security/cases/${caseId}`, { waitUntil: 'load' })
  const panel = page.getByTestId('triage-panel')
  await expect(panel).toBeVisible({ timeout: 30_000 })
  await panel.getByTestId('triage-run').click()
  await expect(panel.getByTestId('ai-section-what_happened')).toBeVisible({ timeout: 30_000 })
  await expect(panel.getByTestId('ai-fallback')).toHaveText('Built from the evidence, without AI')
  for (const key of ['attack', 'entities', 'next_steps']) {
    await expect(panel.getByTestId(`ai-section-${key}`)).toBeVisible()
  }
  // every sentence cites, and every citation is a source listed below
  const sentences = panel.locator('[data-testid^="ai-section-"] li')
  const count = await sentences.count()
  expect(count).toBeGreaterThan(3)
  for (let i = 0; i < count; i++) {
    await expect(sentences.nth(i).getByTestId('ai-citation').first()).toBeVisible()
  }
  await expect(panel.getByTestId('ai-sources').locator('li').first()).toContainText('case')
  // the case's address, and its related activity: the burst ingested above
  await expect(panel.getByTestId('ai-section-entities')).toContainText(sourceIp)
  await expect(panel.getByTestId('ai-section-related')).toContainText(`${sourceIp} appears in`)
  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})

test('a pipeline is drafted from sample lines and simulated before it is offered', async ({ page }) => {
  test.setTimeout(120_000)
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/settings/pipelines/new', { waitUntil: 'load' })
  await page.getByTestId('pipeline-draft-samples').fill([
    'Nov 19 10:01:02 web-01 sshd[1201]: Accepted publickey for deploy from 10.0.1.20 port 51514 ssh2',
    'Nov 19 10:02:11 web-01 sshd[1205]: Failed password for root from 203.0.113.50 port 40112 ssh2',
  ].join('\n'))
  await page.getByTestId('pipeline-draft-run').click()
  const result = page.getByTestId('pipeline-draft-result')
  await expect(result).toBeVisible({ timeout: 30_000 })
  await expect(result.getByTestId('ai-fallback')).toHaveText('Heuristic draft, without AI')
  await expect(result.getByTestId('pipeline-draft-summary')).toContainText('Parsed 2 of 2 lines')
  await expect(result.getByTestId('pipeline-draft-fields')).toContainText('host')
  await result.getByTestId('pipeline-draft-use').click()
  await expect(page.getByTestId('pipeline-processors')).toHaveValue(/"syslog"/)
  // and the editor's own simulation agrees
  await page.getByTestId('pipeline-samples').fill(
    'Nov 19 10:02:11 web-01 sshd[1205]: Failed password for root from 203.0.113.50 port 40112 ssh2')
  await page.getByTestId('pipeline-simulate').click()
  await expect(page.getByTestId('pipeline-result').first().getByTestId('pipeline-result-status')).toHaveText('ok')
  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})
