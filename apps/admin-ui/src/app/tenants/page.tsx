'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, Plus, ExternalLink, Eye, CreditCard, Search, ChevronUp, ChevronDown, ChevronRight, ChevronLeft } from 'lucide-react'
import { fetchTenants, fetchTenantUsage, createTenant, createTenantWithAdmin, apiRequest } from '@/lib/api'

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
  billing?: { total_cost?: number }
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

const formatDate = (dateString: string) => {
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  } catch {
    return 'N/A'
  }
}

// Simple Tooltip Component
function Tooltip({ children, content }: { children: React.ReactNode, content: string }) {
  const [isVisible, setIsVisible] = useState(false)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const containerRef = React.useRef<HTMLDivElement>(null)
  
  const handleMouseEnter = (e: React.MouseEvent) => {
    setIsVisible(true)
    const rect = e.currentTarget.getBoundingClientRect()
    setPosition({
      x: rect.left + rect.width / 2,
      y: rect.top - 10
    })
  }
  
  return (
    <div 
      ref={containerRef}
      className="relative inline-block"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={() => setIsVisible(false)}
    >
      {children}
      {isVisible && (
        <div 
          className="fixed transform -translate-x-1/2 -translate-y-full px-3 py-2 text-sm text-white bg-gray-900 rounded-md shadow-lg whitespace-nowrap z-50 pointer-events-none"
          style={{
            left: `${position.x}px`,
            top: `${position.y}px`,
          }}
        >
          {content}
          <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-900"></div>
        </div>
      )}
    </div>
  )
}

interface OnboardingModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

function OnboardingModal({ isOpen, onClose, onSuccess }: OnboardingModalProps) {
  const [formData, setFormData] = useState({
    organizationName: '',
    domain: '',
    subscriptionTier: '',
    status: 'pending',
    billingEmail: '',
    adminContact: '',
    adminContactEmail: '',
    industry: '',
    region: 'us-east-1',
    complianceRequirements: [] as string[]
  })

  const [selectedCompliance, setSelectedCompliance] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const [showSuccess, setShowSuccess] = useState(false)
  const [successInfo, setSuccessInfo] = useState<any>(null)

  // Dropdown options
  const subscriptionTiers = [
    { value: 'startup', label: 'Startup' },
    { value: 'smb', label: 'SMB' },
    { value: 'enterprise', label: 'Enterprise' },
    { value: 'non_profit', label: 'Non-Profit' },
    { value: 'government', label: 'Government' },
    { value: 'education', label: 'Education' },
    { value: 'healthcare', label: 'Healthcare' },
    { value: 'financial', label: 'Financial Services' }
  ]

  const statusOptions = [
    { value: 'pending', label: 'Pending Activation' },
    { value: 'active', label: 'Active' },
    { value: 'inactive', label: 'Inactive' },
    { value: 'suspended', label: 'Suspended' }
  ]

  const regions = [
    { value: 'us-east-1', label: 'US East (N. Virginia)' },
    { value: 'us-west-2', label: 'US West (Oregon)' },
    { value: 'eu-west-1', label: 'Europe (Ireland)' },
    { value: 'eu-central-1', label: 'Europe (Frankfurt)' },
    { value: 'ap-southeast-1', label: 'Asia Pacific (Singapore)' },
    { value: 'ap-northeast-1', label: 'Asia Pacific (Tokyo)' },
    { value: 'ca-central-1', label: 'Canada (Central)' }
  ]

  const industries = [
    'technology', 'healthcare', 'financial', 'retail', 'manufacturing', 
    'education', 'government', 'non-profit', 'media', 'telecommunications',
    'energy', 'transportation', 'real-estate', 'consulting', 'other'
  ]

  const complianceOptions = [
    'GDPR', 'HIPAA', 'SOX', 'PCI-DSS', 'SOC2', 'FISMA', 'FedRAMP', 'ISO27001'
  ]

  const addComplianceRequirement = () => {
    if (selectedCompliance && !formData.complianceRequirements.includes(selectedCompliance)) {
      setFormData(prev => ({
        ...prev,
        complianceRequirements: [...prev.complianceRequirements, selectedCompliance]
      }))
      setSelectedCompliance('')
    }
  }

  const removeComplianceRequirement = (requirement: string) => {
    setFormData(prev => ({
      ...prev,
      complianceRequirements: prev.complianceRequirements.filter(req => req !== requirement)
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Clear previous errors
    setErrors([])
    
    // Validate required fields
    const requiredFields = [
      { field: formData.organizationName, name: 'Organization Name' },
      { field: formData.domain, name: 'Domain' },
      { field: formData.subscriptionTier, name: 'Subscription Tier' },
      { field: formData.billingEmail, name: 'Billing Email' },
      { field: formData.adminContact, name: 'Admin Contact Name' },
      { field: formData.adminContactEmail, name: 'Admin Contact Email' }
    ]
    
    const missingFields = requiredFields.filter(field => !field.field).map(field => field.name)
    
    if (missingFields.length > 0) {
      setErrors([`Required fields missing: ${missingFields.join(', ')}`])
      return
    }

    setIsSubmitting(true)

    try {
      // Map form data to API expected format
      const tenantData = {
        name: formData.organizationName,                    // API expects 'name'
        type: formData.subscriptionTier,                    // API expects 'type'  
        primary_contact_name: formData.adminContact,        // API expects 'primary_contact_name'
        primary_contact_email: formData.adminContactEmail,  // API expects 'primary_contact_email'
        domain: formData.domain,
        status: formData.status,
        billing_email: formData.billingEmail,
        industry: formData.industry,
        region: formData.region,
        compliance_requirements: formData.complianceRequirements
      }
      
      // Use enhanced tenant creation with admin user
      const result = await createTenantWithAdmin(tenantData)
      console.log('🎉 Tenant creation workflow completed:', result)
      
      // Store success info for display
      setSuccessInfo(result)
      
      // Show success state with admin user info
      setShowSuccess(true)
      
      // Close modal and reset form after success
      setTimeout(() => {
        setShowSuccess(false)
        onClose()
        setFormData({
          organizationName: '',
          domain: '',
          subscriptionTier: '',
          status: 'pending',
          billingEmail: '',
          adminContact: '',
          adminContactEmail: '',
          industry: '',
          region: 'us-east-1',
          complianceRequirements: []
        })
        setSelectedCompliance('')
        setErrors([])
        // Refresh the tenant list and stats without full page reload
        onSuccess()
      }, 1500)
      
    } catch (error: any) {
      console.error('Failed to create tenant:', error)
      
      // Parse API error response
      if (error?.response?.data?.detail) {
        if (Array.isArray(error.response.data.detail)) {
          // Pydantic validation errors
          const validationErrors = error.response.data.detail.map((err: any) => 
            `${err.loc?.join('.')} is ${err.msg || 'invalid'}`
          )
          setErrors(validationErrors)
        } else {
          setErrors([error.response.data.detail])
        }
      } else if (error?.message) {
        setErrors([error.message])
      } else {
        setErrors(['Failed to create tenant. Please try again.'])
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto">
      <div className="bg-white rounded-lg p-6 w-full max-w-4xl m-4 max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-semibold mb-6">Onboard New Tenant</h2>
        
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Error Messages */}
          {errors.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-md p-4">
              <div className="flex">
                <div className="text-sm text-red-600">
                  <ul className="list-disc list-inside space-y-1">
                    {errors.map((error, index) => (
                      <li key={index}>{error}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* Success Message */}
          {showSuccess && (
            <div className="bg-green-50 border border-green-200 rounded-md p-4">
              <div className="flex">
                <div className="text-sm text-green-600">
                  ✓ Tenant created successfully! Refreshing...
                </div>
              </div>
            </div>
          )}

          {/* Basic Information */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                Domain *
              </label>
              <Input
                type="text"
                value={formData.domain}
                onChange={(e) => setFormData(prev => ({ ...prev, domain: e.target.value }))}
                placeholder="company.com"
                required
              />
            </div>
          </div>

          {/* Contact Information */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Billing Email *
              </label>
              <Input
                type="email"
                value={formData.billingEmail}
                onChange={(e) => setFormData(prev => ({ ...prev, billingEmail: e.target.value }))}
                placeholder="billing@company.com"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Admin Contact Name *
              </label>
              <Input
                type="text"
                value={formData.adminContact}
                onChange={(e) => setFormData(prev => ({ ...prev, adminContact: e.target.value }))}
                placeholder="John Doe"
                required
              />
            </div>
          </div>

          {/* Admin Contact Email */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Admin Contact Email *
            </label>
            <Input
              type="email"
              value={formData.adminContactEmail}
              onChange={(e) => setFormData(prev => ({ ...prev, adminContactEmail: e.target.value }))}
              placeholder="admin@company.com"
              required
            />
          </div>

          {/* Subscription & Status */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Subscription Tier *
              </label>
              <select
                value={formData.subscriptionTier}
                onChange={(e) => setFormData(prev => ({ ...prev, subscriptionTier: e.target.value }))}
                className="w-full border border-gray-300 rounded-md px-3 py-2"
                required
              >
                <option value="">Select subscription tier</option>
                {subscriptionTiers.map(tier => (
                  <option key={tier.value} value={tier.value}>{tier.label}</option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Initial Status
              </label>
              <select
                value={formData.status}
                onChange={(e) => setFormData(prev => ({ ...prev, status: e.target.value }))}
                className="w-full border border-gray-300 rounded-md px-3 py-2"
              >
                {statusOptions.map(status => (
                  <option key={status.value} value={status.value}>{status.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Industry & Region */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Industry
              </label>
              <select
                value={formData.industry}
                onChange={(e) => setFormData(prev => ({ ...prev, industry: e.target.value }))}
                className="w-full border border-gray-300 rounded-md px-3 py-2"
              >
                <option value="">Select industry</option>
                {industries.map(industry => (
                  <option key={industry} value={industry}>
                    {industry.charAt(0).toUpperCase() + industry.slice(1).replace('-', ' ')}
                  </option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Region
              </label>
              <select
                value={formData.region}
                onChange={(e) => setFormData(prev => ({ ...prev, region: e.target.value }))}
                className="w-full border border-gray-300 rounded-md px-3 py-2"
              >
                {regions.map(region => (
                  <option key={region.value} value={region.value}>{region.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Compliance Requirements */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Compliance Requirements
            </label>
            <div className="flex gap-2 mb-2">
              <select
                value={selectedCompliance}
                onChange={(e) => setSelectedCompliance(e.target.value)}
                className="flex-1 border border-gray-300 rounded-md px-3 py-2"
              >
                <option value="">Select compliance standard</option>
                {complianceOptions.map(option => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
              <Button type="button" onClick={addComplianceRequirement} variant="outline">
                Add
              </Button>
            </div>
            {formData.complianceRequirements.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {formData.complianceRequirements.map(req => (
                  <span
                    key={req}
                    className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                  >
                    {req}
                    <button
                      type="button"
                      onClick={() => removeComplianceRequirement(req)}
                      className="ml-2 text-blue-600 hover:text-blue-800"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Form Actions */}
          <div className="flex justify-end space-x-2 pt-4 border-t">
            <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Creating...
                </>
              ) : (
                'Create Tenant'
              )}
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
  const [tenantUsages, setTenantUsages] = useState<Record<string, TenantUsage | null>>({})
  const [tenantStats, setTenantStats] = useState<TenantStats[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [sortField, setSortField] = useState<string | null>(null)
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const [expandedTenants, setExpandedTenants] = useState<Set<string>>(new Set())
  const [loadingUsage, setLoadingUsage] = useState<Set<string>>(new Set())
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [pageSize] = useState(50)

  useEffect(() => {
    fetchTenantsData()
  }, [currentPage])

  const fetchTenantsData = async () => {
    try {
      setLoading(true)
      
      // Fetch tenant statistics and paginated tenant list
      const [statsData, tenantsData] = await Promise.all([
        apiRequest('/v1/tenants/stats'),
        apiRequest(`/v1/tenants?page=${currentPage}&page_size=${pageSize}`)
      ])
      
      setTenants(tenantsData.tenants || [])
      
      // Set pagination data from API response
      setTotalCount(tenantsData.total_count || 0)
      setTotalPages(tenantsData.total_pages || 1)
      
      // Use lightweight stats endpoint for accurate counts
      const totalTenants = statsData.total_tenants || 0
      const activeTenants = statsData.active_tenants || 0
      
      // Calculate enterprise count from current page (until backend supports this)
      const enterpriseCount = tenantsData.tenants.filter((t: Tenant) => t.type === 'enterprise').length
      
      setTenantStats([
        { title: "Total Tenants", value: totalTenants.toString(), description: "All registered tenants" },
        { title: "Active Tenants", value: activeTenants.toString(), description: "Currently active tenants" },
        { title: "Enterprise Customers", value: enterpriseCount.toString(), description: "From current page" },
        { title: "Pending Activation", value: (statsData.pending_tenants || 0).toString(), description: "Awaiting activation" }
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

  // Pagination functions
  const goToPage = (page: number) => {
    if (page >= 1 && page <= totalPages && page !== currentPage) {
      setCurrentPage(page)
      setExpandedTenants(new Set()) // Clear expanded state when changing pages
    }
  }

  const goToNextPage = () => {
    if (currentPage < totalPages) {
      goToPage(currentPage + 1)
    }
  }

  const goToPreviousPage = () => {
    if (currentPage > 1) {
      goToPage(currentPage - 1)
    }
  }

  // Function to toggle tenant expansion and fetch usage data
  const toggleTenantExpansion = async (tenantId: string) => {
    const newExpandedTenants = new Set(expandedTenants)
    
    if (expandedTenants.has(tenantId)) {
      // Collapse tenant
      newExpandedTenants.delete(tenantId)
    } else {
      // Expand tenant and fetch usage data if not already fetched
      newExpandedTenants.add(tenantId)
      
      if (!tenantUsages[tenantId]) {
        // Add to loading state
        setLoadingUsage(prev => new Set([...prev, tenantId]))
        
        try {
          const usageData = await fetchTenantUsage(tenantId)
          setTenantUsages(prev => ({ ...prev, [tenantId]: usageData }))
        } catch (error) {
          console.error(`Failed to fetch usage for tenant ${tenantId}:`, error)
          setTenantUsages(prev => ({ ...prev, [tenantId]: null }))
        } finally {
          // Remove from loading state
          setLoadingUsage(prev => {
            const newSet = new Set(prev)
            newSet.delete(tenantId)
            return newSet
          })
        }
      }
    }
    
    setExpandedTenants(newExpandedTenants)
  }

  // Filter tenants based on search term
  const filteredTenants = tenants.filter(tenant => {
    if (!searchTerm) return true
    
    const searchLower = searchTerm.toLowerCase()
    return (
      tenant.name.toLowerCase().includes(searchLower) ||
      tenant.tenant_id.toLowerCase().includes(searchLower) ||
      tenant.primary_contact_email.toLowerCase().includes(searchLower)
    )
  })

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

      {/* Search and Actions */}
      <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
        <div className="relative w-full sm:w-96">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-5 w-5 text-gray-400" />
          </div>
          <Input
            type="text"
            placeholder="Search by organization name, tenant ID, or email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10 pr-4 py-2 w-full border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <Button 
          onClick={() => setShowOnboardingModal(true)}
          className="bg-blue-600 text-white hover:bg-blue-700 whitespace-nowrap"
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
                  Contact
                </th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider hidden xl:table-cell">
                  Created
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
              ) : filteredTenants.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                    {searchTerm ? `No tenants found matching "${searchTerm}"` : 'No tenants found'}
                  </td>
                </tr>
              ) : (
                filteredTenants.map((tenant) => {
                  const isExpanded = expandedTenants.has(tenant.tenant_id)
                  const usage = tenantUsages[tenant.tenant_id]
                  const isLoadingUsage = loadingUsage.has(tenant.tenant_id)
                  
                  // Use real billing cost from usage data, fallback to $0 if not available
                  const monthlyCost = usage?.billing?.total_cost 
                    ? `$${usage.billing.total_cost.toFixed(2)}`
                    : '$0.00'
                  
                  return (
                    <React.Fragment key={tenant.tenant_id}>
                      {/* Main tenant row */}
                      <tr className="hover:bg-gray-50">
                        <td className="px-4 py-4">
                          <div className="flex items-center">
                            <button
                              onClick={() => toggleTenantExpansion(tenant.tenant_id)}
                              className="mr-2 p-1 text-gray-400 hover:text-gray-600 transition-colors"
                              title="Expand for usage details"
                            >
                              {isExpanded ? (
                                <ChevronDown className="h-4 w-4" />
                              ) : (
                                <ChevronRight className="h-4 w-4" />
                              )}
                            </button>
                            <div>
                              <div className="text-sm font-medium text-gray-900">{tenant.name}</div>
                              <div className="text-xs text-gray-500 md:hidden font-mono">{tenant.tenant_id.slice(0, 8)}...</div>
                            </div>
                          </div>
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
                          <div className="text-sm text-gray-600">{tenant.primary_contact_email}</div>
                        </td>
                        <td className="px-3 py-4 hidden xl:table-cell">
                          <div className="text-sm text-gray-600">{formatDate(tenant.created_at)}</div>
                        </td>
                        <td className="px-3 py-4">
                          <div className="flex justify-center space-x-1">
                            <Tooltip content="View tenant details and configuration">
                              <Link 
                                href={`/tenants/${tenant.tenant_id}`} 
                                className="p-2 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-md transition-colors"
                              >
                                <Eye className="h-4 w-4" />
                              </Link>
                            </Tooltip>
                            <Tooltip content="Manage subscription and billing">
                              <Link 
                                href={`/tenants/${tenant.tenant_id}/subscription`} 
                                className="p-2 text-purple-600 hover:text-purple-800 hover:bg-purple-50 rounded-md transition-colors"
                              >
                                <CreditCard className="h-4 w-4" />
                              </Link>
                            </Tooltip>
                          </div>
                        </td>
                      </tr>

                      {/* Expanded usage details row */}
                      {isExpanded && (
                        <tr className="bg-gray-50">
                          <td colSpan={7} className="px-4 py-4">
                            <div className="ml-6 pl-4 border-l-2 border-gray-200">
                              {isLoadingUsage ? (
                                <div className="flex items-center space-x-2 text-gray-500">
                                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-500"></div>
                                  <span className="text-sm">Loading usage data...</span>
                                </div>
                              ) : usage ? (
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                                  <div>
                                    <span className="text-gray-500">Storage:</span>
                                    <div className="font-medium">{(usage.storage_used_gb || 0).toFixed(1)}GB</div>
                                  </div>
                                  <div>
                                    <span className="text-gray-500">Monthly Cost:</span>
                                    <div className="font-medium">{monthlyCost}</div>
                                  </div>
                                  <div>
                                    <span className="text-gray-500">Logs Today:</span>
                                    <div className="font-medium">{(usage.log_count_today || 0).toLocaleString()}</div>
                                  </div>
                                  <div>
                                    <span className="text-gray-500">API Calls:</span>
                                    <div className="font-medium">{(usage.api_calls || 0).toLocaleString()}</div>
                                  </div>
                                  <div>
                                    <span className="text-gray-500">Logs This Month:</span>
                                    <div className="font-medium">{(usage.log_count_month || 0).toLocaleString()}</div>
                                  </div>
                                  <div>
                                    <span className="text-gray-500">Queries:</span>
                                    <div className="font-medium">{(usage.query_count || 0).toLocaleString()}</div>
                                  </div>
                                  <div>
                                    <span className="text-gray-500">Industry:</span>
                                    <div className="font-medium capitalize">{tenant.industry || 'N/A'}</div>
                                  </div>
                                  <div>
                                    <span className="text-gray-500">Contact:</span>
                                    <div className="font-medium">{tenant.primary_contact_name || 'N/A'}</div>
                                  </div>
                                </div>
                              ) : (
                                <div className="text-sm text-red-600">
                                  Failed to load usage data
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Pagination */}
      {!loading && totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="flex items-center text-sm text-gray-500">
            <span>
              Showing {((currentPage - 1) * pageSize) + 1} to {Math.min(currentPage * pageSize, totalCount)} of {totalCount} tenants
            </span>
          </div>
          
          <div className="flex items-center space-x-2">
            {/* Previous Button */}
            <Button
              variant="outline"
              onClick={goToPreviousPage}
              disabled={currentPage === 1}
              className="flex items-center space-x-1"
            >
              <ChevronLeft className="h-4 w-4" />
              <span>Previous</span>
            </Button>

            {/* Page Numbers */}
            <div className="flex items-center space-x-1">
              {/* First page */}
              {currentPage > 3 && (
                <>
                  <Button
                    variant={1 === currentPage ? "default" : "outline"}
                    onClick={() => goToPage(1)}
                    className="w-10 h-10 p-0"
                  >
                    1
                  </Button>
                  {currentPage > 4 && (
                    <span className="px-2 text-gray-400">...</span>
                  )}
                </>
              )}

              {/* Pages around current page */}
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNum = currentPage - 2 + i
                if (currentPage <= 2) {
                  pageNum = i + 1
                } else if (currentPage >= totalPages - 1) {
                  pageNum = totalPages - 4 + i
                }
                
                if (pageNum < 1 || pageNum > totalPages) return null
                
                return (
                  <Button
                    key={pageNum}
                    variant={pageNum === currentPage ? "default" : "outline"}
                    onClick={() => goToPage(pageNum)}
                    className="w-10 h-10 p-0"
                  >
                    {pageNum}
                  </Button>
                )
              })}

              {/* Last page */}
              {currentPage < totalPages - 2 && (
                <>
                  {currentPage < totalPages - 3 && (
                    <span className="px-2 text-gray-400">...</span>
                  )}
                  <Button
                    variant={totalPages === currentPage ? "default" : "outline"}
                    onClick={() => goToPage(totalPages)}
                    className="w-10 h-10 p-0"
                  >
                    {totalPages}
                  </Button>
                </>
              )}
            </div>

            {/* Next Button */}
            <Button
              variant="outline"
              onClick={goToNextPage}
              disabled={currentPage === totalPages}
              className="flex items-center space-x-1"
            >
              <span>Next</span>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Onboarding Modal */}
      <OnboardingModal 
        isOpen={showOnboardingModal}
        onClose={() => setShowOnboardingModal(false)}
        onSuccess={fetchTenantsData}
      />
    </div>
  )
}