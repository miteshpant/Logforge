import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/** Splitting alerts out of a case and merging cases, from the case page. */

const n = Date.now()

test('an analyst splits a case and merges another into it', async ({ page, request }) => {
  test.setTimeout(120_000)
  const problems = watchForProblems(page)
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const create = async (title: string, alert_ids: string[]) => {
    const r = await request.post(`${API}/v1/security/cases`, { headers, data: { title, severity: 'high', alert_ids } })
    expect(r.ok(), await r.text()).toBeTruthy()
    return (await r.json()).id as string
  }
  // two real alerts: reuse stored ones, or raise some with a burst of failed logins
  const alerts = async () => ((await (await request.get(`${API}/v1/security/events?limit=50`, { headers })).json()) as any[])
    .map(e => e.id)
  if ((await alerts()).length < 2) {
    const ip = `198.19.${n % 250}.${Math.floor(n / 250) % 250}`
    const logs = Array.from({ length: 10 }, (_, i) => ({ ts: new Date(Date.now() + i * 1000).toISOString(), service: 'sshd',
      level: 'warning', msg: 'authentication attempt', src_ip: ip, attrs: { event_type: 'authentication', result: 'failed', user: 'deploy' } }))
    expect((await request.post(`${API}/v1/ingest/logs/batch`, { headers, data: { logs } })).ok()).toBeTruthy()
    await expect(async () => expect((await alerts()).length).toBeGreaterThanOrEqual(2)).toPass({ timeout: 90_000, intervals: [2_000] })
  }
  const [a, b] = (await alerts()).slice(0, 2)
  const parent = await create(`E2E split parent ${n}`, [a, b])
  const other = await create(`E2E merge source ${n}`, [])

  await loginViaUi(page)
  await page.goto(`/security/cases/${parent}`, { waitUntil: 'load' })
  await expect(page.getByTestId('case-alert')).toHaveCount(2)
  await page.getByTestId('split-pick').first().check()
  await page.getByTestId('split-title').fill(`E2E split child ${n}`)
  await page.getByTestId('split-submit').click()
  await page.waitForURL(url => !url.pathname.endsWith(parent))
  const child = decodeURIComponent(page.url().split('/').pop() || '')
  await expect(page.getByTestId('case-alert')).toHaveCount(1)

  await page.getByTestId('merge-pick').selectOption(other)
  await page.getByTestId('merge-submit').click()
  await expect(page.getByTestId('merge-pick').locator(`option[value="${other}"]`)).toHaveCount(0)

  const source = await (await request.get(`${API}/v1/security/cases/${other}`, { headers })).json()
  expect(source.case.merged_into).toBe(child)
  const left = await (await request.get(`${API}/v1/security/cases/${parent}`, { headers })).json()
  expect(left.case.alert_ids).toHaveLength(1)
  expect(problems.pageErrors).toEqual([])
})
