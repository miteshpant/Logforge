/**
 * What the signed-in user may read, from GET /v1/auth/access (built-in role
 * grants plus custom roles), so pages can leave out widgets whose endpoints
 * would refuse them instead of showing errors.
 *
 * Grants look like "logs:read,search:tenant" or "security:*:tenant"; the
 * matching mirrors the API's check_permission. If access can't be read,
 * everything is allowed (the API still enforces it).
 */
import { useEffect, useState } from 'react'
import { apiClient } from './api'

export function allows(granted: string[], required: string): boolean {
  const [resource, action] = required.split(':')
  return granted.some(grant => {
    const [r, actions, scope] = grant.split(':')
    if (r !== '*' && r !== resource) return false
    if (actions !== '*' && !actions.split(',').includes(action)) return false
    return scope === 'tenant' || scope === '*' || scope === 'platform'
  })
}

let cache: { key: string; granted: Promise<string[] | null> } | null = null

function load(): Promise<string[] | null> {
  const key = typeof window === 'undefined' ? '' : (localStorage.getItem('tenant_id') || '') + '|' +
    (localStorage.getItem('auth_token') || '').slice(-16)
  if (!cache || cache.key !== key) {
    cache = {
      key,
      granted: apiClient.get<{ role_permissions?: string[]; permissions?: string[] }>('/v1/auth/access')
        .then(r => (r.success && r.data ? [...(r.data.role_permissions || []), ...(r.data.permissions || [])] : null))
        .catch(() => null),
    }
  }
  return cache.granted
}

/** `can("usage:read")`; `ready` is false until access has loaded. */
export function useAccess(): { ready: boolean; can: (permission: string) => boolean } {
  const [granted, setGranted] = useState<string[] | null | undefined>(undefined)
  useEffect(() => {
    let live = true
    load().then(g => { if (live) setGranted(g) })
    return () => { live = false }
  }, [])
  return {
    ready: granted !== undefined,
    can: (permission: string) => granted === undefined ? false : granted === null || allows(granted, permission),
  }
}
