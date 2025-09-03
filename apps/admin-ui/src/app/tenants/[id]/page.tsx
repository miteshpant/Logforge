'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, Edit, Mail, Calendar, Building, Globe, CreditCard } from 'lucide-react'
import { fetchTenants, fetchTenantUsage } from '@/lib/api'

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

const getSubscriptionColor = (type: string) => {
  switch (type.toLowerCase()) {
    case 'enterprise': return 'purple' as const
    case 'smb': return 'blue' as const
    case 'startup': return 'green' as const
    default: return 'secondary' as const
  }
}

const formatSubscriptionDisplay = (type: string) => {
  switch (type.toLowerCase()) {
    case 'enterprise': return 'ENTERPRISE'
    case 'smb': return 'PROFESSIONAL'
    case 'startup': return 'STARTER'
    default: return type.toUpperCase()
  }
}

export default function TenantDetailsPage() {
  const params = useParams()
  const tenantId = params.id as string
  
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [usage, setUsage] = useState<TenantUsage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchTenantDetails()
  }, [tenantId])

  const fetchTenantDetails = async () => {
    try {
      setLoading(true)
      setError(null)
      
      // Fetch all tenants and find the specific one
      const tenantsData = await fetchTenants()
      const foundTenant = tenantsData.tenants?.find((t: Tenant) => t.tenant_id === tenantId)
      
      if (!foundTenant) {
        setError('Tenant not found')
        return
      }
      
      setTenant(foundTenant)
      
      // Fetch usage data
      try {
        const usageData = await fetchTenantUsage(tenantId)
        setUsage(usageData)
      } catch (usageError) {
        console.error('Failed to fetch usage data:', usageError)
      }
      
    } catch (error) {
      console.error('Failed to fetch tenant details:', error)
      setError(error instanceof Error ? error.message : 'Failed to fetch tenant details')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-8">
        <div className="flex items-center space-x-4">
          <Link href="/tenants" className="text-blue-600 hover:text-blue-800 flex items-center">
            <ArrowLeft className="h-4 w-4 mr-1" />
            ← Back to Tenants
          </Link>
        </div>
        
        <div className="flex flex-col space-y-2">
          <h1 className="text-3xl font-bold text-gray-900">Loading...</h1>
          <p className="text-gray-600">Fetching tenant details</p>
        </div>
      </div>
    )
  }

  if (error || !tenant) {
    return (
      <div className="space-y-8">
        <div className="flex items-center space-x-4">
          <Link href="/tenants" className="text-blue-600 hover:text-blue-800 flex items-center">
            <ArrowLeft className="h-4 w-4 mr-1" />
            ← Back to Tenants
          </Link>
        </div>
        
        <div className="flex flex-col space-y-2">
          <h1 className="text-3xl font-bold text-red-600">Error</h1>
          <p className="text-gray-600">{error || 'Tenant not found'}</p>
        </div>
      </div>
    )
  }

  const getMonthlyCost = (type: string) => {
    switch (type.toLowerCase()) {
      case 'enterprise': return '$997'
      case 'smb': return '$499'
      case 'startup': return '$99'
      default: return 'Contact Sales'
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link href="/tenants" className="text-blue-600 hover:text-blue-800 flex items-center">
            <ArrowLeft className="h-4 w-4 mr-1" />
            ← Back to Tenants
          </Link>
        </div>
        <Button variant="outline" className="flex items-center">
          <Edit className="h-4 w-4 mr-2" />
          Edit Tenant
        </Button>
      </div>

      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold text-gray-900">{tenant.name}</h1>
        <p className="text-gray-600">Tenant Details & Usage Analytics</p>
      </div>

      {/* Tenant Information */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <Building className="h-5 w-5 mr-2" />
              Organization Details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-500">Tenant ID</label>
              <p className="text-sm font-mono bg-gray-50 p-2 rounded">{tenant.tenant_id}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Organization Name</label>
              <p className="text-base font-medium">{tenant.name}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Industry</label>
              <p className="text-base">{tenant.industry}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Status</label>
              <Badge variant={tenant.status === 'active' ? 'green' : 'red'}>
                {tenant.status.charAt(0).toUpperCase() + tenant.status.slice(1)}
              </Badge>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Subscription Tier</label>
              <Badge variant={getSubscriptionColor(tenant.type)}>
                {formatSubscriptionDisplay(tenant.type)}
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <Mail className="h-5 w-5 mr-2" />
              Contact Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-500">Primary Contact</label>
              <p className="text-base font-medium">{tenant.primary_contact_name}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Email</label>
              <p className="text-base">{tenant.primary_contact_email}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Created</label>
              <p className="text-base">{new Date(tenant.created_at).toLocaleDateString()}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Last Updated</label>
              <p className="text-base">{new Date(tenant.updated_at).toLocaleDateString()}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Usage Analytics */}
      {usage && (
        <Card>
          <CardHeader>
            <CardTitle>Usage Analytics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div className="bg-blue-50 p-4 rounded-lg">
                <h3 className="text-sm font-medium text-blue-600">Logs Today</h3>
                <p className="text-2xl font-bold text-blue-900">{usage.log_count_today.toLocaleString()}</p>
              </div>
              <div className="bg-green-50 p-4 rounded-lg">
                <h3 className="text-sm font-medium text-green-600">Logs This Month</h3>
                <p className="text-2xl font-bold text-green-900">{usage.log_count_month.toLocaleString()}</p>
              </div>
              <div className="bg-purple-50 p-4 rounded-lg">
                <h3 className="text-sm font-medium text-purple-600">Storage Used</h3>
                <p className="text-2xl font-bold text-purple-900">{usage.storage_used_gb.toFixed(1)}GB</p>
              </div>
              <div className="bg-orange-50 p-4 rounded-lg">
                <h3 className="text-sm font-medium text-orange-600">API Calls</h3>
                <p className="text-2xl font-bold text-orange-900">{usage.api_calls.toLocaleString()}</p>
              </div>
              <div className="bg-indigo-50 p-4 rounded-lg">
                <h3 className="text-sm font-medium text-indigo-600">Query Count</h3>
                <p className="text-2xl font-bold text-indigo-900">{usage.query_count.toLocaleString()}</p>
              </div>
              <div className="bg-gray-50 p-4 rounded-lg">
                <h3 className="text-sm font-medium text-gray-600">Monthly Cost</h3>
                <p className="text-2xl font-bold text-gray-900">{getMonthlyCost(tenant.type)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Link href={`/tenants/${tenant.tenant_id}/subscription`}>
              <Button variant="outline" className="flex items-center">
                <CreditCard className="h-4 w-4 mr-2" />
                Manage Subscription
              </Button>
            </Link>
            <Link href="/usage">
              <Button variant="outline" className="flex items-center">
                <Calendar className="h-4 w-4 mr-2" />
                Usage Analytics
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}