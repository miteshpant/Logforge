import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * AI wave 2 (Phase 10), as the stack ships (AI off): the copilot plans and
 * runs searches the analyst approves, and pinning is the analyst's (and can
 * be taken back); a case report cites its sources; a drafted rule must pass
 * the gate, then is backtested and enabled.
 *
 * A burst of failed logins from a unique address gives the case.
 */

const n = Date.now()
const sourceIp = `198.18.${Math.floor(n / 1000) % 250}.${(n + 13) % 250}`
let caseId = ''

test.beforeAll(async ({ request }) => {
  test.setTimeout(120_000)
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const logs = Array.from({ length: 10 }, (_, i) => ({
    ts: new Date(n + i * 1000).toISOString(), service: 'sshd', level: 'warning',
    msg: `Failed password for deploy from ${sourceIp} port ${40000 + i} ssh2`,
    src_ip: sourceIp, attrs: { event_type: 'authentication', result: 'failed', user: 'deploy' },
  }))
  const res = await request.post(`${API}/v1/ingest/logs/batch`, { headers, data: { logs } })
  expect(res.ok(), `ingest failed: ${res.status()} ${await res.text()}`).toBeTruthy()
  await expect(async () => {
    const r = await request.get(`${API}/v1/security/cases?q=${sourceIp}`, { headers })
    const body = await r.json()
    expect(body.total).toBeGreaterThan(0)
    caseId = body.cases[0].id
  }).toPass({ timeout: 90_000, intervals: [2_000] })
})

test('the copilot plans, runs what the analyst keeps, and the analyst pins and takes back', async ({ page }) => {
  test.setTimeout(120_000)
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto(`/security/cases/${caseId}`, { waitUntil: 'load' })
  const panel = page.getByTestId('copilot-panel')
  await panel.getByTestId('copilot-plan').click()
  const steps = panel.getByTestId('copilot-step')
  await expect(steps.first()).toBeVisible({ timeout: 30_000 })
  expect(await steps.count()).toBeGreaterThan(1)
  await expect(panel.getByTestId('copilot-steps')).toContainText(`What else did ${sourceIp} touch?`)
  await panel.getByTestId('copilot-run').click()
  const timeline = panel.getByTestId('copilot-timeline')
  await expect(timeline.getByTestId('copilot-event').first()).toBeVisible({ timeout: 30_000 })
  await expect(timeline).toContainText(sourceIp)
  await expect(panel.getByTestId('ai-fallback')).toHaveText('Built from the evidence, without AI')
  // nothing was pinned by the copilot itself
  await expect(page.getByTestId('evidence-item')).toHaveCount(0)
  await timeline.getByTestId('copilot-pin').first().click()
  await expect(page.getByTestId('evidence-item')).toHaveCount(1, { timeout: 15_000 })
  await page.getByTestId('evidence-unpin').first().click()
  await expect(page.getByTestId('evidence-item')).toHaveCount(0, { timeout: 15_000 })
  await expect(page.locator('[data-testid="timeline-item"][data-kind="evidence_unpinned"]')).toHaveCount(1)
  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})

test('a post-incident review cites the case', async ({ page }) => {
  test.setTimeout(120_000)
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto(`/security/cases/${caseId}`, { waitUntil: 'load' })
  const panel = page.getByTestId('case-report-panel')
  await panel.getByTestId('case-report-audience').selectOption('review')
  await panel.getByTestId('case-report-run').click()
  await expect(panel.getByTestId('case-report-title')).toContainText('Post-incident review', { timeout: 30_000 })
  await expect(panel.getByTestId('ai-section-detection')).toBeVisible()
  const sentences = panel.locator('[data-testid^="ai-section-"] li')
  const count = await sentences.count()
  expect(count).toBeGreaterThan(2)
  for (let i = 0; i < count; i++) await expect(sentences.nth(i).getByTestId('ai-citation').first()).toBeVisible()
  await expect(panel.getByTestId('case-report-download')).toBeVisible()
  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})

test('a drafted rule must pass the gate, then is backtested and enabled', async ({ page }) => {
  test.setTimeout(120_000)
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/security/rules', { waitUntil: 'load' })
  await page.getByTestId('rule-draft-toggle').click()
  const panel = page.getByTestId('rule-draft')
  const host = `ws-${n}`
  await panel.getByTestId('rule-draft-description').fill('Volume shadow copies deleted, as ransomware does')
  await panel.getByTestId('rule-draft-technique').fill('T1490')
  await panel.getByTestId('rule-draft-samples').fill([
    JSON.stringify({ event_type: 'process_creation', process_name: 'vssadmin.exe',
      command_line: 'vssadmin.exe delete shadows /all /quiet', hostname: host }),
    JSON.stringify({ event_type: 'process_creation', process_name: 'vssadmin.exe',
      command_line: 'vssadmin delete shadows /for=C: /quiet', hostname: host }),
  ].join('\n'))
  await panel.getByTestId('rule-draft-known-good').fill(JSON.stringify({ event_type: 'process_creation',
    process_name: 'vssadmin.exe', command_line: 'vssadmin.exe list shadows', hostname: host }))
  await panel.getByTestId('rule-draft-run').click()
  await expect(panel.getByTestId('rule-draft-attempts')).toContainText('passed the gate', { timeout: 30_000 })
  await expect(panel.getByTestId('rule-draft-yaml')).toContainText('attack.t1490')
  await panel.getByTestId('rule-draft-enable').click()
  await expect(panel.getByTestId('rule-draft-enabled')).toContainText('Enabled ai_', { timeout: 60_000 })
  await expect(panel.getByTestId('rule-draft-enable')).toBeDisabled()
  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})
