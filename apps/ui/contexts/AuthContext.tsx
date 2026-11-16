'use client'

import React, { createContext, useContext, useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { AuthApi, apiClient } from '@/lib/api/index'
import { TenantsApi } from '@/lib/api/tenants'
import type { AuthContext as AuthContextType, UserProfile, TenantInfo } from '@/lib/api/index'
import type { UserRoleAssignment } from '@/lib/api/auth'
import type { Tenant } from '@/lib/api/tenants'

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
      console.log('🔄 AuthContext initialization - auth context:', { 
        isAuthenticated: authContext.isAuthenticated, 
        hasToken: !!authContext.token,
        tenantId: authContext.tenantId 
      })
      
      if (authContext.isAuthenticated && authContext.token) {
        // Validate JWT token format first
        const tokenParts = authContext.token.split('.')
        if (tokenParts.length !== 3) {
          console.warn('Invalid JWT token format - not 3 parts')
          throw new Error('Invalid JWT token format')
        }
        
        // Extract tenant_id and user_role from JWT token (same as login flow)
        try {
          const tokenPayload = JSON.parse(atob(tokenParts[1]))
          const tenantId = tokenPayload.tenant_id
          const userRole = tokenPayload.user_role
          
          if (!tenantId || !userRole) {
            console.warn('JWT token missing tenant_id or user_role:', { tenantId, userRole })
            throw new Error('JWT token missing tenant_id or user_role')
          }
          
          // Update auth context with correct tenant ID from JWT
          apiClient.setAuth(authContext.token, tenantId, undefined)
          
          // Validate session with backend using correct tenant context
          console.log('🔍 Testing session validation...')
          const userProfile = await AuthApi.getCurrentUser()
          console.log('👤 getCurrentUser response:', userProfile)
          
          if (userProfile.success && userProfile.data) {
            // Fetch actual tenant information from API using tenant ID
            const tenantData = await TenantsApi.getTenant(tenantId)
            if (!tenantData) {
              throw new Error('Failed to fetch tenant information')
            }
            
            // Handle different response formats - backend might return data directly or wrapped
            let tenant
            if (tenantData.data && tenantData.data.tenant_id) {
              // Standard ApiResponse<Tenant> format (wrapped)
              tenant = tenantData.data
            } else if (tenantData.tenant_id) {
              // Backend returns tenant directly (not wrapped) - this is the actual format
              tenant = tenantData
            } else {
              throw new Error('Tenant data not found in expected format')
            }
            
            const tenantInfo: TenantInfo = {
              id: tenant.tenant_id,
              name: tenant.name,
              subscription_tier: tenant.type,
              features: ['logs', 'analytics', 'alerts', 'dashboards', 'security'],
              limits: {
                users: 100,
                storage_gb: 1000,
                retention_days: 90,
                api_calls_per_month: 1000000
              }
            }
            
            setUser(userProfile.data ?? null)
            setTenant(tenantInfo)
            setTenantId(tenantId)
            setUserRole(userRole) // Use role from JWT
            setPermissions(['logs:read', 'analytics:read', 'dashboards:read'])
            setIsAuthenticated(true)
            
            console.log('✅ Auth initialization successful:', {
              userId: userProfile.data.id,
              userEmail: userProfile.data.email,
              tenantId: tenantId,
              tenantName: tenantInfo.name,
              userRole: userRole
            })
            
            // Fetch available tenants for multi-tenant support
            await loadAvailableTenants()
          } else {
            throw new Error('Failed to validate session')
          }
        } catch (jwtError) {
          console.error('Failed to parse JWT token:', jwtError)
          // Clear invalid tokens
          apiClient.logout()
          throw new Error('Invalid JWT token format')
        }
      } else {
        // No valid session, clear any remaining state and proceed to login check
        setIsAuthenticated(false)
        // Don't automatically redirect here - let the page routing handle it
      }
    } catch (error: any) {
      console.error('Auth initialization failed:', error)
      // Only set error if we're not on the login page already
      if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
        setError('Authentication failed. Please log in again.')
      }
      setIsAuthenticated(false)
      // Clear any invalid auth state
      apiClient.logout()
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

        // Platform-scoped accounts (super_admin & co.) have no tenant to open
        // here; their console is the admin UI. Without this the tenant lookup
        // 404s and the user sees "Tenant data not found in expected format".
        if (tenantId === 'platform') {
          throw new Error(
            'This is a platform administrator account. Sign in to the admin console instead; ' +
            'the tenant console needs a tenant user.'
          )
        }
        
        if (!userRole) {
          throw new Error('No user_role found in JWT token')
        }
        
        // Step 5: Set auth context with tenant ID from JWT
        apiClient.setAuth(access_token, tenantId, undefined)
        
        // Step 6: Fetch actual tenant information from API using tenant ID
        console.log('🔑 Fetching tenant data for tenantId:', tenantId)
        const tenantData = await TenantsApi.getTenant(tenantId)
        console.log('🏢 Raw tenant API response:', tenantData)
        
        if (!tenantData) {
          throw new Error('Failed to fetch tenant information')
        }
        
        // Handle different response formats - backend might return data directly or wrapped
        let tenant
        if (tenantData.data && tenantData.data.tenant_id) {
          // Standard ApiResponse<Tenant> format (wrapped)
          tenant = tenantData.data
          console.log('🏢 Using tenant from .data property:', tenant)
        } else if (tenantData.tenant_id) {
          // Backend returns tenant directly (not wrapped) - this is the actual format
          tenant = tenantData
          console.log('🏢 Using tenant directly from response:', tenant)
        } else {
          console.error('🚨 Unexpected tenant response format:', tenantData)
          throw new Error('Tenant data not found in expected format')
        }
        
        const tenantInfo: TenantInfo = {
          id: tenant.tenant_id,
          name: tenant.name,
          subscription_tier: tenant.type,
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

        // Step 8: Return to the page that sent the user to /login (AuthGate
        // sets ?next=), else the default landing page. Same-origin paths only,
        // so `next` can't be used as an open redirect.
        const next = new URLSearchParams(window.location.search).get('next')
        const safeNext = next && next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/login')
        router.push(safeNext ? next : '/centrum')
      } else {
        throw new Error(loginResponse.error || loginResponse.message || 'Login failed')
      }
    } catch (error: any) {
      console.error('Login failed:', error)
      // A failure after setAuth() (e.g. the tenant lookup) used to leave the
      // token and tenant in localStorage, so the next page load ran with a
      // half-established session. Clear everything a failed login may have set.
      apiClient.logout()
      setUser(null)
      setTenant(null)
      setTenantId(null)
      setUserRole(null)
      setIsAuthenticated(false)
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
      
      setUser(userProfile.data ?? null)
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
        // /v1/auth/me/roles returns { user_id, roles: [...] }
        setAvailableTenants(rolesResponse.data.roles ?? [])
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
      
      // Handle different response formats - backend might return data directly or wrapped
      let tenant
      if (tenantData.data && tenantData.data.tenant_id) {
        // Standard ApiResponse<Tenant> format (wrapped)
        tenant = tenantData.data
      } else if (tenantData.tenant_id) {
        // Backend returns tenant directly (not wrapped) - this is the actual format
        tenant = tenantData
      } else {
        throw new Error('Tenant data not found in expected format')
      }
      
      const newTenantInfo: TenantInfo = {
        id: tenant.tenant_id,
        name: tenant.name,
        subscription_tier: tenant.type,
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