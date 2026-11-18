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
 */
const path = require('path')
const { chromium } = require(require.resolve('playwright', { paths: [path.join(__dirname, '..', 'apps', 'ui')] }))

const UI = process.env.UI_URL || 'http://localhost:3001'
const OUT = path.join(__dirname, '..', 'docs', 'images')
const EMAIL = process.env.E2E_EMAIL || 'dana@acme.example'
const PASSWORD = process.env.E2E_PASSWORD || 'Acme-Demo-Pass-123!'

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
    await page.screenshot({ path: path.join(OUT, `${name}.png`) })
    console.log(`${name}.png`)
  }

  // The case an analyst is working (seeded by seed_demo_telemetry.py).
  await page.goto(`${UI}/security/cases`, { waitUntil: 'load' })
  const worked = page.getByTestId('case-row').filter({ hasText: 'investigating' }).first()
  await worked.getByRole('link').click()
  await page.getByTestId('timeline-item').first().waitFor()
  await page.waitForTimeout(2000)
  await page.screenshot({ path: path.join(OUT, 'case-detail.png') })
  console.log('case-detail.png')

  await browser.close()
  if (errors.length) {
    console.error('page errors:', errors)
    process.exit(1)
  }
}

main().catch(e => { console.error(e); process.exit(1) })
