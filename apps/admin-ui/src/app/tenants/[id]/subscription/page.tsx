'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ArrowLeft, CreditCard, CheckCircle, AlertTriangle, Calendar, DollarSign, User, Settings } from 'lucide-react'
import { apiRequest } from '@/lib/api'
import { authService } from '@/lib/auth'

interface Subscription {
  tenant_id: string
  subscribed_features: string[]
  subscription_tier: string
  billing_cycle: string
  status: string
  started_at: string
  expires_at: string
  auto_renew: boolean
  monthly_spend_limit?: number
  current_usage: Record<string, number>
}

interface BillingHistory {
  bill_id: string
  billing_period: string
  total_amount: number
  currency: string
  generated_at: string
  due_date: string
  status: string
}

interface AvailableFeatures {
  feature_categories: Record<string, string[]>
}

const getTierColor = (tier: string) => {
  switch (tier.toLowerCase()) {
    case 'enterprise': return 'purple' as const
    case 'financial': return 'purple' as const
    case 'healthcare': return 'blue' as const  
    case 'government': return 'blue' as const
    case 'smb': return 'blue' as const
    case 'education': return 'green' as const
    case 'startup': return 'green' as const
    case 'non_profit': return 'green' as const
    default: return 'secondary' as const
  }
}

const getTierPrice = (tier: string) => {
  switch (tier.toLowerCase()) {
    case 'financial': return '$399 base + usage'
    case 'enterprise': return '$299 base + usage'
    case 'healthcare': return '$199 base + usage'
    case 'government': return '$199 base + usage'
    case 'smb': return '$99 base + usage'
    case 'education': return '$39 base + usage'
    case 'startup': return '$25 base + usage'
    case 'non_profit': return '$15 base + usage'
    default: return 'Usage-based'
  }
}

const formatTierDisplay = (tier: string) => {
  switch (tier.toLowerCase()) {
    case 'startup': return 'STARTUP'
    case 'smb': return 'SMB'
    case 'enterprise': return 'ENTERPRISE'
    case 'non_profit': return 'NON-PROFIT'
    case 'government': return 'GOVERNMENT'
    case 'education': return 'EDUCATION'
    case 'healthcare': return 'HEALTHCARE'
    case 'financial': return 'FINANCIAL SERVICES'
    default: return tier.toUpperCase()
  }
}

export default function SubscriptionManagementPage() {
  const params = useParams()
  const tenantId = params.id as string
  
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [billingHistory, setBillingHistory] = useState<BillingHistory[]>([])
  const [availableFeatures, setAvailableFeatures] = useState<AvailableFeatures | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)

  const [selectedTier, setSelectedTier] = useState<string>('')
  const [showUpgradeForm, setShowUpgradeForm] = useState(false)
  const [promoCode, setPromoCode] = useState<string>('')
  const [promoDiscount, setPromoDiscount] = useState<number>(0)
  const [promoError, setPromoError] = useState<string>('')

  useEffect(() => {
    fetchSubscriptionData()
  }, [tenantId])

  const fetchSubscriptionData = async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch subscription details
      const subscriptionData = await apiRequest(`/v1/tenants/${tenantId}/subscription`)
      setSubscription(subscriptionData)
      setSelectedTier(subscriptionData.subscription_tier)

      // Fetch billing history
      try {
        const billingData = await apiRequest(`/v1/tenants/${tenantId}/billing/history`)
        setBillingHistory(billingData.bills || [])
      } catch (billingError) {
        console.error('Failed to fetch billing history:', billingError)
      }

      // Fetch available features
      try {
        const featuresData = await apiRequest('/v1/features/available')
        setAvailableFeatures(featuresData)
      } catch (featuresError) {
        console.error('Failed to fetch available features:', featuresError)
      }

    } catch (error) {
      console.error('Failed to fetch subscription data:', error)
      setError(error instanceof Error ? error.message : 'Failed to fetch subscription data')
    } finally {
      setLoading(false)
    }
  }

  const handleTierUpgrade = async () => {
    if (!selectedTier || selectedTier === subscription?.subscription_tier) return

    try {
      setActionLoading(true)

      // Get features for the selected tier from the subscription service
      let features: string[] = []
      try {
        const featuresResponse = await apiRequest(`/v1/features/tier/${selectedTier}`)
        features = featuresResponse.features || []
      } catch (featuresError) {
        console.error('Failed to get features for tier:', featuresError)
        // Fallback: use basic features
        features = ['ingestion.basic', 'storage.hot', 'queries.basic']
      }

      const updateData = {
        subscribed_features: features,
        subscription_tier: selectedTier,
        billing_cycle: 'monthly',
        auto_renew: true
      }

      await apiRequest(`/v1/tenants/${tenantId}/subscription`, {
        method: 'PUT',
        body: JSON.stringify(updateData),
      })

      // Refresh data
      await fetchSubscriptionData()
      setShowUpgradeForm(false)

    } catch (error) {
      console.error('Failed to update subscription:', error)
      setError('Failed to update subscription: ' + (error instanceof Error ? error.message : 'Unknown error'))
    } finally {
      setActionLoading(false)
    }
  }

  const generateBill = async () => {
    try {
      setActionLoading(true)
      
      const billData = await apiRequest(`/v1/tenants/${tenantId}/billing/generate`, {
        method: 'POST',
        body: JSON.stringify({
          billing_period: 'current',
          include_usage_details: true
        })
      })

      // Refresh billing history
      const billingData = await apiRequest(`/v1/tenants/${tenantId}/billing/history`)
      setBillingHistory(billingData.bills || [])

    } catch (error) {
      console.error('Failed to generate bill:', error)
      setError('Failed to generate bill: ' + (error instanceof Error ? error.message : 'Unknown error'))
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-8">
        <div className="flex items-center space-x-4">
          <Link href={`/tenants/${tenantId}`} className="text-blue-600 hover:text-blue-800 flex items-center">
            <ArrowLeft className="h-4 w-4 mr-1" />
            ← Back to Tenant Details
          </Link>
        </div>
        
        <div className="flex flex-col space-y-2">
          <h1 className="text-3xl font-bold text-gray-900">Loading...</h1>
          <p className="text-gray-600">Fetching subscription details</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-8">
        <div className="flex items-center space-x-4">
          <Link href={`/tenants/${tenantId}`} className="text-blue-600 hover:text-blue-800 flex items-center">
            <ArrowLeft className="h-4 w-4 mr-1" />
            ← Back to Tenant Details
          </Link>
        </div>
        
        <div className="flex flex-col space-y-2">
          <h1 className="text-3xl font-bold text-red-600">Error</h1>
          <p className="text-gray-600">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link href={`/tenants/${tenantId}`} className="text-blue-600 hover:text-blue-800 flex items-center">
            <ArrowLeft className="h-4 w-4 mr-1" />
            ← Back to Tenant Details
          </Link>
        </div>
        <div className="flex items-center space-x-3">
          <Button 
            variant="outline" 
            onClick={() => setShowUpgradeForm(!showUpgradeForm)}
            className="flex items-center"
          >
            <Settings className="h-4 w-4 mr-2" />
            Change Subscription
          </Button>
          <Button 
            variant="outline" 
            onClick={generateBill}
            disabled={actionLoading}
            className="flex items-center"
          >
            <DollarSign className="h-4 w-4 mr-2" />
            Generate Bill
          </Button>
        </div>
      </div>

      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold text-gray-900">Subscription Management</h1>
        <p className="text-gray-600">Manage billing, features, and subscription settings</p>
      </div>

      {/* Current Subscription */}
      {subscription && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <CreditCard className="h-5 w-5 mr-2" />
                Current Subscription
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium text-gray-500">Subscription Tier</label>
                <div className="flex items-center space-x-2">
                  <Badge variant={getTierColor(subscription.subscription_tier)}>
                    {formatTierDisplay(subscription.subscription_tier)}
                  </Badge>
                  <span className="text-lg font-semibold">{getTierPrice(subscription.subscription_tier)}/month</span>
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-500">Status</label>
                <div className="flex items-center space-x-2">
                  <Badge variant={subscription.status === 'active' ? 'green' : 'red'}>
                    {subscription.status.charAt(0).toUpperCase() + subscription.status.slice(1)}
                  </Badge>
                  {subscription.status === 'active' && (
                    <CheckCircle className="h-4 w-4 text-green-500" />
                  )}
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-500">Billing Cycle</label>
                <p className="text-base">{subscription.billing_cycle.charAt(0).toUpperCase() + subscription.billing_cycle.slice(1)}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-500">Auto Renewal</label>
                <p className="text-base">{subscription.auto_renew ? 'Enabled' : 'Disabled'}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-500">Expires</label>
                <p className="text-base">{new Date(subscription.expires_at).toLocaleDateString()}</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <User className="h-5 w-5 mr-2" />
                Subscription Features
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-gray-500">
                    Active Features ({subscription.subscribed_features.length})
                  </label>
                  <Badge variant="outline" className="text-xs">
                    {formatTierDisplay(subscription.subscription_tier)}
                  </Badge>
                </div>
                
                {/* Organize features by category */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Ingestion Features */}
                  {subscription.subscribed_features.some(f => f.startsWith('ingestion') || f === '*') && (
                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold text-blue-700">Ingestion</h4>
                      <div className="space-y-1">
                        {subscription.subscribed_features.filter(f => f.startsWith('ingestion') || f === '*').map((feature, index) => (
                          <div key={index} className="flex items-center space-x-2">
                            <CheckCircle className="h-3 w-3 text-green-500" />
                            <span className="text-xs">{feature === '*' ? 'All' : feature.replace('ingestion.', '').replace(/\./g, ' ')}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Storage Features */}
                  {subscription.subscribed_features.some(f => f.startsWith('storage') || f === '*') && (
                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold text-purple-700">Storage</h4>
                      <div className="space-y-1">
                        {subscription.subscribed_features.filter(f => f.startsWith('storage') || f === '*').map((feature, index) => (
                          <div key={index} className="flex items-center space-x-2">
                            <CheckCircle className="h-3 w-3 text-green-500" />
                            <span className="text-xs">{feature === '*' ? 'All' : feature.replace('storage.', '').replace(/\./g, ' ')}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Query Features */}
                  {subscription.subscribed_features.some(f => f.startsWith('queries') || f === '*') && (
                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold text-green-700">Queries</h4>
                      <div className="space-y-1">
                        {subscription.subscribed_features.filter(f => f.startsWith('queries') || f === '*').map((feature, index) => (
                          <div key={index} className="flex items-center space-x-2">
                            <CheckCircle className="h-3 w-3 text-green-500" />
                            <span className="text-xs">{feature === '*' ? 'All' : feature.replace('queries.', '').replace(/\./g, ' ')}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Alerts Features */}
                  {subscription.subscribed_features.some(f => f.startsWith('alerts') || f === '*') && (
                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold text-orange-700">Alerts</h4>
                      <div className="space-y-1">
                        {subscription.subscribed_features.filter(f => f.startsWith('alerts') || f === '*').map((feature, index) => (
                          <div key={index} className="flex items-center space-x-2">
                            <CheckCircle className="h-3 w-3 text-green-500" />
                            <span className="text-xs">{feature === '*' ? 'All' : feature.replace('alerts.', '').replace(/\./g, ' ')}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Dashboards Features */}
                  {subscription.subscribed_features.some(f => f.startsWith('dashboards') || f === '*') && (
                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold text-indigo-700">Dashboards</h4>
                      <div className="space-y-1">
                        {subscription.subscribed_features.filter(f => f.startsWith('dashboards') || f === '*').map((feature, index) => (
                          <div key={index} className="flex items-center space-x-2">
                            <CheckCircle className="h-3 w-3 text-green-500" />
                            <span className="text-xs">{feature === '*' ? 'All' : feature.replace('dashboards.', '').replace(/\./g, ' ')}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Security Features */}
                  {subscription.subscribed_features.some(f => f.startsWith('security') || f === '*') && (
                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold text-red-700">Security</h4>
                      <div className="space-y-1">
                        {subscription.subscribed_features.filter(f => f.startsWith('security') || f === '*').map((feature, index) => (
                          <div key={index} className="flex items-center space-x-2">
                            <CheckCircle className="h-3 w-3 text-green-500" />
                            <span className="text-xs">{feature === '*' ? 'All' : feature.replace('security.', '').replace(/\./g, ' ')}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Enterprise Features */}
                  {subscription.subscribed_features.some(f => f.startsWith('enterprise') || f.startsWith('observability') || f.startsWith('ai_assistant') || f.startsWith('export') || f === '*') && (
                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold text-gray-700">Advanced</h4>
                      <div className="space-y-1">
                        {subscription.subscribed_features.filter(f => 
                          f.startsWith('enterprise') || 
                          f.startsWith('observability') || 
                          f.startsWith('ai_assistant') || 
                          f.startsWith('export') ||
                          f === '*'
                        ).map((feature, index) => (
                          <div key={index} className="flex items-center space-x-2">
                            <CheckCircle className="h-3 w-3 text-green-500" />
                            <span className="text-xs">{feature === '*' ? 'All' : feature.replace(/^(enterprise|observability|ai_assistant|export)\./, '').replace(/\./g, ' ')}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Show enterprise wildcard message */}
                {subscription.subscribed_features.includes('*') && (
                  <div className="mt-4 p-3 bg-purple-50 border border-purple-200 rounded-lg">
                    <div className="flex items-center space-x-2">
                      <CheckCircle className="h-4 w-4 text-purple-600" />
                      <span className="text-sm font-medium text-purple-800">Enterprise Tier</span>
                    </div>
                    <p className="text-xs text-purple-700 mt-1">
                      This subscription includes access to all Logforge platform features and capabilities.
                    </p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Change Subscription Form */}
      {showUpgradeForm && (
        <Card>
          <CardHeader>
            <CardTitle>Change Subscription Tier</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div>
              <label className="text-sm font-medium text-gray-700 mb-2 block">
                Select New Subscription Tier
              </label>
              <Select value={selectedTier} onValueChange={setSelectedTier}>
                <SelectTrigger>
                  <SelectValue placeholder="Select subscription tier" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="startup">
                    <div className="flex items-center justify-between w-full">
                      <span>Startup</span>
                      <span className="ml-4 text-gray-500">$25 base + usage</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="smb">
                    <div className="flex items-center justify-between w-full">
                      <span>SMB</span>
                      <span className="ml-4 text-gray-500">$99 base + usage</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="enterprise">
                    <div className="flex items-center justify-between w-full">
                      <span>Enterprise</span>
                      <span className="ml-4 text-gray-500">$299 base + usage</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="non_profit">
                    <div className="flex items-center justify-between w-full">
                      <span>Non-Profit</span>
                      <span className="ml-4 text-gray-500">$15 base + usage</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="government">
                    <div className="flex items-center justify-between w-full">
                      <span>Government</span>
                      <span className="ml-4 text-gray-500">$199 base + usage</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="education">
                    <div className="flex items-center justify-between w-full">
                      <span>Education</span>
                      <span className="ml-4 text-gray-500">$39 base + usage</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="healthcare">
                    <div className="flex items-center justify-between w-full">
                      <span>Healthcare</span>
                      <span className="ml-4 text-gray-500">$199 base + usage</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="financial">
                    <div className="flex items-center justify-between w-full">
                      <span>Financial Services</span>
                      <span className="ml-4 text-gray-500">$399 base + usage</span>
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            {selectedTier && selectedTier !== subscription?.subscription_tier && (
              <div className="bg-blue-50 p-4 rounded-lg">
                <h4 className="font-medium text-blue-900 mb-2">
                  {selectedTier === 'starter' ? 'Downgrade' : 'Upgrade'} to {formatTierDisplay(selectedTier)}
                </h4>
                <p className="text-sm text-blue-700 mb-3">
                  Your subscription will be updated immediately. Billing will be prorated for the current period.
                </p>
                <div className="flex items-center space-x-3">
                  <Button 
                    onClick={handleTierUpgrade}
                    disabled={actionLoading}
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    {actionLoading ? 'Updating...' : `Confirm ${selectedTier === 'starter' ? 'Downgrade' : 'Upgrade'}`}
                  </Button>
                  <Button 
                    variant="outline" 
                    onClick={() => setShowUpgradeForm(false)}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Billing History */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Calendar className="h-5 w-5 mr-2" />
            Billing History
          </CardTitle>
        </CardHeader>
        <CardContent>
          {billingHistory.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2">Bill ID</th>
                    <th className="text-left py-2">Period</th>
                    <th className="text-left py-2">Amount</th>
                    <th className="text-left py-2">Generated</th>
                    <th className="text-left py-2">Due Date</th>
                    <th className="text-left py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {billingHistory.slice(0, 10).map((bill) => (
                    <tr key={bill.bill_id} className="border-b">
                      <td className="py-2 font-mono text-xs">{bill.bill_id.slice(0, 8)}...</td>
                      <td className="py-2">{bill.billing_period}</td>
                      <td className="py-2 font-semibold">${bill.total_amount.toFixed(2)}</td>
                      <td className="py-2">{new Date(bill.generated_at).toLocaleDateString()}</td>
                      <td className="py-2">{new Date(bill.due_date).toLocaleDateString()}</td>
                      <td className="py-2">
                        <Badge variant={bill.status === 'paid' ? 'green' : 'yellow'}>
                          {bill.status || 'pending'}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">No billing history available</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}