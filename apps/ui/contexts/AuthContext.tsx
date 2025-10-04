'use client'

import React, { createContext, useContext, useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { AuthApi, apiClient } from '@/lib/api'
import { TenantsApi } from '@/lib/api/tenants'
import type { AuthContext as AuthContextType, UserProfile, TenantInfo, UserRoleAssignment } from '@/lib/api'

interface AuthProviderState {
  // Authentication state
  isAuthenticated: boolean
  isLoading: boolean
  user: UserProfile | null
  tenant: TenantInfo | null
  
  // Actions
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshAuth: () => Promise<void>
  
  // Tenant context
  tenantId: string | null
  userRole: string | null
  permissions: string[]
  
  // Multi-tenant support
  availableTenants: UserRoleAssignment[]
  switchTenant: (tenantId: string) => Promise<void>
  
  // Error handling
  error: string | null
  clearError: () => void
}

const AuthContext = createContext<AuthProviderState | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [user, setUser] = useState<UserProfile | null>(null)
  const [tenant, setTenant] = useState<TenantInfo | null>(null)
  const [tenantId, setTenantId] = useState<string | null>(null)
  const [userRole, setUserRole] = useState<string | null>(null)
  const [permissions, setPermissions] = useState<string[]>([])
  const [availableTenants, setAvailableTenants] = useState<UserRoleAssignment[]>([])
  const [error, setError] = useState<string | null>(null)
  
  const router = useRouter()

  // Initialize authentication state on mount
  useEffect(() => {
    initializeAuth()
  }, [])

  const initializeAuth = async () => {
    try {
      setIsLoading(true)
      setError(null)
      
      // Check if user has valid session
      const authContext = apiClient.getAuthContext()
      
      if (authContext.isAuthenticated && authContext.token) {
        // Extract tenant_id and user_role from JWT token (same as login flow)
        try {
          const tokenPayload = JSON.parse(atob(authContext.token.split('.')[1]))
          const tenantId = tokenPayload.tenant_id
          const userRole = tokenPayload.user_role
          
          if (!tenantId || !userRole) {
            throw new Error('JWT token missing tenant_id or user_role')
          }
          
          // Update auth context with correct tenant ID from JWT
          apiClient.setAuth(authContext.token, tenantId, undefined)
          
          // Validate session with backend using correct tenant context
          const userProfile = await AuthApi.getCurrentUser()
          
          if (userProfile.success) {
            // Fetch actual tenant information from API using tenant ID
            const tenantData = await TenantsApi.getTenant(tenantId)
            if (!tenantData) {
              throw new Error('Failed to fetch tenant information')
            }
            
            // Use real tenant data from API (API returns tenant directly, not wrapped)
            const tenantInfo: TenantInfo = {
              id: tenantData.tenant_id,
              name: tenantData.name,
              subscription_tier: tenantData.type,
              features: ['logs', 'analytics', 'alerts', 'dashboards', 'security'],
              limits: {
                users: 100,
                storage_gb: 1000,
                retention_days: 90,
                api_calls_per_month: 1000000
              }
            }
            
            setUser(userProfile.data)
            setTenant(tenantInfo)
            setTenantId(tenantId)
            setUserRole(userRole) // Use role from JWT
            setPermissions(['logs:read', 'analytics:read', 'dashboards:read'])
            setIsAuthenticated(true)
            
            // Fetch available tenants for multi-tenant support
            await loadAvailableTenants()
          } else {
            throw new Error('Failed to validate session')
          }
        } catch (jwtError) {
          console.error('Failed to parse JWT token:', jwtError)
          throw new Error('Invalid JWT token format')
        }
      } else {
        // No valid session, redirect to login
        setIsAuthenticated(false)
        router.push('/login')
      }
    } catch (error: any) {
      console.error('Auth initialization failed:', error)
      setError('Authentication failed. Please log in again.')
      setIsAuthenticated(false)
      router.push('/login')
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (email: string, password: string) => {
    try {
      setIsLoading(true)
      setError(null)
      
      // Step 1: Authenticate with backend
      const loginResponse = await AuthApi.login({ email, password })
      
      if (loginResponse.success && loginResponse.data) {
        const { access_token, user: userProfile, expires_at } = loginResponse.data
        
        // Step 2: Extract tenant_id and user_role from JWT token (backend now includes both)
        const tokenPayload = JSON.parse(atob(access_token.split('.')[1]))
        const tenantId = tokenPayload.tenant_id
        const userRole = tokenPayload.user_role
        
        if (!tenantId) {
          throw new Error('No tenant_id found in JWT token')
        }
        
        if (!userRole) {
          throw new Error('No user_role found in JWT token')
        }
        
        // Step 5: Set auth context with tenant ID from JWT
        apiClient.setAuth(access_token, tenantId, undefined)
        
        // Step 6: Fetch actual tenant information from API using tenant ID
        const tenantData = await TenantsApi.getTenant(tenantId)
        if (!tenantData) {
          throw new Error('Failed to fetch tenant information')
        }
        
        // Use real tenant data from API (API returns tenant directly, not wrapped)
        const tenantInfo: TenantInfo = {
          id: tenantData.tenant_id,
          name: tenantData.name,
          subscription_tier: tenantData.type,
          features: ['logs', 'analytics', 'alerts', 'dashboards', 'security'],
          limits: {
            users: 100,
            storage_gb: 1000,
            retention_days: 90,
            api_calls_per_month: 1000000
          }
        }
        
        // Step 7: Update authentication state with actual role from JWT
        setUser(userProfile)
        setTenant(tenantInfo)
        setTenantId(tenantId)
        setUserRole(userRole) // Use actual role from JWT token
        setPermissions(['logs:read', 'analytics:read', 'dashboards:read'])
        setIsAuthenticated(true)
        
        // Step 8: Redirect to dashboard
        router.push('/dashboard')
      } else {
        throw new Error(loginResponse.message || 'Login failed')
      }
    } catch (error: any) {
      console.error('Login failed:', error)
      setError(error.message || 'Login failed. Please check your credentials.')
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  const logout = async () => {
    try {
      setIsLoading(true)
      
      // Call logout API
      await AuthApi.logout()
      
      // Clear authentication state
      apiClient.logout()
      setUser(null)
      setTenant(null)
      setTenantId(null)
      setUserRole(null)
      setPermissions([])
      setIsAuthenticated(false)
      
      // Redirect to login
      router.push('/login')
    } catch (error: any) {
      console.error('Logout failed:', error)
      // Force logout even if API call fails
      apiClient.logout()
      setIsAuthenticated(false)
      router.push('/login')
    } finally {
      setIsLoading(false)
    }
  }

  const refreshAuth = async () => {
    try {
      const userProfile = await AuthApi.getCurrentUser()
      
      setUser(userProfile.data)
      setUserRole(userRole || 'user')
      setPermissions(permissions)
    } catch (error: any) {
      console.error('Auth refresh failed:', error)
      // If refresh fails, force re-authentication
      await logout()
    }
  }

  const loadAvailableTenants = async () => {
    try {
      // Fetch all user role assignments across different tenants
      const rolesResponse = await AuthApi.getCurrentUserRoles()
      
      if (rolesResponse.success && rolesResponse.data) {
        setAvailableTenants(rolesResponse.data)
      }
    } catch (error: any) {
      console.warn('Failed to load available tenants:', error)
      // Don't fail authentication if we can't load tenants
    }
  }

  const switchTenant = async (newTenantId: string) => {
    try {
      setIsLoading(true)
      
      // Find the role assignment for this tenant
      const tenantRole = availableTenants.find(t => t.tenant_id === newTenantId)
      if (!tenantRole) {
        throw new Error('No access to selected tenant')
      }
      
      // Update auth context with new tenant
      const currentToken = apiClient.getAuthContext().token
      if (!currentToken) {
        throw new Error('No valid token')
      }
      
      apiClient.setAuth(currentToken, newTenantId, undefined)
      
      // Fetch actual tenant information from API using tenant ID
      const tenantData = await TenantsApi.getTenant(newTenantId)
      if (!tenantData) {
        throw new Error('Failed to fetch tenant information')
      }
      
      // Use real tenant data from API (API returns tenant directly, not wrapped)
      const newTenantInfo: TenantInfo = {
        id: tenantData.tenant_id,
        name: tenantData.name,
        subscription_tier: tenantData.type,
        features: ['logs', 'analytics', 'alerts', 'dashboards', 'security'],
        limits: {
          users: 100,
          storage_gb: 1000,
          retention_days: 90,
          api_calls_per_month: 1000000
        }
      }
      
      // Update state
      setTenant(newTenantInfo)
      setTenantId(newTenantId)
      setUserRole(tenantRole.role)
      
      // Reload the current page data
      window.location.reload()
    } catch (error: any) {
      console.error('Failed to switch tenant:', error)
      setError('Failed to switch tenant: ' + error.message)
    } finally {
      setIsLoading(false)
    }
  }

  const clearError = () => {
    setError(null)
  }

  // Permission checking utilities
  const hasPermission = (permission: string): boolean => {
    return permissions.includes(permission) || userRole === 'admin' || userRole === 'super_admin'
  }

  const hasRole = (role: string): boolean => {
    return userRole === role
  }

  const value: AuthProviderState = {
    isAuthenticated,
    isLoading,
    user,
    tenant,
    login,
    logout,
    refreshAuth,
    tenantId,
    userRole,
    permissions,
    availableTenants,
    switchTenant,
    error,
    clearError,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

// Permission checking hook
export function usePermissions() {
  const { permissions, userRole } = useAuth()
  
  const hasPermission = (permission: string): boolean => {
    return permissions.includes(permission) || userRole === 'admin' || userRole === 'super_admin'
  }

  const hasRole = (role: string): boolean => {
    return userRole === role
  }

  const hasAnyRole = (roles: string[]): boolean => {
    return roles.includes(userRole || '')
  }

  return {
    hasPermission,
    hasRole,
    hasAnyRole,
    permissions,
    userRole,
  }
}