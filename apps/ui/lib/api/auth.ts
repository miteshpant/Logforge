/**
 * Authentication API Module
 *
 * APIs for user authentication, authorization, and profile management
 */

import { apiClient, ApiResponse } from '../api'

// ========== TYPE DEFINITIONS ==========

export interface UserProfile {
  id: string
  email: string
  name: string
  customer_id: string
  created_at: string
  last_login?: string
  email_verified_at?: string
  status: 'active' | 'inactive' | 'suspended'
}

export interface TenantInfo {
  id: string
  name: string
  subdomain?: string
  created_at: string
  status: 'active' | 'inactive' | 'suspended'
  plan?: string
}

export interface UserRoleAssignment {
  user_id: string
  customer_id: string
  role: string
  granted_at: string
  granted_by: string
  tenant?: TenantInfo
}

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  token: string
  user: UserProfile
  tenant: TenantInfo
  expires_at: string
}

export interface AuthContext {
  user: UserProfile | null
  tenant: TenantInfo | null
  isAuthenticated: boolean
}

// ========== API FUNCTIONS ==========

/**
 * Login with email and password
 */
export async function login(
  credentials: LoginRequest
): Promise<ApiResponse<LoginResponse>> {
  return apiClient.post<LoginResponse>('/v1/auth/login', credentials)
}

/**
 * Logout current user
 */
export async function logout(): Promise<ApiResponse<void>> {
  return apiClient.post('/v1/auth/logout')
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
  ApiResponse<{ roles: UserRoleAssignment[] }>
> {
  return apiClient.get('/v1/auth/me/roles')
}

/**
 * Refresh authentication token
 */
export async function refreshToken(): Promise<
  ApiResponse<{ token: string; expires_at: string }>
> {
  return apiClient.post('/v1/auth/refresh')
}

/**
 * Change user password
 */
export async function changePassword(params: {
  current_password: string
  new_password: string
}): Promise<ApiResponse<void>> {
  return apiClient.post('/v1/auth/change-password', params)
}

/**
 * Request password reset
 */
export async function requestPasswordReset(
  email: string
): Promise<ApiResponse<void>> {
  return apiClient.post('/v1/auth/password-reset/request', { email })
}

/**
 * Reset password with token
 */
export async function resetPassword(params: {
  token: string
  new_password: string
}): Promise<ApiResponse<void>> {
  return apiClient.post('/v1/auth/password-reset/confirm', params)
}

/**
 * Verify email with token
 */
export async function verifyEmail(token: string): Promise<ApiResponse<void>> {
  return apiClient.post('/v1/auth/verify-email', { token })
}

/**
 * Update user profile
 */
export async function updateProfile(
  updates: Partial<UserProfile>
): Promise<ApiResponse<UserProfile>> {
  return apiClient.put<UserProfile>('/v1/auth/me', updates)
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
  verifyEmail,
  updateProfile,
}

export default AuthApi
