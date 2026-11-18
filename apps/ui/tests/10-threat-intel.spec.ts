import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * Threat intelligence (Phase 3): an indicator added for the tenant is
 * matched against new events at ingest, raised as an intel alert, and shown
 * with how often it was seen in the tenant's logs.
 */

const n = Date.now()
const c2Domain = `c2-${n}.badactor.example`
const manual = `drop-${n}.phish.example`

test.beforeAll(async ({ request }) => {
  test.setTimeout(120_000)
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const added = await request.post(`${API}/v1/security/intel/indicators`, {
    headers, data: { value: c2Domain, threat_type: 'botnet_cc', confidence: 90, tags: ['e2e'] },
  })
  expect(added.status(), await added.text()).toBe(201)
  const logs = [{
    ts: new Date().toISOString(), service: 'dns', level: 'info', msg: 'query', src_ip: '10.0.1.15',
    attrs: { query: `beacon.${c2Domain}`, event_type: 'dns' },
  }]
  const res = await request.post(`${API}/v1/ingest/logs/batch`, { headers, data: { logs } })
  expect(res.ok(), `ingest failed: ${res.status()} ${await res.text()}`).toBeTruthy()
  await expect(async () => {
    const r = await request.get(`${API}/v1/security/events?limit=200`, { headers })
    const events = await r.json()
    expect(events.some((e: any) => e.rule_id.includes('lf-ti-known-c2') && e.threat)).toBeTruthy()
  }).toPass({ timeout: 90_000, intervals: [2_000] })
})

test('an indicator is matched at ingest and searchable with its sightings', async ({ page }) => {
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/security/threat-intel', { waitUntil: 'load' })

  await page.getByTestId('intel-search').fill(c2Domain)
  const row = page.getByTestId('intel-indicator').filter({ hasText: c2Domain })
  await expect(row).toHaveCount(1)
  await expect(row).toContainText('botnet cc')
  await expect(row.getByTestId('intel-seen')).not.toHaveText('0')

  // Add and remove an indicator by hand; defanged input is accepted.
  await page.getByTestId('intel-new-value').fill(manual.replace(/\./g, '[.]'))
  await page.getByTestId('intel-add').click()
  await expect(page.getByTestId('intel-notice')).toContainText(manual)
  await page.getByTestId('intel-search').fill(manual)
  await expect(page.getByTestId('intel-indicator').filter({ hasText: manual })).toHaveCount(1)
  await page.getByRole('button', { name: `Delete ${manual}` }).click()
  await expect(page.getByTestId('intel-indicator').filter({ hasText: manual })).toHaveCount(0)

  await page.getByTestId('intel-tab-feeds').click()
  await expect(page.getByText('abuse.ch Feodo Tracker').first()).toBeVisible()

  await page.goto('/security/events', { waitUntil: 'load' })
  await expect(page.getByTestId('intel-badge').first()).toContainText('Known botnet C2')
  expect(problems.failedApiCalls).toEqual([])
  expect(problems.pageErrors).toEqual([])
})
