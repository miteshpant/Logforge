import { test, expect, APIRequestContext } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * Content packs (Phase 7): a tenant admin installs the Web servers pack from
 * Settings, an nginx access line sent afterwards arrives parsed, and removing
 * the pack takes its objects away again.
 */

const PACK = 'web'
const n = Date.now()

async function headers(request: APIRequestContext) {
  const { token, tenantId } = await apiSession(request)
  return { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
}

async function removeIfInstalled(request: APIRequestContext) {
  const h = await headers(request)
  const detail = await (await request.get(`${API}/v1/packs/${PACK}`, { headers: h })).json()
  if (detail.installed) await request.delete(`${API}/v1/packs/${PACK}`, { headers: h })
}

function httpDate(d: Date) {
  const mon = d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' })
  const p = (x: number) => String(x).padStart(2, '0')
  return `${p(d.getUTCDate())}/${mon}/${d.getUTCFullYear()}:${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())} +0000`
}

test.beforeAll(async ({ request }) => removeIfInstalled(request))
test.afterAll(async ({ request }) => removeIfInstalled(request))

test('install a pack, ingest its source parsed, remove it', async ({ page, request }) => {
  test.setTimeout(180_000)
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/settings/packs', { waitUntil: 'load' })

  await expect(page.getByRole('heading', { level: 1, name: 'Content Packs' })).toBeVisible()
  await expect(page.getByTestId('pack-card')).toHaveCount(6)
  const card = page.getByTestId('pack-card').filter({ hasText: 'Web servers' })
  await expect(card.getByTestId('pack-status')).toHaveText('Not installed')
  await card.click()

  // The plan is shown before anything changes.
  await expect(page.getByRole('heading', { level: 1, name: /Web servers/ })).toBeVisible()
  await expect(page.getByTestId('plan-summary')).toHaveText(/^\d+ to create$/)
  await expect(page.getByTestId('plan-group-create')).toContainText('Web servers')
  await expect(page.getByTestId('pack-rule')).toHaveCount(3)

  await page.getByTestId('pack-install').click()
  await expect(page.getByTestId('pack-notice')).toContainText('Installed 1.0.0')
  await expect(page.getByTestId('pack-status')).toHaveText('Installed 1.0.0')
  await expect(page.getByTestId('plan-summary')).toHaveText(/unchanged: nothing to do/)

  // An access line sent with service nginx goes through the pack's pipeline.
  const h = await headers(request)
  const uri = `/e2e-pack-${n}`
  const line = `198.51.100.77 - - [${httpDate(new Date())}] "GET ${uri} HTTP/1.1" 404 12 "-" "curl/8.4.0" 0.003`
  await expect(async () => {
    const sent = await request.post(`${API}/v1/ingest/logs/batch`, {
      headers: h, data: { logs: [{ service: 'nginx', msg: line, level: 'info' }] } })
    expect(sent.ok(), await sent.text()).toBeTruthy()
    const r = await request.post(`${API}/v1/query/logql`, {
      headers: h, data: { query: `| where service = "nginx" and attrs.uri = "${uri}" | fields attrs.method, attrs.status_class, attrs.ocsf.class_uid | last 1h` } })
    const row = (await r.json()).logs?.[0]
    expect(row?.['attrs.method']).toBe('GET')
    expect(String(row?.['attrs.status_class'])).toBe('4xx')
  }).toPass({ timeout: 90_000, intervals: [5_000] })

  const dashboards = await (await request.get(`${API}/v1/dashboards`, { headers: h })).json()
  const list = dashboards.dashboards || dashboards.items || dashboards
  expect(JSON.stringify(list)).toContain('Web servers')

  await page.getByTestId('pack-remove').click()
  await page.getByTestId('pack-remove-confirm').click()
  await expect(page.getByTestId('pack-notice')).toContainText(/Removed \d+ objects/)
  await expect(page.getByTestId('pack-status')).toHaveText('Not installed')
  expect(problems.failedApiCalls).toEqual([])
  expect(problems.pageErrors).toEqual([])
})
