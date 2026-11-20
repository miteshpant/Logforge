'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ArrowLeft, CreditCard, CheckCircle, AlertTriangle, Calendar, DollarSign, User, Settings, ChevronDown, ChevronRight, Download, Eye } from 'lucide-react'
import { apiRequest, downloadBill } from '@/lib/api'
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
  // Older/alternate bill payloads use these names; the page tolerates both.
  id?: string
  invoice_id?: string
  amount?: number
  subscription_tier?: string
  base_fee?: number
  usage_charges?: number
  tier_discount?: number
  promo_discount?: number
  promo_code?: string
  usage_breakdown?: Record<string, any>
  subtotal?: number
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
  
  // Billing breakdown state
  const [expandedBills, setExpandedBills] = useState<Set<string>>(new Set())
  const [billBreakdowns, setBillBreakdowns] = useState<Record<string, any>>({})
  const [loadingBreakdown, setLoadingBreakdown] = useState<Set<string>>(new Set())
  const [downloadingPDF, setDownloadingPDF] = useState<Set<string>>(new Set())

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

  const fetchBillBreakdown = async (billId: string) => {
    if (billBreakdowns[billId]) {
      // Already fetched, just toggle
      toggleBillExpansion(billId)
      return
    }

    try {
      setLoadingBreakdown(prev => new Set([...prev, billId]))
      
      // Check if breakdown is already in the bill data
      const existingBill = billingHistory.find(bill => 
        (bill.bill_id || bill.id || bill.invoice_id) === billId
      )
      
      if (existingBill) {
        // Use the rich billing data that's already available
        const billBreakdown: any = {}
        
        // Add base fee if present
        if (existingBill.base_fee && existingBill.base_fee > 0) {
          billBreakdown.base_fee = {
            description: `${existingBill.subscription_tier?.toUpperCase() || 'SUBSCRIPTION'} Base Fee`,
            amount: existingBill.base_fee,
            unit_price: existingBill.base_fee,
            quantity: 1,
            unit: 'subscription'
          }
        }
        
        // Add usage charges if present
        if (existingBill.usage_charges && existingBill.usage_charges > 0) {
          billBreakdown.usage_charges = {
            description: 'Usage-based Charges',
            amount: existingBill.usage_charges,
            unit_price: existingBill.usage_charges,
            quantity: 1,
            unit: 'usage'
          }
        }
        
        // Add tier discount if present
        if (existingBill.tier_discount && existingBill.tier_discount > 0) {
          billBreakdown.tier_discount = {
            description: 'Tier Discount',
            amount: -existingBill.tier_discount,
            unit_price: -existingBill.tier_discount,
            quantity: 1,
            unit: 'discount'
          }
        }
        
        // Add promo discount if present
        if (existingBill.promo_discount && existingBill.promo_discount > 0) {
          billBreakdown.promo_discount = {
            description: existingBill.promo_code ? `Promo Code: ${existingBill.promo_code}` : 'Promotional Discount',
            amount: -existingBill.promo_discount,
            unit_price: -existingBill.promo_discount,
            quantity: 1,
            unit: 'discount'
          }
        }
        
        // Add usage breakdown details if present
        if (existingBill.usage_breakdown && Array.isArray(existingBill.usage_breakdown) && existingBill.usage_breakdown.length > 0) {
          existingBill.usage_breakdown.forEach((item: any, index: number) => {
            billBreakdown[`usage_detail_${index}`] = {
              description: item.description || item.feature || `Usage Detail ${index + 1}`,
              amount: item.amount || item.cost || 0,
              unit_price: item.unit_price || item.rate || 0,
              quantity: item.quantity || item.usage || 0,
              unit: item.unit || 'calls'
            }
          })
        }
        
        const breakdown = {
          bill_id: billId,
          total_amount: existingBill.total_amount,
          subtotal: existingBill.subtotal,
          currency: existingBill.currency || 'USD',
          subscription_tier: existingBill.subscription_tier,
          breakdown: billBreakdown
        }
        setBillBreakdowns(prev => ({ ...prev, [billId]: breakdown }))
        setExpandedBills(prev => new Set([...prev, billId]))
      } else {
        // Try to fetch fresh bill details from generate endpoint
        try {
          const billDetails = await apiRequest(`/v1/billing/generate/${tenantId}`, {
            method: 'POST',
            body: JSON.stringify({
              bill_id: billId,
              regenerate: false // Just get existing bill details
            })
          })
          
          const breakdown = {
            bill_id: billId,
            total_amount: billDetails.total_cost || 0,
            currency: billDetails.currency || 'USD',
            breakdown: billDetails.line_items || {}
          }
          setBillBreakdowns(prev => ({ ...prev, [billId]: breakdown }))
          setExpandedBills(prev => new Set([...prev, billId]))
        } catch (detailError) {
          console.error('Failed to fetch bill details:', detailError)
          // Show message that breakdown is not available
          setBillBreakdowns(prev => ({ ...prev, [billId]: null }))
          setExpandedBills(prev => new Set([...prev, billId]))
        }
      }
      
    } catch (error) {
      console.error('Failed to fetch bill breakdown:', error)
      setError('Failed to fetch bill breakdown: ' + (error instanceof Error ? error.message : 'API endpoint not available'))
    } finally {
      setLoadingBreakdown(prev => {
        const newSet = new Set(prev)
        newSet.delete(billId)
        return newSet
      })
    }
  }

  const toggleBillExpansion = (billId: string) => {
    setExpandedBills(prev => {
      const newSet = new Set(prev)
      if (newSet.has(billId)) {
        newSet.delete(billId)
      } else {
        newSet.add(billId)
      }
      return newSet
    })
  }

  const downloadBillPDF = async (billId: string) => {
    try {
      setDownloadingPDF(prev => new Set([...prev, billId]))
      
      await downloadBill(billId)
    } catch (error) {
      console.error('Failed to download PDF:', error)
      setError('Failed to download PDF: ' + (error instanceof Error ? error.message : 'API endpoint not available'))
    } finally {
      setDownloadingPDF(prev => {
        const newSet = new Set(prev)
        newSet.delete(billId)
        return newSet
      })
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
            <div className="space-y-4">
              {billingHistory.slice(0, 10).map((bill, index) => {
                // Handle different possible ID field names and ensure safe access
                const billId = bill.bill_id || bill.id || bill.invoice_id || `bill_${index}`
                const billIdDisplay = billId && typeof billId === 'string' ? billId.slice(0, 8) + '...' : billId || 'N/A'
                const isExpanded = expandedBills.has(billId)
                const isLoadingBreakdown = loadingBreakdown.has(billId)
                const isDownloadingPDF = downloadingPDF.has(billId)
                const breakdown = billBreakdowns[billId]
                
                return (
                  <div key={billId || index} className="border rounded-lg p-4 space-y-3">
                    {/* Bill Summary Row */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-4">
                        <div className="flex items-center space-x-2">
                          <span className="font-mono text-sm font-medium">{billIdDisplay}</span>
                          <Badge variant={bill.status === 'paid' ? 'green' : 'secondary'}>
                            {bill.status || 'pending'}
                          </Badge>
                        </div>
                        <div className="text-sm text-gray-600">
                          {bill.billing_period || 'N/A'}
                        </div>
                        <div className="text-lg font-semibold text-gray-900">
                          ${(Number(bill.total_amount || bill.amount || 0) || 0).toFixed(2)}
                        </div>
                      </div>
                      
                      <div className="flex items-center space-x-2">
                        <div className="text-sm text-gray-500">
                          Due: {bill.due_date ? new Date(bill.due_date).toLocaleDateString() : 'N/A'}
                        </div>
                        
                        {/* Action Buttons */}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => fetchBillBreakdown(billId)}
                          disabled={isLoadingBreakdown}
                          className="flex items-center"
                        >
                          {isLoadingBreakdown ? (
                            <>
                              <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-600 mr-1"></div>
                              Loading...
                            </>
                          ) : (
                            <>
                              {isExpanded ? <ChevronDown className="h-3 w-3 mr-1" /> : <ChevronRight className="h-3 w-3 mr-1" />}
                              <Eye className="h-3 w-3 mr-1" />
                              Details
                            </>
                          )}
                        </Button>
                        
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => downloadBillPDF(billId)}
                          disabled={isDownloadingPDF}
                          className="flex items-center"
                        >
                          {isDownloadingPDF ? (
                            <>
                              <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-600 mr-1"></div>
                              Downloading...
                            </>
                          ) : (
                            <>
                              <Download className="h-3 w-3 mr-1" />
                              PDF
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                    
                    {/* Bill Breakdown (Expandable) */}
                    {isExpanded && breakdown && (
                      <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                        <h4 className="font-medium text-gray-900 mb-3">Bill Breakdown</h4>
                        <div className="space-y-3">
                          {breakdown.breakdown && Object.entries(breakdown.breakdown).map(([key, item]: [string, any]) => (
                            <div key={key} className="flex items-center justify-between py-2 border-b border-gray-200 last:border-0">
                              <div className="flex-1">
                                <div className="font-medium text-sm text-gray-900">
                                  {item.description || key.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}
                                </div>
                                {item.quantity && item.unit && (
                                  <div className="text-xs text-gray-500">
                                    {item.quantity.toLocaleString()} {item.unit} × ${item.unit_price?.toFixed ? item.unit_price.toFixed(3) : '0.000'}
                                  </div>
                                )}
                              </div>
                              <div className="font-semibold text-sm text-gray-900">
                                ${item.amount?.toFixed ? item.amount.toFixed(2) : '0.00'}
                              </div>
                            </div>
                          ))}
                          
                          {/* Total */}
                          <div className="flex items-center justify-between pt-3 border-t-2 border-gray-300">
                            <div className="font-semibold text-base text-gray-900">
                              Total Amount
                            </div>
                            <div className="font-bold text-lg text-gray-900">
                              ${breakdown.total_amount?.toFixed ? breakdown.total_amount.toFixed(2) : '0.00'} {breakdown.currency || 'USD'}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {/* Show message if expanded but no breakdown available */}
                    {isExpanded && !breakdown && !isLoadingBreakdown && (
                      <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                        <p className="text-sm text-yellow-800">
                          Bill breakdown details are not available for this invoice.
                        </p>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">No billing history available</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}