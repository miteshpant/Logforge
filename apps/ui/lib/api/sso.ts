/** Single sign-on (Phase 14): OIDC providers, and finding one for an address at sign-in. */
import { API_CONFIG, apiClient } from '../api'

export interface SsoProvider {
  id: string; tenant_id: string; name: string; issuer: string; client_id: string; client_secret_set: boolean
  scopes: string; groups_claim: string; role_mapping: Record<string, string>; default_role: string | null
  allowed_domains: string[]; enabled: boolean
}
export type SsoProviderBody = Omit<SsoProvider, 'id' | 'tenant_id' | 'client_secret_set'> & { client_secret?: string }

async function call<T>(promise: Promise<{ success?: boolean; data?: T; error?: string }>, what: string): Promise<T> {
  const response = await promise
  if (!response.success) throw new Error(response.error || what)
  return response.data as T
}

export const listProviders = () =>
  call<{ providers: SsoProvider[]; callback_url_path: string; roles: string[] }>(apiClient.get('/v1/sso/providers'), 'Failed to load sign-in providers')
export const saveProvider = (body: SsoProviderBody, id?: string) =>
  call<{ provider: SsoProvider }>(id ? apiClient.put(`/v1/sso/providers/${id}`, body) : apiClient.post('/v1/sso/providers', body),
    'Failed to save the provider')
export const deleteProvider = (id: string) => call(apiClient.delete(`/v1/sso/providers/${id}`), 'Failed to delete the provider')

/** The providers for an address's domain (public; used on the sign-in page). */
export const discoverProviders = (email: string) =>
  call<{ providers: { id: string; name: string }[] }>(apiClient.get('/v1/auth/sso/discover', { email }), 'Single sign-on lookup failed')

/** Where the browser goes to sign in with a provider. */
export const startUrl = (providerId: string, next?: string | null) =>
  `${API_CONFIG.baseURL}/v1/auth/sso/${encodeURIComponent(providerId)}/start` + (next ? `?next=${encodeURIComponent(next)}` : '')
