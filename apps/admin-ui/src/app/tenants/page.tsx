'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, Plus, ExternalLink, Eye, CreditCard } from 'lucide-react'
import { fetchTenants, fetchTenantUsage, createTenant } from '@/lib/api'

interface Tenant {
  tenant_id: string
  name: string
  type: string
  status: string
  primary_contact_name: string
  primary_contact_email: string
  industry: string
  created_at: string
  updated_at: string
}

interface TenantUsage {
  tenant_id: string
  log_count_today: number
  log_count_month: number
  storage_used_gb: number
  query_count: number
  api_calls: number
  billing_period: string
}

interface TenantStats {
  title: string
  value: string
  description: string
}

const getSubscriptionColor = (type: string) => {
  switch (type.toLowerCase()) {
    case 'enterprise': return 'purple' as const
    case 'smb': return 'blue' as const
    case 'startup': return 'green' as const
    case 'professional': return 'blue' as const
    default: return 'secondary' as const
  }
}

const formatSubscriptionDisplay = (type: string) => {
  switch (type.toLowerCase()) {
    case 'enterprise': return 'ENTERPRISE'
    case 'smb': return 'PROFESSIONAL'
    case 'startup': return 'STARTER'
    case 'professional': return 'PROFESSIONAL'
    default: return type.toUpperCase()
  }
}

interface OnboardingModalProps {
  isOpen: boolean
  onClose: () => void
}

function OnboardingModal({ isOpen, onClose }: OnboardingModalProps) {
  const [formData, setFormData] = useState({
    organizationName: '',
    adminEmail: '',
    subscriptionTier: ''
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!formData.organizationName || !formData.adminEmail || !formData.subscriptionTier) {
      return
    }

    try {
      const tenantData = {
        name: formData.organizationName,
        primary_contact_name: formData.organizationName + ' Admin',
        primary_contact_email: formData.adminEmail,
        type: formData.subscriptionTier,
        industry: 'technology'
      }
      
      await createTenant(tenantData)
      
      onClose()
      setFormData({ organizationName: '', adminEmail: '', subscriptionTier: '' })
      // Refresh the tenant list
      window.location.reload()
      
    } catch (error) {
      console.error('Failed to create tenant:', error)
      alert(`Failed to create tenant: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h2 className="text-lg font-semibold mb-4">Onboard New Tenant</h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Organization Name *
            </label>
            <Input
              type="text"
              value={formData.organizationName}
              onChange={(e) => setFormData(prev => ({ ...prev, organizationName: e.target.value }))}
              placeholder="Enter organization name"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Admin Email *
            </label>
            <Input
              type="email"
              value={formData.adminEmail}
              onChange={(e) => setFormData(prev => ({ ...prev, adminEmail: e.target.value }))}
              placeholder="admin@company.com"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Subscription Tier *
            </label>
            <Select
              value={formData.subscriptionTier}
              onChange={(e) => setFormData(prev => ({ ...prev, subscriptionTier: e.target.value }))}
              required
            >
              <option value="">Select subscription tier</option>
              <option value="startup">Startup ($99/month)</option>
              <option value="smb">SMB ($499/month)</option>
              <option value="enterprise">Enterprise (Custom)</option>
            </Select>
          </div>
          
          <div className="flex justify-end space-x-2 pt-4">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit">
              Create Tenant
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function TenantsPage() {
  const [showOnboardingModal, setShowOnboardingModal] = useState(false)
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [tenantUsages, setTenantUsages] = useState<Record<string, TenantUsage>>({})
  const [tenantStats, setTenantStats] = useState<TenantStats[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchTenantsData()
  }, [])

  const fetchTenantsData = async () => {
    try {
      setLoading(true)
      
      // Fetch all tenants using API utility
      const tenantsData = await fetchTenants()
      setTenants(tenantsData.tenants || [])
      
      // Fetch usage data for each tenant
      const usagePromises = tenantsData.tenants.map(async (tenant: Tenant) => {
        try {
          const usageData = await fetchTenantUsage(tenant.tenant_id)
          return { [tenant.tenant_id]: usageData }
        } catch (error) {
          console.error(`Failed to fetch usage for tenant ${tenant.tenant_id}:`, error)
          return { [tenant.tenant_id]: null }
        }
      })
      
      const usageResults = await Promise.all(usagePromises)
      const combinedUsage = usageResults.reduce((acc, curr) => ({ ...acc, ...curr }), {})
      setTenantUsages(combinedUsage)
      
      // Calculate statistics
      const totalTenants = tenantsData.tenants.length
      const activeTenants = tenantsData.tenants.filter((t: Tenant) => t.status === 'active').length
      const enterpriseCount = tenantsData.tenants.filter((t: Tenant) => t.type === 'enterprise').length
      
      // Calculate total storage
      const totalStorage = Object.values(combinedUsage).reduce((sum, usage: any) => 
        sum + (usage?.storage_used_gb || 0), 0)
      
      setTenantStats([
        { title: "Total Tenants", value: totalTenants.toString(), description: "All registered tenants" },
        { title: "Active Tenants", value: activeTenants.toString(), description: "Currently active tenants" },
        { title: "Total Storage", value: `${totalStorage.toFixed(1)}GB`, description: "Storage used by all tenants" },
        { title: "Enterprise Customers", value: enterpriseCount.toString(), description: "Enterprise tier customers" }
      ])
      
    } catch (error) {
      console.error('Failed to fetch tenant data:', error)
      // Show error in UI
      setTenantStats([
        { title: "Error", value: "Failed to load", description: "Check API connection" },
        { title: "Error", value: "Failed to load", description: "Check API connection" },
        { title: "Error", value: "Failed to load", description: "Check API connection" },
        { title: "Error", value: "Failed to load", description: "Check API connection" }
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link href="/" className="text-blue-600 hover:text-blue-800 flex items-center">
            <ArrowLeft className="h-4 w-4 mr-1" />
            ← Back to Dashboard
          </Link>
        </div>
      </div>
      
      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold text-gray-900">Tenant Management</h1>
        <p className="text-gray-600">Onboard new tenants and manage existing accounts</p>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading ? (
          // Loading skeleton
          [1, 2, 3, 4].map((i) => (
            <Card key={i} className="bg-white p-4 rounded-lg shadow">
              <CardContent className="p-0">
                <div className="flex flex-col">
                  <span className="text-sm text-gray-400">Loading...</span>
                  <span className="text-2xl font-bold text-gray-400">-</span>
                </div>
              </CardContent>
            </Card>
          ))
        ) : (
          tenantStats.map((stat) => (
            <Card key={stat.title} className="bg-white p-4 rounded-lg shadow">
              <CardContent className="p-0">
                <div className="flex flex-col">
                  <span className="text-sm text-gray-500">{stat.title}</span>
                  <span className="text-2xl font-bold text-gray-900">{stat.value}</span>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Action Button */}
      <div className="flex justify-end">
        <Button 
          onClick={() => setShowOnboardingModal(true)}
          className="bg-blue-600 text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4 mr-2" />
          Onboard New Tenant
        </Button>
      </div>

      {/* Tenant Table */}
      <Card className="bg-white rounded-lg shadow">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Organization
                </th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider hidden md:table-cell">
                  Tenant ID
                </th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Tier
                </th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider hidden lg:table-cell">
                  Storage
                </th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider hidden lg:table-cell">
                  Cost
                </th>
                <th className="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {loading ? (
                // Loading rows
                [1, 2, 3].map((i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-4">
                      <div className="text-sm text-gray-400">Loading...</div>
                    </td>
                    <td className="px-3 py-4 hidden md:table-cell">
                      <div className="text-xs text-gray-400">Loading...</div>
                    </td>
                    <td className="px-3 py-4">
                      <Badge variant="secondary" className="text-xs">Loading</Badge>
                    </td>
                    <td className="px-3 py-4">
                      <Badge variant="secondary" className="text-xs">Loading</Badge>
                    </td>
                    <td className="px-3 py-4 hidden lg:table-cell">
                      <div className="text-sm text-gray-400">Loading...</div>
                    </td>
                    <td className="px-3 py-4 hidden lg:table-cell">
                      <div className="text-sm text-gray-400">Loading...</div>
                    </td>
                    <td className="px-3 py-4 text-center">
                      <div className="flex justify-center space-x-1">
                        <div className="w-8 h-8 bg-gray-200 rounded"></div>
                        <div className="w-8 h-8 bg-gray-200 rounded"></div>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                tenants.map((tenant) => {
                  const usage = tenantUsages[tenant.tenant_id]
                  const storageGB = usage?.storage_used_gb || 0
                  const monthlyCost = tenant.type === 'enterprise' ? '$997' : 
                                      tenant.type === 'smb' ? '$499' : '$99'
                  
                  return (
                    <tr key={tenant.tenant_id} className="hover:bg-gray-50">
                      <td className="px-4 py-4">
                        <div className="text-sm font-medium text-gray-900">{tenant.name}</div>
                        <div className="text-xs text-gray-500 md:hidden font-mono">{tenant.tenant_id.slice(0, 8)}...</div>
                      </td>
                      <td className="px-3 py-4 hidden md:table-cell">
                        <div className="text-xs text-gray-500 font-mono">{tenant.tenant_id.slice(0, 8)}...</div>
                      </td>
                      <td className="px-3 py-4">
                        <Badge variant={getSubscriptionColor(tenant.type)} className="text-xs">
                          {formatSubscriptionDisplay(tenant.type)}
                        </Badge>
                      </td>
                      <td className="px-3 py-4">
                        <Badge variant={tenant.status === 'active' ? 'green' : 'red'} className="text-xs">
                          {tenant.status === 'active' ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                      <td className="px-3 py-4 hidden lg:table-cell">
                        <div className="text-sm text-gray-900">{storageGB.toFixed(1)}GB</div>
                      </td>
                      <td className="px-3 py-4 hidden lg:table-cell">
                        <div className="text-sm font-medium text-gray-900">{monthlyCost}</div>
                      </td>
                      <td className="px-3 py-4">
                        <div className="flex justify-center space-x-1">
                          <Link 
                            href={`/tenants/${tenant.tenant_id}`} 
                            className="p-2 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-md transition-colors"
                            title="View Details"
                          >
                            <Eye className="h-4 w-4" />
                          </Link>
                          <Link 
                            href={`/tenants/${tenant.tenant_id}/subscription`} 
                            className="p-2 text-purple-600 hover:text-purple-800 hover:bg-purple-50 rounded-md transition-colors"
                            title="Manage Subscription"
                          >
                            <CreditCard className="h-4 w-4" />
                          </Link>
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Onboarding Modal */}
      <OnboardingModal 
        isOpen={showOnboardingModal}
        onClose={() => setShowOnboardingModal(false)}
      />
    </div>
  )
}