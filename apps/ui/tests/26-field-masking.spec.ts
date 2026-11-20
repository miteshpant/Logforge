import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * Field-level masking. An admin makes a custom role that masks `email` and holds it:
 * a log's attrs.email then reads [masked], and a query naming the field is refused,
 * until the role is gone.
 */

const n = Date.now()
const name = `E2E masks email ${n}`
const service = `e2e-mask-${n}`

test.afterAll(async ({ request }) => {
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const roles = (await (await request.get(`${API}/v1/roles/custom`, { headers })).json()).roles || []
  for (const r of roles.filter((x: any) => x.name === name)) await request.delete(`${API}/v1/roles/custom/${r.id}`, { headers })
})

test('a role masking a field hides its values and refuses queries that name it', async ({ page, request }) => {
  test.setTimeout(120_000)
  const problems = watchForProblems(page)
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const me = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString()).user_id
  const ingest = await request.post(`${API}/v1/ingest/logs/batch`, { headers, data: { logs: [
    { service, level: 'info', msg: 'signup', attrs: { email: 'someone@example.com', plan: 'pro' } }] } })
  expect(ingest.ok(), await ingest.text()).toBeTruthy()

  const search = async () => {
    const end = new Date(Date.now() + 60_000); const start = new Date(end.getTime() - 3600_000)
    return request.post(`${API}/v1/query/logql`, { headers, data: {
      query: `| where service = "${service}"`, start_time: start.toISOString(), end_time: end.toISOString() } })
  }
  await expect.poll(async () => JSON.stringify(await (await search()).json()), { timeout: 30_000 })
    .toContain('someone@example.com')

  await loginViaUi(page)
  await page.goto('/settings/roles', { waitUntil: 'load' })
  await page.getByTestId('role-new').click()
  await page.getByTestId('role-name').fill(name)
  await page.getByTestId('role-masked').fill('email')
  await page.getByTestId('role-save').click()
  await expect(page.getByTestId('roles-message')).toContainText(`Saved ${name}`)
  const card = page.getByTestId(`role-${name}`)
  await expect(card).toContainText('masks email')
  expect(problems.failedApiCalls).toEqual([])

  const role = ((await (await request.get(`${API}/v1/roles/custom`, { headers })).json()).roles as any[]).find(r => r.name === name)
  expect((await request.put(`${API}/v1/roles/custom/${role.id}/members/${me}`, { headers, data: {} })).ok()).toBeTruthy()

  const masked = JSON.stringify(await (await search()).json())
  expect(masked).toContain('[masked]')
  expect(masked).not.toContain('someone@example.com')
  expect(masked).toContain('"plan":"pro"')
  const named = await request.post(`${API}/v1/query/logql`, { headers, data: { query: '| stats count() by attrs.email' } })
  expect(named.status()).toBe(403)

  expect((await request.delete(`${API}/v1/roles/custom/${role.id}`, { headers })).ok()).toBeTruthy()
  expect(JSON.stringify(await (await search()).json())).toContain('someone@example.com')
})
