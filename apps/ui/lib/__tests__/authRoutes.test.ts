import { describe, expect, it } from 'vitest'
import { isPublicRoute, loginRedirect } from '../authRoutes'

describe('auth routes', () => {
  it('lets the account pages through without a session', () => {
    for (const p of ['/login', '/forgot-password', '/reset-password', '/accept-invite']) expect(isPublicRoute(p)).toBe(true)
    expect(isPublicRoute('/verify-email')).toBe(false) // needs the session of the address being verified
    expect(isPublicRoute('/security/cases')).toBe(false)
    expect(isPublicRoute('/login-something')).toBe(false)
    expect(isPublicRoute(null)).toBe(false)
  })

  it('keeps the query string when sending a visitor to log in', () => {
    expect(loginRedirect('/verify-email', '?token=1.abc')).toBe('/login?next=%2Fverify-email%3Ftoken%3D1.abc')
    expect(loginRedirect('/security/cases', '')).toBe('/login?next=%2Fsecurity%2Fcases')
    expect(loginRedirect(null, '')).toBe('/login?next=%2F')
  })
})
