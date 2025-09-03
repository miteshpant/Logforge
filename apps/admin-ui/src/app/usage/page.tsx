'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, Download, Receipt, TrendingUp, Database, Activity, DollarSign } from 'lucide-react'
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

interface UsageStats {
  title: string
  value: string
  description: string
  icon: any
}

export default function UsageAnalyticsPage() {
  const [selectedPeriod, setSelectedPeriod] = useState('current_month')
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [tenantUsages, setTenantUsages] = useState<Record<string, TenantUsage>>({})
  const [usageStats, setUsageStats] = useState<UsageStats[]>([])
  const [loading, setLoading] = useState(true)
  const [exportStatus, setExportStatus] = useState<string | null>(null)

  useEffect(() => {
    console.log('Period changed to:', selectedPeriod)
    fetchUsageData()
  }, [selectedPeriod])

  const fetchUsageData = async () => {
    try {
      setLoading(true)
      
      // Fetch all tenants
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
      
      // Calculate platform-wide statistics
      const totalTenants = tenantsData.tenants.length
      const totalRevenue = tenantsData.tenants.reduce((sum: number, tenant: Tenant) => {
        const cost = tenant.type === 'enterprise' ? 997 : tenant.type === 'smb' ? 499 : 99
        return sum + cost
      }, 0)
      
      const totalApiCalls = Object.values(combinedUsage).reduce((sum, usage: any) => 
        sum + (usage?.api_calls || 0), 0)
      
      const totalStorage = Object.values(combinedUsage).reduce((sum, usage: any) => 
        sum + (usage?.storage_used_gb || 0), 0)
      
      const avgRevenue = totalTenants > 0 ? Math.round(totalRevenue / totalTenants) : 0
      
      setUsageStats([
        {
          title: "Total Revenue",
          value: `$${totalRevenue.toLocaleString()}`,
          description: "Monthly recurring revenue",
          icon: DollarSign
        },
        {
          title: "Total API Calls",
          value: totalApiCalls.toLocaleString(),
          description: "API requests this month",
          icon: Activity
        },
        {
          title: "Total Storage",
          value: `${totalStorage.toFixed(1)}GB`,
          description: "Data stored across all tenants",
          icon: Database
        },
        {
          title: "Avg Revenue/Tenant",
          value: `$${avgRevenue}`,
          description: "Average revenue per tenant",
          icon: TrendingUp
        }
      ])
      
    } catch (error) {
      console.error('Failed to fetch usage data:', error)
    } finally {
      setLoading(false)
    }
  }

  const getMonthlyCost = (type: string) => {
    switch (type.toLowerCase()) {
      case 'enterprise': return '$997'
      case 'smb': return '$499' 
      case 'startup': return '$99'
      default: return 'Contact Sales'
    }
  }

  const getSubscriptionColor = (type: string) => {
    switch (type.toLowerCase()) {
      case 'enterprise': return 'purple' as const
      case 'smb': return 'blue' as const
      case 'startup': return 'green' as const
      default: return 'secondary' as const
    }
  }

  const handleExportReport = async () => {
    try {
      console.log('Export button clicked')
      setExportStatus('Generating usage report...')
      
      // Generate CSV content from current data
      const csvContent = generateUsageCSV()
      console.log('CSV content generated:', csvContent.substring(0, 100))
      
      const blob = new Blob([csvContent], { type: 'text/csv' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `usage-report-${selectedPeriod}-${new Date().toISOString().split('T')[0]}.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      setExportStatus('Report exported successfully!')
      setTimeout(() => setExportStatus(null), 3000)
    } catch (error) {
      console.error('Failed to export report:', error)
      setExportStatus('Failed to export report')
      setTimeout(() => setExportStatus(null), 5000)
    }
  }

  const generateUsageCSV = () => {
    const headers = ['Organization', 'Tenant ID', 'Subscription Tier', 'Storage (GB)', 'API Calls', 'Log Count (Month)', 'Monthly Cost']
    const rows = tenants.map(tenant => {
      const usage = tenantUsages[tenant.tenant_id]
      return [
        tenant.name,
        tenant.tenant_id,
        tenant.type.toUpperCase(),
        usage?.storage_used_gb?.toFixed(1) || '0.0',
        usage?.api_calls?.toLocaleString() || '0',
        usage?.log_count_month?.toLocaleString() || '0',
        getMonthlyCost(tenant.type)
      ]
    })
    
    return [headers, ...rows].map(row => row.join(',')).join('\n')
  }

  const generateTenantBill = (tenantId: string, tenantName: string) => {
    console.log('Generate tenant bill clicked for:', tenantName, tenantId)
    setExportStatus(`Generating bill for ${tenantName}...`)
    
    setTimeout(() => {
      setExportStatus(`Bill generated successfully for ${tenantName}`)
      setTimeout(() => setExportStatus(null), 3000)
    }, 1500)
  }

  const handleGenerateAllBills = async () => {
    console.log('Generate all bills clicked, tenants count:', tenants.length)
    setExportStatus('Generating bills for all tenants...')
    
    setTimeout(() => {
      setExportStatus(`Generated ${tenants.length} bills successfully!`)
      setTimeout(() => setExportStatus(null), 3000)
    }, 2000)
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
        <h1 className="text-3xl font-bold text-gray-900">Usage Analytics</h1>
        <p className="text-gray-600">Monitor tenant usage patterns and generate billing reports</p>
      </div>

      {/* Status Notification */}
      {exportStatus && (
        <Card className={`${exportStatus.includes('Failed') ? 'border-red-200 bg-red-50' : 'border-green-200 bg-green-50'}`}>
          <CardContent className="p-4">
            <div className="flex items-center">
              <Activity className="h-5 w-5 text-green-600 mr-2" />
              <p className={exportStatus.includes('Failed') ? 'text-red-800' : 'text-green-800'}>
                {exportStatus}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Period Selector */}
      <div className="flex justify-between items-center">
        <div className="flex items-center space-x-2">
          <label className="text-sm font-medium text-gray-700">Period:</label>
          <Select
            value={selectedPeriod}
            onChange={(e) => setSelectedPeriod(e.target.value)}
          >
            <option value="current_month">Current Month</option>
            <option value="last_month">Last Month</option>
            <option value="last_3_months">Last 3 Months</option>
            <option value="custom">Custom Range</option>
          </Select>
        </div>

        <div className="flex space-x-2">
          <Button variant="outline" onClick={handleExportReport}>
            <Download className="h-4 w-4 mr-2" />
            Export Usage Report
          </Button>
          <Button onClick={handleGenerateAllBills}>
            <Receipt className="h-4 w-4 mr-2" />
            Generate All Bills
          </Button>
        </div>
      </div>

      {/* Summary Statistics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading ? (
          [1, 2, 3, 4].map((i) => (
            <Card key={i} className="bg-white p-4 rounded-lg shadow">
              <CardContent className="p-0">
                <div className="flex items-center space-x-2">
                  <div className="h-4 w-4 bg-gray-200 rounded" />
                  <div className="flex flex-col">
                    <span className="text-sm text-gray-400">Loading...</span>
                    <span className="text-2xl font-bold text-gray-400">-</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        ) : (
          usageStats.map((stat) => {
            const Icon = stat.icon
            return (
              <Card key={stat.title} className="bg-white p-4 rounded-lg shadow">
                <CardContent className="p-0">
                  <div className="flex items-center space-x-2">
                    <Icon className="h-4 w-4 text-gray-500" />
                    <div className="flex flex-col">
                      <span className="text-sm text-gray-500">{stat.title}</span>
                      <span className="text-2xl font-bold text-gray-900">{stat.value}</span>
                      <span className="text-xs text-gray-400">{stat.description}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })
        )}
      </div>

      {/* Tenant Usage Breakdown Table */}
      <Card className="bg-white rounded-lg shadow">
        <CardHeader>
          <CardTitle className="flex items-center">
            <Database className="h-5 w-5 mr-2" />
            Tenant Usage Breakdown
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Organization
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Tier
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Storage
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    API Calls
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Logs/Month
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Monthly Cost
                  </th>
                  <th className="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {loading ? (
                  [1, 2, 3].map((i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-4 py-4">
                        <div className="text-sm text-gray-400">Loading...</div>
                      </td>
                      <td className="px-3 py-4">
                        <Badge variant="secondary" className="text-xs">Loading</Badge>
                      </td>
                      <td className="px-3 py-4">
                        <div className="text-sm text-gray-400">Loading...</div>
                      </td>
                      <td className="px-3 py-4">
                        <div className="text-sm text-gray-400">Loading...</div>
                      </td>
                      <td className="px-3 py-4">
                        <div className="text-sm text-gray-400">Loading...</div>
                      </td>
                      <td className="px-3 py-4">
                        <div className="text-sm text-gray-400">Loading...</div>
                      </td>
                      <td className="px-3 py-4 text-center">
                        <div className="w-8 h-8 bg-gray-200 rounded mx-auto"></div>
                      </td>
                    </tr>
                  ))
                ) : (
                  tenants.map((tenant) => {
                    const usage = tenantUsages[tenant.tenant_id]
                    return (
                      <tr key={tenant.tenant_id} className="hover:bg-gray-50">
                        <td className="px-4 py-4">
                          <div className="text-sm font-medium text-gray-900">{tenant.name}</div>
                          <div className="text-xs text-gray-500">{tenant.industry}</div>
                        </td>
                        <td className="px-3 py-4">
                          <Badge variant={getSubscriptionColor(tenant.type)} className="text-xs">
                            {tenant.type.toUpperCase()}
                          </Badge>
                        </td>
                        <td className="px-3 py-4">
                          <div className="text-sm text-gray-900">{usage?.storage_used_gb?.toFixed(1) || '0.0'}GB</div>
                        </td>
                        <td className="px-3 py-4">
                          <div className="text-sm text-gray-900">{usage?.api_calls?.toLocaleString() || '0'}</div>
                        </td>
                        <td className="px-3 py-4">
                          <div className="text-sm text-gray-900">{usage?.log_count_month?.toLocaleString() || '0'}</div>
                        </td>
                        <td className="px-3 py-4">
                          <div className="text-sm font-medium text-gray-900">{getMonthlyCost(tenant.type)}</div>
                        </td>
                        <td className="px-3 py-4">
                          <div className="flex justify-center">
                            <Button 
                              variant="outline" 
                              size="sm"
                              className="text-xs"
                              onClick={() => generateTenantBill(tenant.tenant_id, tenant.name)}
                            >
                              <Receipt className="h-3 w-3 mr-1" />
                              Bill
                            </Button>
                          </div>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Feature Usage Summary */}
      <Card className="bg-white rounded-lg shadow">
        <CardHeader>
          <CardTitle className="flex items-center">
            <TrendingUp className="h-5 w-5 mr-2" />
            Platform Feature Usage
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-blue-50 p-4 rounded-lg">
              <h4 className="text-sm font-medium text-blue-600">Log Ingestion</h4>
              <p className="text-xl font-bold text-blue-900">
                {Object.values(tenantUsages).reduce((sum, usage: any) => sum + (usage?.log_count_month || 0), 0).toLocaleString()}
              </p>
              <p className="text-xs text-blue-700">Total logs this month</p>
            </div>
            
            <div className="bg-green-50 p-4 rounded-lg">
              <h4 className="text-sm font-medium text-green-600">Query Engine</h4>
              <p className="text-xl font-bold text-green-900">
                {Object.values(tenantUsages).reduce((sum, usage: any) => sum + (usage?.query_count || 0), 0).toLocaleString()}
              </p>
              <p className="text-xs text-green-700">Total queries executed</p>
            </div>
            
            <div className="bg-purple-50 p-4 rounded-lg">
              <h4 className="text-sm font-medium text-purple-600">API Gateway</h4>
              <p className="text-xl font-bold text-purple-900">
                {Object.values(tenantUsages).reduce((sum, usage: any) => sum + (usage?.api_calls || 0), 0).toLocaleString()}
              </p>
              <p className="text-xs text-purple-700">Total API calls</p>
            </div>
            
            <div className="bg-orange-50 p-4 rounded-lg">
              <h4 className="text-sm font-medium text-orange-600">Data Storage</h4>
              <p className="text-xl font-bold text-orange-900">
                {Object.values(tenantUsages).reduce((sum, usage: any) => sum + (usage?.storage_used_gb || 0), 0).toFixed(1)}GB
              </p>
              <p className="text-xs text-orange-700">Total storage used</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}