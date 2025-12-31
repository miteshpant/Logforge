/**
 * Logforge API - Centralized Export
 *
 * Import all API modules and re-export for convenient access
 */

// Export base API client
export { apiClient, ApiClient } from '../api'
export type { ApiResponse } from '../api'

// Export all API modules
export * from './observability'
export * from './security'
export * from './alerts'
export * from './ai'
export * from './query'
export * from './usage'

// Export as namespaces for grouped access
export { ObservabilityApi } from './observability'
export { SecurityApi } from './security'
export { AlertsApi } from './alerts'
export { AiApi } from './ai'
export { QueryApi } from './query'
export { UsageApi } from './usage'

// Default export - API client
export { default } from '../api'
