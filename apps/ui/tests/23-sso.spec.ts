import { test, expect } from '@playwright/test'
import { API, apiSession, loginViaUi, watchForProblems } from './support/session'

/**
 * Single sign-on (Phase 14). A tenant admin adds an OIDC provider; a user
 * of its domain chooses single sign-on and is sent through the API to the
 * IdP. The IdP here is a .invalid host, so the start fails and the sign-in
 * page says why. The IdP round trip itself (code, ID token, roles) is
 * covered by tests/test_sso_api.py against a mock IdP.
 */

const n = Date.now()
const domain = `sso-${n}.example`
const name = `E2E IdP ${n}`

test.afterAll(async ({ request }) => {
  const { token, tenantId } = await apiSession(request)
  const headers = { Authorization: `Bearer ${token}`, 'X-Customer-ID': tenantId }
  const listed = await (await request.get(`${API}/v1/sso/providers`, { headers })).json()
  for (const p of (listed.providers || []).filter((x: any) => x.name === name)) {
    await request.delete(`${API}/v1/sso/providers/${p.id}`, { headers })
  }
})

test('an admin adds an OIDC provider and its users are sent to it', async ({ page, browser }) => {
  const problems = watchForProblems(page)
  await loginViaUi(page)
  await page.goto('/settings/authentication', { waitUntil: 'load' })
  await page.getByRole('button', { name: /SSO/ }).first().click()
  await page.getByTestId('sso-add').click()
  await page.getByTestId('sso-name').fill(name)
  await page.getByTestId('sso-issuer').fill(`https://idp-${n}.example.invalid`)
  await page.getByTestId('sso-client-id').fill('logforge-e2e')
  await page.getByTestId('sso-client-secret').fill('e2e-client-secret')
  await page.getByTestId('sso-domains').fill(domain)
  await page.getByTestId('sso-mapping').fill('secops = security_analyst')
  await page.getByTestId('sso-save').click()
  await expect(page.getByTestId('sso-message')).toContainText(`Saved ${name}`)
  await expect(page.getByTestId(`sso-provider-${name}`)).toContainText('secret set')
  await expect(page.getByTestId(`sso-provider-${name}`)).toContainText('secops → security_analyst')
  await expect(page.locator('body')).not.toContainText('e2e-client-secret')
  // a SCIM token, shown once, then revoked
  await page.getByTestId('scim-name').fill(`E2E SCIM ${n}`)
  await page.getByTestId('scim-create').click()
  await expect(page.getByTestId('scim-fresh')).toContainText('lfscim_')
  page.once('dialog', d => d.accept())
  await page.getByTestId(`scim-token-E2E SCIM ${n}`).getByRole('button', { name: 'Revoke' }).click()
  await expect(page.getByTestId(`scim-token-E2E SCIM ${n}`)).toHaveCount(0)
  expect(problems.pageErrors).toEqual([])
  expect(problems.failedApiCalls).toEqual([])

  // a signed-out visitor from that domain
  const visitor = await (await browser.newContext()).newPage()
  await visitor.goto('/login', { waitUntil: 'load' })
  await visitor.getByTestId('email-input').fill(`dana@${domain}`)
  await visitor.getByTestId('sso-signin').click()
  // API start → IdP unreachable → back to the sign-in page with the reason
  await expect(visitor).toHaveURL(/\/login\?sso_error=/, { timeout: 30_000 })
  await expect(visitor.getByTestId('sso-signin-error')).toContainText(/identity provider/i)

  // a domain without SSO is told to use the password
  await visitor.getByTestId('email-input').fill('dana@no-sso.example')
  await visitor.getByTestId('sso-signin').click()
  await expect(visitor.getByTestId('sso-signin-error')).toContainText('Use your password')
})
