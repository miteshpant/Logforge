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
        return 'bg-red-500/20 text-red-400'
      case 'tenant_admin':
        return 'bg-blue-500/20 text-blue-400'
      case 'security_analyst':
        return 'bg-purple-500/20 text-purple-400'
      case 'devops_engineer':
        return 'bg-green-500/20 text-green-400'
      default:
        return 'bg-slate-500/20 text-slate-400'
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center space-x-2 px-4 py-2 bg-slate-800/50 rounded-lg">
        <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
        <span className="text-sm text-slate-400">Loading tenant...</span>
      </div>
    )
  }

  if (!tenant || !tenantId) {
    return (
      <div className="flex items-center space-x-2 px-4 py-2 bg-red-500/10 rounded-lg">
        <Building2 className="h-4 w-4 text-red-400" />
        <span className="text-sm text-red-400">No tenant assigned</span>
      </div>
    )
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          disabled={isSwitching}
          className="flex items-center space-x-2 px-3 py-2 h-auto min-w-0 hover:bg-white/5"
          data-testid="tenant-selector"
        >
          <Building2 className="h-4 w-4 text-slate-400" />
          <div className="flex flex-col items-start min-w-0">
            <span className="text-sm font-medium text-white truncate max-w-[200px]" data-testid="current-tenant-name">
              {tenant?.name || getTenantDisplayName(tenantId)}
            </span>
            <div className="flex items-center space-x-1">
              <span className="text-xs text-slate-500" data-testid="current-user-role">
                {userRole || 'user'}
              </span>
              <span className="text-xs text-slate-400">•</span>
              <span className="text-xs text-slate-500" data-testid="current-subscription-tier">
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
      <DropdownMenuContent align="end" className="w-80 p-2 bg-slate-800 border border-white/10">
        <div className="px-2 py-1.5 text-xs font-medium text-slate-500 uppercase tracking-wider">
          Organization
        </div>

        {/* Current Tenant */}
        <DropdownMenuItem className="flex items-center justify-between p-3 bg-blue-500/10 border border-blue-500/20 rounded-md mb-2">
          <div className="flex items-center space-x-3">
            <Building2 className="h-4 w-4 text-blue-400" />
            <div>
              <div className="font-medium text-sm text-white">
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
          <Badge variant="secondary" className="text-xs bg-blue-500/20 text-blue-400">
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
                  className="flex items-center justify-between p-3 rounded-md hover:bg-white/5"
                >
                  <div className="flex items-center space-x-3">
                    <Building2 className="h-4 w-4 text-slate-400" />
                    <div>
                      <div className="font-medium text-sm text-white">
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