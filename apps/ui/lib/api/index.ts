/**
 * Logforge API - Centralized Export
 *
 * Only modules with real, verified backend endpoints are exported here.
 * The former ai/alerts/dashboard/enterprise/observability/query/roles/
 * security/storage/subscription/usage/users modules referenced ~130
 * endpoints that do not exist server-side and were removed (LF-027).
 * Pages call `apiClient` directly with real `/v1/...` paths.
 */

// Export base API client
export { apiClient, ApiClient } from '../api'
export type { ApiResponse } from '../api'

// Export the modules that back the live auth flow
export * from './auth'
export * from './tenants'

// Export as namespaces for grouped access
export { AuthApi } from './auth'
export { TenantsApi } from './tenants'

// Default export - API client
export { default } from '../api'
