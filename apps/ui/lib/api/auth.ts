/**
 * Authentication API Module
 *
 * APIs for user authentication, authorization, and profile management.
 * All paths verified against the live OpenAPI spec (LF-027):
 *   POST /v1/auth/login, /v1/auth/logout, /v1/auth/refresh
 *   GET  /v1/auth/me, /v1/auth/me/roles, /v1/auth/sessions
 *   POST /v1/auth/password/change, /v1/auth/password/reset,
 *        /v1/auth/password/reset-confirm, /v1/auth/verify-email,
 *        /v1/auth/verify-email-confirm
 */

import { apiClient, ApiResponse } from '../api'

// ========== TYPE DEFINITIONS ==========

/**
 * Shape of the backend's UserResponse model, as returned by
 * GET /v1/auth/me and inside the login response.
 */
export interface UserProfile {
  id: string
  email: string
  name: string
  status: 'active' | 'inactive' | 'suspended' | string
  created_at: string
  updated_at?: string
  last_login_at?: string | null
  email_verified_at?: string | null
}

/**
 * UI-side tenant summary used by AuthContext / TenantSelector.
 */
export interface TenantInfo {
  id: string
  name: string
  subdomain?: string
  created_at?: string
  status?: 'active' | 'inactive' | 'suspended' | string
  plan?: string
  subscription_tier?: string
  features?: string[]
  limits?: {
    users?: number
    storage_gb?: number
    retention_days?: number
    api_calls_per_month?: number
  }
}

/**
 * One row of GET /v1/auth/me/roles → { user_id, roles: [...] }.
 */
export interface UserRoleAssignment {
  id: string
  tenant_id: string
  role: string
  granted_at: string | null
  status: string
  tenant?: TenantInfo
}

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  /** Opaque rotating refresh token (LF-015). */
  refresh_token?: string
  refresh_expires_at?: string
  user: UserProfile
  tenant?: TenantInfo
  expires_at: string
}

export interface AuthContext {
  user: UserProfile | null
  tenant: TenantInfo | null
  isAuthenticated: boolean
}

// ========== API FUNCTIONS ==========

/**
 * Login with email and password.
 * Stores the returned refresh token so the client can renew the
 * session transparently when the access token expires (LF-015).
 */
export async function login(
  credentials: LoginRequest
): Promise<ApiResponse<LoginResponse>> {
  const response = await apiClient.post<LoginResponse>('/v1/auth/login', credentials)
  if (response.success && response.data?.refresh_token) {
    apiClient.setRefreshToken(response.data.refresh_token)
  }
  return response
}

/**
 * Logout current user. Revokes the server-side session and the
 * refresh token, then clears local auth state.
 */
export async function logout(): Promise<ApiResponse<void>> {
  const refreshToken = apiClient.getRefreshToken()
  return apiClient.post('/v1/auth/logout', refreshToken ? { refresh_token: refreshToken } : undefined)
}

/**
 * Get current authenticated user profile
 */
export async function getCurrentUser(): Promise<ApiResponse<UserProfile>> {
  return apiClient.get<UserProfile>('/v1/auth/me')
}

/**
 * Get current user's role assignments across tenants
 */
export async function getCurrentUserRoles(): Promise<
  ApiResponse<{ user_id: string; roles: UserRoleAssignment[] }>
> {
  return apiClient.get('/v1/auth/me/roles')
}

/**
 * Exchange the stored refresh token for a new access + refresh token
 * pair (rotation). Fails if no refresh token is stored.
 */
export async function refreshToken(): Promise<ApiResponse<LoginResponse>> {
  const stored = apiClient.getRefreshToken()
  if (!stored) {
    return { success: false, error: 'No refresh token available' }
  }
  const response = await apiClient.post<LoginResponse>('/v1/auth/refresh', {
    refresh_token: stored,
  })
  if (response.success && response.data?.refresh_token) {
    apiClient.setRefreshToken(response.data.refresh_token)
  }
  return response
}

/**
 * Change user password
 */
export async function changePassword(params: {
  current_password: string
  new_password: string
}): Promise<ApiResponse<void>> {
  return apiClient.post('/v1/auth/password/change', params)
}

/**
 * Request password reset
 */
export async function requestPasswordReset(
  email: string
): Promise<ApiResponse<void>> {
  return apiClient.post('/v1/auth/password/reset', { email })
}

/**
 * Reset password with token
 */
export async function resetPassword(params: {
  token: string
  new_password: string
}): Promise<ApiResponse<void>> {
  return apiClient.post('/v1/auth/password/reset-confirm', params)
}

/**
 * Accept an invitation: creates the account and grants the invited role
 */
export async function acceptInvite(params: {
  invitation_token: string
  email: string
  tenant_id: string
  name: string
  password: string
}): Promise<ApiResponse<void>> {
  return apiClient.post('/v1/auth/accept-invite', params)
}

/**
 * Send an email-verification token to the current user
 */
export async function sendEmailVerification(): Promise<ApiResponse<void>> {
  return apiClient.post('/v1/auth/verify-email')
}

/**
 * Confirm email verification with token
 */
export async function verifyEmail(token: string): Promise<ApiResponse<void>> {
  return apiClient.post('/v1/auth/verify-email-confirm', { token })
}

/**
 * List the current user's active sessions
 */
export async function listSessions(): Promise<
  ApiResponse<{ sessions: any[]; total_count: number }>
> {
  return apiClient.get('/v1/auth/sessions')
}

// Export all functions as a namespace
export const AuthApi = {
  login,
  logout,
  getCurrentUser,
  getCurrentUserRoles,
  refreshToken,
  changePassword,
  requestPasswordReset,
  resetPassword,
  sendEmailVerification,
  verifyEmail,
  listSessions,
}

export default AuthApi
