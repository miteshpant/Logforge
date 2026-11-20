import { describe, expect, it } from 'vitest'
import { allows } from '../access'

// The grants of the built-in roles look like the API's ROLE_PERMISSIONS.
const viewer = ['tenant_profile:read:tenant', 'logs:read:tenant', 'dashboards:read:tenant', 'alerts:read:own', 'reports:read:tenant']
const analyst = ['security:*:tenant', 'logs:read,search:tenant', 'ai:read:tenant', 'alerts:read,investigate:tenant']

describe('allows', () => {
  it('matches resource, action list and wildcard', () => {
    expect(allows(analyst, 'security:read')).toBe(true)
    expect(allows(analyst, 'security:write')).toBe(true)
    expect(allows(analyst, 'logs:search')).toBe(true)
    expect(allows(analyst, 'alerts:read')).toBe(true)
    expect(allows(analyst, 'alerts:write')).toBe(false)
    expect(allows(analyst, 'usage:read')).toBe(false)
  })
  it('needs tenant scope: alerts:read:own does not read the tenant\'s alerts', () => {
    expect(allows(viewer, 'logs:read')).toBe(true)
    expect(allows(viewer, 'alerts:read')).toBe(false)
  })
  it('lets a platform admin through', () => {
    expect(allows(['*:*:platform'], 'usage:read')).toBe(true)
  })
})
