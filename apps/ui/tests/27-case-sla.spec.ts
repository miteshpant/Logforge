import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/** Per-tenant SLA targets: edited on the Cases page, used by the SLA overview. */

test.afterAll(async ({ request }) => {
  const { token, tenantId } = await apiSession(request)
  await request.put(`${API}/v1/security/cases/sla`, { headers: { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }, data: {} })
})

test('a tenant sets its own SLA targets', async ({ page, request }) => {
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/security/cases', { waitUntil: 'load' })
  await page.getByTestId('sla-toggle').click()
  const critical = page.getByTestId('sla-acknowledge-critical')
  await expect(critical).toHaveValue('15')
  await critical.fill('5')
  await page.getByTestId('sla-save').click()
  await expect(page.getByTestId('sla-message')).toContainText('Saved')

  const { token, tenantId } = await apiSession(request)
  const sla = await (await request.get(`${API}/v1/security/cases/sla`, { headers: { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId } })).json()
  expect(sla.overrides).toEqual({ acknowledge: { critical: 5 } })
  const metrics = await (await request.get(`${API}/v1/security/cases/metrics`, { headers: { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId } })).json()
  expect(metrics.sla_targets_minutes.acknowledge.critical).toBe(5)

  // acknowledging can't take longer than resolving
  await page.getByTestId('sla-acknowledge-low').fill('99999')
  await page.getByTestId('sla-save').click()
  await expect(page.getByTestId('sla-error')).toContainText("can't be longer than the resolve target")
  expect(problems.pageErrors).toEqual([])
})
