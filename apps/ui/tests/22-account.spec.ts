import { test, expect } from '@playwright/test'
import { loginViaUi, watchForProblems } from './support/session'

/**
 * Account pages (Phase 14): forgot and reset password, accepting an
 * invitation, email verification. Links carry tokens from emails; these
 * checks use invalid tokens, which must be refused (the valid paths are
 * covered by tests/test_account_flows.py).
 */

test('forgot password asks for an email and says the same thing whoever you are', async ({ page }) => {
  await page.goto('/login', { waitUntil: 'load' })
  await page.getByTestId('forgot-password').click()
  await expect(page).toHaveURL(/\/forgot-password$/)
  await page.getByTestId('reset-email').fill(`nobody-${Date.now()}@example.invalid`)
  await page.getByTestId('reset-request').click()
  await expect(page.getByTestId('reset-requested')).toContainText('If an account uses')
})

test('a reset link with a bad token is refused', async ({ page }) => {
  await page.goto('/reset-password?token=not-a-real-token', { waitUntil: 'load' })
  await page.getByTestId('new-password').fill('Another-Passw0rd!')
  await page.getByTestId('new-password-again').fill('Another-Passw0rd!')
  await page.getByTestId('reset-confirm').click()
  await expect(page.getByTestId('reset-error')).toContainText(/invalid|expired/i)
})

test('an invitation with a bad token is refused', async ({ page }) => {
  await page.goto('/accept-invite?token=nope&email=new%40example.invalid&tenant=t1', { waitUntil: 'load' })
  await page.getByTestId('invite-name').fill('New Person')
  await page.getByTestId('invite-password').fill('Str0ng-Passw0rd!')
  await page.getByTestId('invite-accept').click()
  await expect(page.getByTestId('invite-error')).toContainText(/invalid|expired/i)
})

test('email verification needs a session, keeps the token through sign-in, and refuses a bad one', async ({ page }) => {
  const problems = watchForProblems(page)
  await page.goto('/verify-email?token=1.bad', { waitUntil: 'load' })
  await expect(page).toHaveURL(/\/login\?next=%2Fverify-email%3Ftoken%3D1\.bad/)
  await loginViaUi(page)
  await page.goto('/verify-email?token=1.bad', { waitUntil: 'load' })
  await expect(page.getByTestId('verify-result')).toContainText(/invalid|expired|another account/i)
  expect(problems.pageErrors).toEqual([])
})
