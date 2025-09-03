'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Select } from '@/components/ui/select'
import { ArrowLeft, CreditCard, DollarSign, Calendar, CheckCircle, AlertTriangle } from 'lucide-react'
import { fetchTenants, updateTenant } from '@/lib/api'

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

const subscriptionTiers = [
  {
    id: 'startup',
    name: 'STARTER',
    price: 99,
    features: [
      'Up to 1GB log storage',
      '30-day retention',
      'Basic dashboards',
      'Email support',
      'Standard integrations'
    ]
  },
  {
    id: 'smb',
    name: 'PROFESSIONAL', 
    price: 499,
    features: [
      'Up to 50GB log storage',
      '90-day retention',
      'Advanced dashboards',
      'Priority support',
      'Custom integrations',
      'Basic alerting'
    ]
  },
  {
    id: 'enterprise',
    name: 'ENTERPRISE',
    price: 997,
    features: [
      'Unlimited log storage',
      'Custom retention',
      'Full dashboard suite',
      '24/7 dedicated support',
      'Custom integrations',
      'Advanced alerting',
      'SIEM capabilities',
      'Compliance reporting'
    ]
  }
]

const getSubscriptionColor = (type: string) => {
  switch (type.toLowerCase()) {
    case 'enterprise': return 'purple' as const
    case 'smb': return 'blue' as const  
    case 'startup': return 'green' as const
    default: return 'secondary' as const
  }
}

export default function SubscriptionPage() {
  const params = useParams()
  const tenantId = params.id as string
  
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedTier, setSelectedTier] = useState<string>('')

  useEffect(() => {
    fetchTenantDetails()
  }, [tenantId])

  const fetchTenantDetails = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const tenantsData = await fetchTenants()
      const foundTenant = tenantsData.tenants?.find((t: Tenant) => t.tenant_id === tenantId)
      
      if (!foundTenant) {
        setError('Tenant not found')
        return
      }
      
      setTenant(foundTenant)
      setSelectedTier(foundTenant.type)
      
    } catch (error) {
      console.error('Failed to fetch tenant details:', error)
      setError(error instanceof Error ? error.message : 'Failed to fetch tenant details')
    } finally {
      setLoading(false)
    }
  }

  const [updateStatus, setUpdateStatus] = useState<string | null>(null)

  const handleSubscriptionUpdate = async () => {
    try {
      setUpdateStatus('Updating subscription...')
      
      // Make actual API call to update tenant subscription
      console.log(`Updating tenant ${tenantId} subscription to ${selectedTier}`)
      
      await updateTenant(tenantId, {
        type: selectedTier
      })
      
      // Update local state to reflect the change
      setTenant(prev => prev ? { ...prev, type: selectedTier } : null)
      
      const newTierName = subscriptionTiers.find(t => t.id === selectedTier)?.name
      setUpdateStatus(`Successfully updated subscription to ${newTierName}`)
      
      // Auto-dismiss notification after 3 seconds
      setTimeout(() => setUpdateStatus(null), 3000)
      
    } catch (error) {
      console.error('Failed to update subscription:', error)
      setUpdateStatus(`Failed to update subscription: ${error instanceof Error ? error.message : 'Unknown error'}`)
      
      // Auto-dismiss error after 5 seconds
      setTimeout(() => setUpdateStatus(null), 5000)
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
        <div className="text-center">Loading...</div>
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
        <div className="text-center text-red-600">{error || 'Tenant not found'}</div>
      </div>
    )
  }

  const currentTier = subscriptionTiers.find(tier => tier.id === tenant.type)

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
      </div>

      <div className="flex flex-col space-y-2">
        <div className="flex items-center space-x-3">
          <h1 className="text-3xl font-bold text-gray-900">Manage Subscription</h1>
          <Badge variant={getSubscriptionColor(tenant.type)} className="text-sm">
            Current: {currentTier?.name || tenant.type.toUpperCase()}
          </Badge>
        </div>
        <p className="text-xl font-medium text-gray-700">{tenant.name}</p>
        <p className="text-gray-600">Update subscription tier and billing information</p>
      </div>

      {/* Status Notification */}
      {updateStatus && (
        <Card className={`${updateStatus.includes('Failed') ? 'border-red-200 bg-red-50' : 'border-blue-200 bg-blue-50'}`}>
          <CardContent className="p-4">
            <div className="flex items-center">
              {updateStatus.includes('Failed') ? (
                <AlertTriangle className="h-5 w-5 text-red-600 mr-2" />
              ) : (
                <CheckCircle className="h-5 w-5 text-blue-600 mr-2" />
              )}
              <p className={updateStatus.includes('Failed') ? 'text-red-800' : 'text-blue-800'}>
                {updateStatus}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Current Subscription */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <CreditCard className="h-5 w-5 mr-2" />
            Current Subscription
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div>
              <Badge variant={getSubscriptionColor(tenant.type)} className="mb-2">
                {currentTier?.name || tenant.type.toUpperCase()}
              </Badge>
              <p className="text-2xl font-bold">${currentTier?.price}/month</p>
              <p className="text-sm text-gray-500">Billed monthly</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-500">Status</p>
              <div className="flex items-center text-green-600">
                <CheckCircle className="h-4 w-4 mr-1" />
                Active
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Subscription Tiers */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Available Subscription Tiers</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {subscriptionTiers.map((tier) => (
            <Card 
              key={tier.id}
              className={`cursor-pointer transition-all ${
                selectedTier === tier.id ? 'ring-2 ring-blue-500 bg-blue-50' : 'hover:shadow-lg'
              } ${tenant.type === tier.id ? 'border-green-500 bg-green-50' : ''}`}
              onClick={() => setSelectedTier(tier.id)}
            >
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{tier.name}</CardTitle>
                  {tenant.type === tier.id && (
                    <Badge variant="green">Current</Badge>
                  )}
                </div>
                <div className="flex items-center">
                  <DollarSign className="h-5 w-5 text-gray-500" />
                  <span className="text-3xl font-bold">{tier.price}</span>
                  <span className="text-gray-500 ml-1">/month</span>
                </div>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {tier.features.map((feature, index) => (
                    <li key={index} className="flex items-start">
                      <CheckCircle className="h-4 w-4 text-green-500 mr-2 mt-0.5 flex-shrink-0" />
                      <span className="text-sm">{feature}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Update Actions */}
      {selectedTier !== tenant.type && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center text-orange-600">
              <AlertTriangle className="h-5 w-5 mr-2" />
              Subscription Change
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <p className="text-gray-600">
                You are about to change from <strong>{currentTier?.name}</strong> to{' '}
                <strong>{subscriptionTiers.find(t => t.id === selectedTier)?.name}</strong>
              </p>
              <div className="flex space-x-3">
                <Button onClick={handleSubscriptionUpdate} className="bg-blue-600 hover:bg-blue-700">
                  Update Subscription
                </Button>
                <Button variant="outline" onClick={() => setSelectedTier(tenant.type)}>
                  Cancel
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}