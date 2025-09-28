'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ArrowLeft, Edit, Mail, Calendar, Building, Globe, CreditCard, X } from 'lucide-react'
import { fetchTenant, fetchTenantUsage, apiRequest } from '@/lib/api'
import { authService } from '@/lib/auth'

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

const industries = [
  'technology', 'healthcare', 'financial', 'retail', 'manufacturing', 
  'education', 'government', 'non-profit', 'media', 'telecommunications',
  'energy', 'transportation', 'real-estate', 'consulting', 'other'
]

export default function TenantDetailsPage() {
  const params = useParams()
  const tenantId = params.id as string
  
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [usage, setUsage] = useState<TenantUsage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showEditModal, setShowEditModal] = useState(false)
  const [editFormData, setEditFormData] = useState({
    name: '',
    primary_contact_name: '',
    primary_contact_email: '',
    industry: '',
    status: '',
    subscription_tier: ''
  })
  const [editLoading, setEditLoading] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const [editSuccess, setEditSuccess] = useState<string | null>(null)

  useEffect(() => {
    fetchTenantDetails()
  }, [tenantId])

  const fetchTenantDetails = async () => {
    try {
      setLoading(true)
      setError(null)
      
      // Fetch specific tenant directly
      const tenantData = await fetchTenant(tenantId)
      
      if (!tenantData) {
        setError('Tenant not found')
        return
      }
      
      setTenant(tenantData)
      
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

  const handleEditTenant = () => {
    if (tenant) {
      setEditFormData({
        name: tenant.name,
        primary_contact_name: tenant.primary_contact_name,
        primary_contact_email: tenant.primary_contact_email,
        industry: tenant.industry,
        status: tenant.status,
        subscription_tier: tenant.type
      })
      setEditError(null)
      setEditSuccess(null)
      setShowEditModal(true)
    }
  }

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setEditLoading(true)
    setEditError(null)
    setEditSuccess(null)

    try {
      // Debug authentication
      const token = authService.getToken()
      const user = authService.getCurrentUser()
      console.log('🔧 DEBUG: Current token:', token ? 'Present' : 'Missing')
      console.log('🔧 DEBUG: Current user:', user)
      console.log('🔧 DEBUG: Is authenticated:', authService.isAuthenticated())

      const updateData = {
        organization_name: editFormData.name,
        primary_contact_name: editFormData.primary_contact_name,
        primary_contact_email: editFormData.primary_contact_email,
        industry: editFormData.industry,
        status: editFormData.status,
        subscription_tier: editFormData.subscription_tier
      }

      console.log('🔧 DEBUG: Update data:', updateData)

      const response = await apiRequest(`/v1/tenants/${tenantId}`, {
        method: 'PUT',
        body: JSON.stringify(updateData),
      })

      setEditSuccess('Tenant updated successfully!')
      
      // Refresh tenant data
      setTimeout(() => {
        setShowEditModal(false)
        fetchTenantDetails()
      }, 1500)

    } catch (error: any) {
      console.error('🔧 DEBUG: Full error object:', error)
      console.error('🔧 DEBUG: Error message:', error.message)
      
      // Check if it's a 401 authentication error or token expiry
      if (error.message && (error.message.includes('401') || error.message.includes('Failed to fetch'))) {
        // Check if token is expired
        const token = authService.getToken()
        if (!token) {
          setEditError('Your session has expired. Please log in again.')
          setTimeout(() => {
            window.location.href = '/login'
          }, 2000)
        } else {
          setEditError('Authentication failed. Please try logging in again.')
        }
      } else if (error.response?.data?.detail) {
        if (Array.isArray(error.response.data.detail)) {
          const errorMessages = error.response.data.detail.map((err: any) => 
            `${err.loc ? err.loc.join('.') : 'Field'}: ${err.msg}`
          ).join(', ')
          setEditError(`Validation error: ${errorMessages}`)
        } else {
          setEditError(`Error: ${error.response.data.detail}`)
        }
      } else {
        setEditError(`Failed to update tenant: ${error.message}`)
      }
    } finally {
      setEditLoading(false)
    }
  }

  const closeEditModal = () => {
    setShowEditModal(false)
    setEditError(null)
    setEditSuccess(null)
    setEditFormData({
      name: '',
      primary_contact_name: '',
      primary_contact_email: '',
      industry: '',
      status: '',
      subscription_tier: ''
    })
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
        <div className="flex items-center space-x-3">
          <Link href={`/tenants/${tenant.tenant_id}/subscription`}>
            <Button variant="outline" className="flex items-center">
              <CreditCard className="h-4 w-4 mr-2" />
              Manage Subscription
            </Button>
          </Link>
          <Button 
            variant="outline" 
            className="flex items-center"
            onClick={handleEditTenant}
          >
            <Edit className="h-4 w-4 mr-2" />
            Edit Tenant
          </Button>
        </div>
      </div>

      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold text-gray-900">{tenant.name}</h1>
        <p className="text-gray-600">Tenant Details & Configuration</p>
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
                <p className="text-2xl font-bold text-blue-900">{(usage?.log_count_today || 0).toLocaleString()}</p>
              </div>
              <div className="bg-green-50 p-4 rounded-lg">
                <h3 className="text-sm font-medium text-green-600">Logs This Month</h3>
                <p className="text-2xl font-bold text-green-900">{(usage?.log_count_month || 0).toLocaleString()}</p>
              </div>
              <div className="bg-purple-50 p-4 rounded-lg">
                <h3 className="text-sm font-medium text-purple-600">Storage Used</h3>
                <p className="text-2xl font-bold text-purple-900">{(usage?.storage_used_gb || 0).toFixed(1)}GB</p>
              </div>
              <div className="bg-orange-50 p-4 rounded-lg">
                <h3 className="text-sm font-medium text-orange-600">API Calls</h3>
                <p className="text-2xl font-bold text-orange-900">{(usage?.api_calls || 0).toLocaleString()}</p>
              </div>
              <div className="bg-indigo-50 p-4 rounded-lg">
                <h3 className="text-sm font-medium text-indigo-600">Query Count</h3>
                <p className="text-2xl font-bold text-indigo-900">{(usage?.query_count || 0).toLocaleString()}</p>
              </div>
              <div className="bg-gray-50 p-4 rounded-lg">
                <h3 className="text-sm font-medium text-gray-600">Monthly Cost</h3>
                <p className="text-2xl font-bold text-gray-900">{getMonthlyCost(tenant.type)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}


      {/* Edit Tenant Modal */}
      {showEditModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <div>
                <h2 className="text-xl font-semibold text-gray-900">Edit Tenant</h2>
                <p className="text-sm text-gray-600 mt-1">Update tenant information and settings</p>
              </div>
              <button
                onClick={closeEditModal}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="h-6 w-6" />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="p-6 space-y-6">
              {/* Error and Success Messages */}
              {editError && (
                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                  <div className="flex">
                    <div className="ml-3">
                      <h3 className="text-sm font-medium text-red-800">Error</h3>
                      <div className="mt-2 text-sm text-red-700">
                        {editError}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {editSuccess && (
                <div className="bg-green-50 border border-green-200 rounded-md p-4">
                  <div className="flex">
                    <div className="ml-3">
                      <h3 className="text-sm font-medium text-green-800">Success</h3>
                      <div className="mt-2 text-sm text-green-700">
                        {editSuccess}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Read-only fields */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <Label htmlFor="tenant_id" className="text-sm font-medium text-gray-700">
                    Tenant ID (Read-only)
                  </Label>
                  <Input
                    id="tenant_id"
                    value={tenant?.tenant_id || ''}
                    disabled
                    className="mt-1 bg-gray-50 text-gray-500"
                  />
                </div>

                <div>
                  <Label htmlFor="created_at" className="text-sm font-medium text-gray-700">
                    Created Date (Read-only)
                  </Label>
                  <Input
                    id="created_at"
                    value={tenant ? new Date(tenant.created_at).toLocaleDateString() : ''}
                    disabled
                    className="mt-1 bg-gray-50 text-gray-500"
                  />
                </div>
              </div>

              {/* Editable fields */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <Label htmlFor="edit_name" className="text-sm font-medium text-gray-700">
                    Organization Name *
                  </Label>
                  <Input
                    id="edit_name"
                    value={editFormData.name}
                    onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
                    className="mt-1"
                    required
                  />
                </div>

                <div>
                  <Label htmlFor="edit_industry" className="text-sm font-medium text-gray-700">
                    Industry
                  </Label>
                  <Select
                    value={editFormData.industry}
                    onValueChange={(value) => setEditFormData({ ...editFormData, industry: value })}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="Select industry" />
                    </SelectTrigger>
                    <SelectContent>
                      {industries.map(industry => (
                        <SelectItem key={industry} value={industry}>
                          {industry.charAt(0).toUpperCase() + industry.slice(1).replace('-', ' ')}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <Label htmlFor="edit_contact_name" className="text-sm font-medium text-gray-700">
                    Primary Contact Name *
                  </Label>
                  <Input
                    id="edit_contact_name"
                    value={editFormData.primary_contact_name}
                    onChange={(e) => setEditFormData({ ...editFormData, primary_contact_name: e.target.value })}
                    className="mt-1"
                    required
                  />
                </div>

                <div>
                  <Label htmlFor="edit_contact_email" className="text-sm font-medium text-gray-700">
                    Primary Contact Email *
                  </Label>
                  <Input
                    id="edit_contact_email"
                    type="email"
                    value={editFormData.primary_contact_email}
                    onChange={(e) => setEditFormData({ ...editFormData, primary_contact_email: e.target.value })}
                    className="mt-1"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <Label htmlFor="edit_status" className="text-sm font-medium text-gray-700">
                    Status *
                  </Label>
                  <Select
                    value={editFormData.status}
                    onValueChange={(value) => setEditFormData({ ...editFormData, status: value })}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="Select status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="inactive">Inactive</SelectItem>
                      <SelectItem value="pending">Pending</SelectItem>
                      <SelectItem value="suspended">Suspended</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor="edit_subscription_tier" className="text-sm font-medium text-gray-700">
                    Subscription Tier *
                  </Label>
                  <Select
                    value={editFormData.subscription_tier}
                    onValueChange={(value) => setEditFormData({ ...editFormData, subscription_tier: value })}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="Select tier" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="startup">Starter</SelectItem>
                      <SelectItem value="smb">Professional</SelectItem>
                      <SelectItem value="enterprise">Enterprise</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex items-center justify-end space-x-4 pt-6 border-t border-gray-200">
                <Button
                  type="button"
                  variant="outline"
                  onClick={closeEditModal}
                  disabled={editLoading}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={editLoading}
                  className="min-w-[120px]"
                >
                  {editLoading ? (
                    <div className="flex items-center space-x-2">
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      <span>Updating...</span>
                    </div>
                  ) : (
                    'Update Tenant'
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}