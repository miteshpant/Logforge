#!/usr/bin/env node
/**
 * Capture the README screenshots (docs/images/*.png) from a running UI.
 *
 *   python scripts/bootstrap_demo.py
 *   python scripts/seed_demo_telemetry.py
 *   node scripts/capture_screenshots.js            # UI at http://localhost:3001
 *   UI_URL=http://localhost:3000 node scripts/capture_screenshots.js
 *
 * Needs Playwright (`npm ci` in apps/ui). Logs in as the demo user, opens each
 * page, waits for its data, and writes 1440x900 PNGs. A page that shows an
 * error or no data is reported, so a broken page never becomes a screenshot.
 * SHOTS=log-explorer,ai-triage writes only those (the others still load).
 */
const path = require('path')
const { chromium } = require(require.resolve('playwright', { paths: [path.join(__dirname, '..', 'apps', 'ui')] }))

const UI = process.env.UI_URL || 'http://localhost:3001'
const OUT = path.join(__dirname, '..', 'docs', 'images')
const EMAIL = process.env.E2E_EMAIL || 'dana@acme.example'
const PASSWORD = process.env.E2E_PASSWORD || 'Acme-Demo-Pass-123!'
const ONLY = new Set((process.env.SHOTS || '').split(',').map(s => s.trim()).filter(Boolean))

// name -> page and an element that proves its data loaded
const PAGES = [
  ['centrum', '/centrum', 'main'],
  ['log-explorer', '/observability/logs', 'table, [data-testid="logs-refresh"]'],
  ['tracing', '/observability/traces', 'main'],
  ['apm', '/observability/apm', 'main'],
  ['service-map', '/observability/service-map', 'main'],
  ['detection-rules', '/security/rules', 'main'],
  ['cases', '/security/cases', '[data-testid="case-row"]'],
  ['threat-intel', '/security/threat-intel', '[data-testid="intel-indicator"]'],
]

async function shot(page, name) {
  if (ONLY.size && !ONLY.has(name)) return
  await page.screenshot({ path: path.join(OUT, `${name}.png`) })
  console.log(`${name}.png`)
}

async function main() {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', e => errors.push(e.message))

  await page.goto(`${UI}/login`, { waitUntil: 'load' })
  await page.screenshot({ path: path.join(OUT, 'login.png') })
  await page.fill('[data-testid="email-input"]', EMAIL)
  await page.fill('[data-testid="password-input"]', PASSWORD)
  await page.locator('[data-testid="login-button"]:not([disabled])').click()
  await page.waitForURL(url => !url.pathname.startsWith('/login'), { timeout: 30000 })

  for (const [name, route, ready] of PAGES) {
    await page.goto(`${UI}${route}`, { waitUntil: 'load' })
    await page.locator(ready).first().waitFor({ timeout: 20000 })
    await page.waitForTimeout(3000) // data loads, charts animate in (pages poll, so no networkidle)
    await shot(page, name)
  }

  // The Log Explorer's field explorer, on a common-schema field.
  await page.goto(`${UI}/observability/logs`, { waitUntil: 'load' })
  await page.locator('[data-testid="logs-refresh"]').first().waitFor()
  await page.getByTestId('fields-toggle').click()
  await page.getByTestId('field-search').fill('user.name')
  const userField = page.locator('[data-testid="field-row"][data-field="ocsf.actor.user.name"]')
  await userField.waitFor({ timeout: 20000 })
  await userField.getByRole('button').first().click()
  await userField.getByTestId('field-value').first().waitFor()
  await page.waitForTimeout(1500)
  await shot(page, 'field-explorer')

  // The pipeline editor testing a sample (seeded by seed_demo_telemetry.py).
  await page.goto(`${UI}/settings/pipelines/payments-gateway`, { waitUntil: 'load' })
  await page.getByTestId('pipeline-samples').waitFor()
  await page.getByTestId('pipeline-samples').fill(
    'txn=TX9001 amount=42.50 currency=EUR status=DECLINED card=4111-1111-1111-1111 customer=dana@acme.example gateway=edge-1')
  await page.getByTestId('pipeline-simulate').click()
  await page.getByTestId('pipeline-result-changes').first().waitFor()
  await page.waitForTimeout(1000)
  await shot(page, 'pipelines')

  // LogforgeQL analytics (Phase 6): the query builder, then a timechart's results.
  await page.goto(`${UI}/observability/logs`, { waitUntil: 'load' })
  await page.getByRole('button', { name: 'LogQL', exact: true }).click()
  await page.getByTestId('builder-toggle').click()
  await page.getByTestId('builder-filter-field').fill('level')
  await page.getByTestId('builder-filter-value').fill('error')
  await page.getByTestId('builder-agg-as').fill('errors')
  await page.locator('button', { hasText: 'calculation' }).click()
  await page.getByTestId('builder-agg-fn').nth(1).selectOption('dc')
  await page.getByTestId('builder-agg-field').nth(1).fill('host')
  await page.getByTestId('builder-agg-as').nth(1).fill('hosts')
  await page.getByTestId('builder-group-by').fill('service')
  await page.getByTestId('builder-sort').fill('-errors')
  await page.waitForTimeout(500)
  await shot(page, 'query-builder')
  await page.getByTestId('builder-use').click()
  await page.getByPlaceholder(/LogforgeQL/).fill('| where level in ["error", "warn"] | timechart span=5m count() by service')
  await page.getByTestId('logs-refresh').click()
  await page.getByTestId('query-results-chart').locator('.recharts-line').first().waitFor({ timeout: 20000 })
  await page.waitForTimeout(1500)
  await shot(page, 'query-results')

  // A dashboard built from queries, with variables (seeded by seed_demo_telemetry.py).
  await page.goto(`${UI}/dashboards`, { waitUntil: 'load' })
  await page.getByText('Service health').first().click()
  await page.getByTestId('dashboard-variables').waitFor({ timeout: 20000 })
  await page.locator('.recharts-line').first().waitFor({ timeout: 20000 })
  await page.waitForTimeout(2500)
  await shot(page, 'dashboard-queries')

  // The case an analyst is working (seeded by seed_demo_telemetry.py).
  await page.goto(`${UI}/security/cases`, { waitUntil: 'load' })
  const worked = page.getByTestId('case-row').filter({ hasText: 'investigating' }).first()
  await worked.getByRole('link').click()
  await page.getByTestId('timeline-item').first().waitFor()
  await page.waitForTimeout(2000)
  await shot(page, 'case-detail')

  // Content packs: the catalogue, and what installing the AWS pack would add.
  await page.goto(`${UI}/settings/packs`, { waitUntil: 'load' })
  await page.getByTestId('pack-card').nth(5).waitFor({ timeout: 20000 })
  await page.waitForTimeout(1000)
  await shot(page, 'content-packs')
  await page.goto(`${UI}/settings/packs/aws`, { waitUntil: 'load' })
  await page.getByTestId('plan-group-create').waitFor({ timeout: 20000 })
  await page.waitForTimeout(1000)
  await shot(page, 'content-pack')

  // AI wave 1 (Phase 9), as the stack ships: AI off, so each answer is the reduced one, marked as such.
  await page.goto(`${UI}/observability/logs`, { waitUntil: 'load' })
  await page.getByTestId('ask-query-input').fill('How many events did each service log in the last 24 hours?')
  await page.getByTestId('ask-query-run').click()
  await page.getByTestId('ask-query-use').click()
  await page.getByTestId('query-results-table').locator('tbody tr').first().waitFor({ timeout: 20000 })
  await page.waitForTimeout(1500)
  await shot(page, 'ai-ask-query')

  const sshFailures = '| where service = "sshd" and msg contains "Failed password" | head 50'
  await page.goto(`${UI}/observability/logs?logql=${encodeURIComponent(sshFailures)}&since=7d`,
    { waitUntil: 'load', referer: `${UI}/observability/logs` })
  await page.getByTestId('log-explain').first().click({ timeout: 20000 })
  await page.getByTestId('explain-run').click()
  await page.getByTestId('explain-fields').waitFor({ timeout: 20000 })
  await page.waitForTimeout(800)
  await shot(page, 'ai-explain')

  await page.goto(`${UI}/security/cases`, { waitUntil: 'load' })
  await page.getByTestId('case-row').filter({ hasText: 'investigating' }).first().getByRole('link').click()
  await page.getByTestId('triage-run').click()
  await page.getByTestId('ai-section-next_steps').waitFor({ timeout: 20000 })
  await page.getByTestId('triage-panel').scrollIntoViewIfNeeded()
  await page.waitForTimeout(800)
  await shot(page, 'ai-triage')

  await page.goto(`${UI}/settings/pipelines/new`, { waitUntil: 'load' })
  await page.getByTestId('pipeline-draft-samples').fill([
    '2 123456789012 eni-0a1b2c3d 203.0.113.14 10.0.1.25 51544 22 6 12 4210 1795086000 1795086060 ACCEPT OK',
    '2 123456789012 eni-0a1b2c3d 10.0.1.25 198.51.100.9 443 50122 6 40 98012 1795086000 1795086060 ACCEPT OK',
    '2 123456789012 eni-0a1b2c3d 192.0.2.77 10.0.1.25 0 0 1 1 84 1795086060 1795086120 REJECT OK',
  ].join('\n'))
  await page.getByTestId('pipeline-draft-run').click()
  await page.getByTestId('pipeline-draft-fields').waitFor({ timeout: 20000 })
  await page.getByTestId('pipeline-draft').scrollIntoViewIfNeeded()
  await page.waitForTimeout(800)
  await shot(page, 'ai-pipeline-draft')

  await browser.close()
  if (errors.length) {
    console.error('page errors:', errors)
    process.exit(1)
  }
}

main().catch(e => { console.error(e); process.exit(1) })
