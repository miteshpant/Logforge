'use client'

import React, { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Building2, ChevronDown, Loader2 } from 'lucide-react'

export function TenantSelector() {
  const { 
    tenant, 
    tenantId, 
    userRole, 
    availableTenants, 
    switchTenant, 
    isLoading 
  } = useAuth()
  
  const [isSwitching, setIsSwitching] = useState(false)

  const handleTenantSwitch = async (newTenantId: string) => {
    if (newTenantId === tenantId) return
    
    try {
      setIsSwitching(true)
      await switchTenant(newTenantId)
    } catch (error) {
      console.error('Failed to switch tenant:', error)
    } finally {
      setIsSwitching(false)
    }
  }

  const getTenantDisplayName = (tenant_id: string) => {
    // Use current tenant name if available
    if (tenant && tenant_id === tenant.id) {
      return tenant.name
    }
    // Last resort: use tenant ID
    return tenant_id
  }

  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case 'super_admin':
      case 'admin':
        return 'bg-red-100 text-red-800'
      case 'tenant_admin':
        return 'bg-blue-100 text-blue-800'
      case 'security_analyst':
        return 'bg-purple-100 text-purple-800'
      case 'devops_engineer':
        return 'bg-green-100 text-green-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center space-x-2 px-4 py-2 bg-slate-50 rounded-lg">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm text-slate-600">Loading tenant...</span>
      </div>
    )
  }

  if (!tenant || !tenantId) {
    return (
      <div className="flex items-center space-x-2 px-4 py-2 bg-red-50 rounded-lg">
        <Building2 className="h-4 w-4 text-red-600" />
        <span className="text-sm text-red-600">No tenant assigned</span>
      </div>
    )
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          disabled={isSwitching}
          className="flex items-center space-x-2 px-3 py-2 h-auto min-w-0 hover:bg-slate-100"
        >
          <Building2 className="h-4 w-4 text-slate-600" />
          <div className="flex flex-col items-start min-w-0">
            <span className="text-sm font-medium text-slate-900 truncate max-w-[200px]">
              {tenant?.name || getTenantDisplayName(tenantId)}
            </span>
            <div className="flex items-center space-x-1">
              <span className="text-xs text-slate-500">
                {userRole || 'user'}
              </span>
              <span className="text-xs text-slate-400">•</span>
              <span className="text-xs text-slate-500">
                {tenant?.subscription_tier || 'enterprise'}
              </span>
            </div>
          </div>
          {isSwitching ? (
            <Loader2 className="h-3 w-3 animate-spin text-slate-400" />
          ) : (
            <ChevronDown className="h-3 w-3 text-slate-400" />
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 p-2">
        <div className="px-2 py-1.5 text-xs font-medium text-slate-500 uppercase tracking-wider">
          Organization
        </div>
        
        {/* Current Tenant */}
        <DropdownMenuItem className="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded-md mb-2">
          <div className="flex items-center space-x-3">
            <Building2 className="h-4 w-4 text-blue-600" />
            <div>
              <div className="font-medium text-sm text-slate-900">
                {tenant?.name || getTenantDisplayName(tenantId)}
              </div>
              <div className="flex items-center space-x-2 mt-1">
                <Badge variant="secondary" className={`text-xs ${getRoleBadgeColor(userRole || 'user')}`}>
                  {userRole || 'user'}
                </Badge>
                <Badge variant="outline" className="text-xs">
                  {tenant?.subscription_tier || 'enterprise'}
                </Badge>
              </div>
            </div>
          </div>
          <Badge variant="secondary" className="text-xs bg-blue-100 text-blue-800">
            Current
          </Badge>
        </DropdownMenuItem>

        {/* Available Tenants */}
        {availableTenants && availableTenants.length > 1 && (
          <>
            <div className="px-2 py-1.5 text-xs font-medium text-slate-500 uppercase tracking-wider">
              Switch To
            </div>
            {availableTenants
              .filter(tenantRole => tenantRole.tenant_id !== tenantId)
              .map((tenantRole) => (
                <DropdownMenuItem
                  key={tenantRole.tenant_id}
                  onClick={() => handleTenantSwitch(tenantRole.tenant_id)}
                  className="flex items-center justify-between p-3 rounded-md hover:bg-slate-50"
                >
                  <div className="flex items-center space-x-3">
                    <Building2 className="h-4 w-4 text-slate-400" />
                    <div>
                      <div className="font-medium text-sm text-slate-900">
                        {getTenantDisplayName(tenantRole.tenant_id)}
                      </div>
                      <div className="flex items-center space-x-2 mt-1">
                        <Badge 
                          variant="secondary" 
                          className={`text-xs ${getRoleBadgeColor(tenantRole.role)}`}
                        >
                          {tenantRole.role}
                        </Badge>
                        {tenantRole.status && (
                          <Badge 
                            variant={tenantRole.status === 'active' ? 'default' : 'secondary'}
                            className="text-xs"
                          >
                            {tenantRole.status}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                  <ChevronDown className="h-3 w-3 rotate-[-90deg] text-slate-400" />
                </DropdownMenuItem>
              ))
            }
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}