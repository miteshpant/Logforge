import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * Custom roles and data scopes (Phase 14). An admin makes a role that limits
 * logs to one service and adds themself to it: their queries then see only
 * that service, until they leave the role.
 */

const n = Date.now()
const name = `E2E auth only ${n}`

test.describe.configure({ mode: 'serial' })

test.afterAll(async ({ request }) => {
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const roles = (await (await request.get(`${API}/v1/roles/custom`, { headers })).json()).roles || []
  for (const r of roles.filter((x: any) => x.name === name)) await request.delete(`${API}/v1/roles/custom/${r.id}`, { headers })
})

test('a scoped custom role limits what its holder can query', async ({ page, request }) => {
  test.setTimeout(120_000)
  const problems = watchForProblems(page)
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const me = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString()).user_id
  const services = async () => {
    const end = new Date(); const start = new Date(end.getTime() - 30 * 86400_000)
    const r = await request.post(`${API}/v1/query/logql`, { headers, data: {
      query: '| stats count() by service', start_time: start.toISOString(), end_time: end.toISOString() } })
    expect(r.ok(), await r.text()).toBeTruthy()
    const body = await r.json()
    return new Set((body.logs || body.rows || []).map((row: any) => row.service))
  }
  const before = await services()
  expect(before.size).toBeGreaterThan(1)

  await loginViaUi(page)
  await page.goto('/settings/roles', { waitUntil: 'load' })
  await page.getByTestId('role-new').click()
  // nothing granted and no scope: refused
  await page.getByTestId('role-name').fill(name)
  await page.getByTestId('role-save').click()
  await expect(page.getByTestId('roles-error')).toContainText('permissions, a data scope, or both')
  await page.getByTestId('role-scoped').check()
  await page.getByTestId('role-services').fill('auth')
  await page.getByTestId('grant-reports').selectOption('read')
  await page.getByTestId('role-save').click()
  await expect(page.getByTestId('roles-message')).toContainText(`Saved ${name}`)
  const card = page.getByTestId(`role-${name}`)
  await expect(card).toContainText('logs of auth')
  await expect(card).toContainText('reports:read')

  await card.getByTestId(`role-add-${name}`).selectOption(me)
  await card.getByTestId(`role-add-confirm-${name}`).click()
  await expect(card.getByTestId('role-member')).toHaveCount(1)
  expect([...(await services())]).toEqual(['auth'])
  const access = await (await request.get(`${API}/v1/auth/access`, { headers })).json()
  expect(access.data_scope).toEqual({ services: ['auth'] })

  await card.getByTestId('role-member').getByRole('button', { name: 'Remove' }).click()
  await expect(card.getByTestId('role-member')).toHaveCount(0)
  expect((await services()).size).toBe(before.size)
  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls.filter(c => !c.includes('/v1/roles/custom'))).toEqual([])
})
