import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * "Create case" wherever a security alert is shown: from the SIEM
 * dashboard's recent alerts, a case opens with the alert attached.
 */

test('a case is opened from an alert on the SIEM dashboard', async ({ page, request }) => {
  test.setTimeout(120_000)
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const open = async () => ((await (await request.get(`${API}/v1/security/dashboard`, { headers })).json()).recent_events as any[] || [])
    .filter(e => e.status !== 'resolved' && e.status !== 'false_positive')
  if ((await open()).length === 0) {
    const n = Date.now()
    const ip = `198.18.${n % 250}.${Math.floor(n / 250) % 250}`
    const logs = Array.from({ length: 10 }, (_, i) => ({ ts: new Date(Date.now() + i * 1000).toISOString(), service: 'sshd',
      level: 'warning', msg: 'authentication attempt', src_ip: ip, attrs: { event_type: 'authentication', result: 'failed', user: 'deploy' } }))
    expect((await request.post(`${API}/v1/ingest/logs/batch`, { headers, data: { logs } })).ok()).toBeTruthy()
    await expect(async () => expect((await open()).length).toBeGreaterThan(0)).toPass({ timeout: 90_000, intervals: [2_000] })
  }

  await loginViaUi(page)
  const problems = watchForProblems(page)
  await page.goto('/security/siem', { waitUntil: 'load' })
  const button = page.getByTestId('siem-create-case').first()
  await expect(button).toBeVisible({ timeout: 60_000 })
  await button.click()
  await page.waitForURL(/\/security\/cases\/[^/]+$/, { timeout: 30_000 })
  const caseId = decodeURIComponent(page.url().split('/').pop() || '')
  const made = await (await request.get(`${API}/v1/security/cases/${encodeURIComponent(caseId)}`, { headers })).json()
  expect((made.case || made).alert_ids.length).toBe(1)
  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])
})
