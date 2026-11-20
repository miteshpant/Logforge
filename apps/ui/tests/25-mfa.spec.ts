import { test, expect, Page } from '@playwright/test'
import { createHmac } from 'crypto'
import { API, apiSession, watchForProblems } from './support/session'

/**
 * Two-step sign-in (TOTP). A fresh user turns it on from Settings, then
 * signing in needs a code as well as the password; turning it off needs one too.
 */

function base32Decode(s: string): Buffer {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
  let bits = ''
  for (const c of s.replace(/=+$/, '').toUpperCase()) bits += alphabet.indexOf(c).toString(2).padStart(5, '0')
  const bytes = []
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2))
  return Buffer.from(bytes)
}

/** RFC 6238 code; `offset` steps from now, since a step can't be used twice. */
function totp(secret: string, offset = 0): string {
  const counter = Buffer.alloc(8)
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 1000 / 30) + offset))
  const h = createHmac('sha1', base32Decode(secret)).update(counter).digest()
  const o = h[h.length - 1] & 0xf
  return String((h.readUInt32BE(o) & 0x7fffffff) % 1_000_000).padStart(6, '0')
}

const email = `e2e-mfa-${Date.now()}@example.invalid`
const password = 'E2e-Mfa-Passw0rd!'

async function signIn(page: Page) {
  await page.goto('/login', { waitUntil: 'load' })
  await page.fill('[data-testid="email-input"]', email)
  await page.fill('[data-testid="password-input"]', password)
  await page.locator('[data-testid="login-button"]:not([disabled])').click()
}

test('a user turns on two-step sign-in and then needs a code', async ({ page, request }) => {
  test.setTimeout(120_000)
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const made = await request.post(`${API}/v1/users`, { headers, data: { name: 'E2E MFA', email, password, status: 'active' } })
  expect(made.ok(), await made.text()).toBeTruthy()
  const role = await request.post(`${API}/v1/users/${(await made.json()).id}/roles`, { headers, data: { tenant_id: tenantId, role: 'viewer' } })
  expect(role.ok(), await role.text()).toBeTruthy()

  // turn it on, from the account page the profile menu leads to
  await signIn(page)
  await page.waitForURL(/\/centrum$/)
  const problems0 = watchForProblems(page)
  await page.goto('/account', { waitUntil: 'load' })
  await expect(page.getByTestId('mfa-state')).toContainText('Off')
  await page.getByTestId('mfa-start').click()
  const secret = (await page.getByTestId('mfa-secret').textContent())!.trim()
  await page.getByTestId('mfa-confirm-code').fill(totp(secret))
  await page.getByTestId('mfa-confirm').click()
  await expect(page.getByTestId('mfa-backup-codes')).toBeVisible()
  const backup = (await page.getByTestId('mfa-backup-codes').locator('span').first().textContent())!.trim()
  await expect(page.getByTestId('mfa-state')).toContainText('On. 8 backup')
  expect(problems0.failedApiCalls).toEqual([])

  // the password alone no longer signs in
  await page.context().clearCookies()
  await page.evaluate(() => localStorage.clear())
  const problems = watchForProblems(page)
  await signIn(page)
  await expect(page.getByTestId('mfa-form')).toBeVisible()
  await page.getByTestId('mfa-code').fill('000000')
  await page.getByTestId('mfa-submit').click()
  await expect(page.getByTestId('mfa-error')).toContainText(/isn.t valid/)
  await page.getByTestId('mfa-code').fill(totp(secret, 1))
  await page.getByTestId('mfa-submit').click()
  await page.waitForURL(/\/centrum$/)
  expect(problems.failedApiCalls.filter(c => !c.includes('/v1/auth/login/mfa'))).toEqual([])

  // turn it off again with a backup code
  await page.goto('/account', { waitUntil: 'load' })
  await page.getByTestId('mfa-disable-code').fill(backup)
  await page.getByTestId('mfa-disable').click()
  await expect(page.getByTestId('mfa-state')).toContainText('Off')
})
