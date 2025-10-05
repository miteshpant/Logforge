'use client'

import React, { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { DashboardApi } from '@/lib/api'
import { Dashboard, DashboardData } from '@/lib/api/dashboard'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { 
  Activity, 
  BarChart3, 
  Shield, 
  Users, 
  FileText, 
  TrendingUp,
  RefreshCw,
  Plus,
  Eye,
  Settings,
  Share,
  Calendar,
  Clock
} from 'lucide-react'
import Link from 'next/link'

interface DashboardCardProps {
  dashboard: Dashboard
  onView: (dashboard: Dashboard) => void
  onRefresh: (dashboardId: string) => void
  isRefreshing?: boolean
}

const DashboardCard: React.FC<DashboardCardProps> = ({ 
  dashboard, 
  onView, 
  onRefresh, 
  isRefreshing = false 
}) => {
  const getIcon = (type: string) => {
    switch (type) {
      case 'security': return <Shield className="w-5 h-5" />
      case 'performance': return <Activity className="w-5 h-5" />
      case 'infrastructure': return <BarChart3 className="w-5 h-5" />
      case 'business': return <TrendingUp className="w-5 h-5" />
      case 'compliance': return <FileText className="w-5 h-5" />
      case 'executive': return <Users className="w-5 h-5" />
      default: return <BarChart3 className="w-5 h-5" />
    }
  }

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'security': return 'bg-red-100 text-red-800'
      case 'performance': return 'bg-blue-100 text-blue-800'
      case 'infrastructure': return 'bg-green-100 text-green-800'
      case 'business': return 'bg-purple-100 text-purple-800'
      case 'compliance': return 'bg-yellow-100 text-yellow-800'
      case 'executive': return 'bg-gray-100 text-gray-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <Card className="hover:shadow-lg transition-shadow cursor-pointer">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-2">
            {getIcon(dashboard.type)}
            <div>
              <CardTitle className="text-lg">{dashboard.name}</CardTitle>
              <CardDescription className="text-sm">{dashboard.description}</CardDescription>
            </div>
          </div>
          <Badge className={getTypeColor(dashboard.type)}>
            {dashboard.type}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm text-gray-600">
            <span className="flex items-center">
              <Clock className="w-4 h-4 mr-1" />
              Updated {new Date(dashboard.updated_at).toLocaleTimeString()}
            </span>
            <span>{dashboard.widgets?.length || 0} widgets</span>
          </div>
          
          <div className="flex flex-wrap gap-1">
            {dashboard.tags?.slice(0, 3).map((tag) => (
              <Badge key={tag} variant="outline" className="text-xs">
                {tag}
              </Badge>
            ))}
            {dashboard.tags?.length > 3 && (
              <Badge variant="outline" className="text-xs">
                +{dashboard.tags.length - 3}
              </Badge>
            )}
          </div>

          <div className="flex space-x-2">
            <Button 
              size="sm" 
              onClick={() => onView(dashboard)}
              className="flex-1"
            >
              <Eye className="w-4 h-4 mr-1" />
              View
            </Button>
            <Button 
              size="sm" 
              variant="outline"
              onClick={() => onRefresh(dashboard.id)}
              disabled={isRefreshing}
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            </Button>
            <Button size="sm" variant="outline">
              <Share className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function DashboardsPage() {
  const { user, tenant } = useAuth()
  const [dashboards, setDashboards] = useState<Dashboard[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshingDashboards, setRefreshingDashboards] = useState<Set<string>>(new Set())
  const [activeTab, setActiveTab] = useState('all')

  useEffect(() => {
    loadDashboards()
  }, [])

  const loadDashboards = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await DashboardApi.listDashboards({
        limit: 50
      })
      
      if (response && response.data) {
        setDashboards(response.data || [])
      } else {
        throw new Error('Failed to load dashboards')
      }
    } catch (err: any) {
      console.error('Failed to load dashboards:', err)
      setError(err.message || 'Failed to load dashboards')
    } finally {
      setLoading(false)
    }
  }

  const refreshDashboard = async (dashboardId: string) => {
    try {
      setRefreshingDashboards(prev => new Set(prev).add(dashboardId))
      
      // Call the dashboard data refresh endpoint
      const endTime = new Date().toISOString()
      const startTime = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
      
      await DashboardApi.getDashboardData(dashboardId, {
        time_range: '24h',
        refresh: true
      })
      
      // Reload dashboards list to get updated timestamps
      await loadDashboards()
    } catch (err: any) {
      console.error('Failed to refresh dashboard:', err)
      setError(err.message || 'Failed to refresh dashboard')
    } finally {
      setRefreshingDashboards(prev => {
        const newSet = new Set(prev)
        newSet.delete(dashboardId)
        return newSet
      })
    }
  }

  const viewDashboard = (dashboard: Dashboard) => {
    // Navigate to individual dashboard view
    window.location.href = `/dashboards/${dashboard.id}`
  }

  const filterDashboards = (dashboards: Dashboard[], filter: string) => {
    if (filter === 'all') return dashboards
    return dashboards.filter(d => d.type === filter)
  }

  const getDashboardStats = () => {
    const total = dashboards.length
    const byType = dashboards.reduce((acc, d) => {
      acc[d.type] = (acc[d.type] || 0) + 1
      return acc
    }, {} as Record<string, number>)
    
    return { total, byType }
  }

  const stats = getDashboardStats()

  if (loading) {
    return (
      <DashboardLayout>
        <div className="p-6">
          <div className="flex items-center justify-center h-64">
            <div className="flex items-center space-x-2">
              <RefreshCw className="w-6 h-6 animate-spin" />
              <span>Loading dashboards...</span>
            </div>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Dashboards</h1>
            <p className="text-gray-600 mt-1">
              Monitor your systems with real-time dashboards and analytics
            </p>
          </div>
          <div className="flex space-x-2">
            <Button variant="outline" onClick={loadDashboards}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
            <Button>
              <Plus className="w-4 h-4 mr-2" />
              Create Dashboard
            </Button>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <BarChart3 className="w-8 h-8 text-blue-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">Total Dashboards</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <Shield className="w-8 h-8 text-red-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">Security</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.byType.security || 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <Activity className="w-8 h-8 text-green-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">Performance</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.byType.performance || 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <TrendingUp className="w-8 h-8 text-purple-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">Business</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.byType.business || 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Dashboard Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="all">All Dashboards ({stats.total})</TabsTrigger>
            <TabsTrigger value="security">Security ({stats.byType.security || 0})</TabsTrigger>
            <TabsTrigger value="performance">Performance ({stats.byType.performance || 0})</TabsTrigger>
            <TabsTrigger value="infrastructure">Infrastructure ({stats.byType.infrastructure || 0})</TabsTrigger>
            <TabsTrigger value="business">Business ({stats.byType.business || 0})</TabsTrigger>
          </TabsList>

          <TabsContent value={activeTab} className="mt-6">
            {filterDashboards(dashboards, activeTab).length === 0 ? (
              <Card>
                <CardContent className="p-8 text-center">
                  <BarChart3 className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    No dashboards found
                  </h3>
                  <p className="text-gray-600 mb-4">
                    {activeTab === 'all' 
                      ? 'Get started by creating your first dashboard'
                      : `No ${activeTab} dashboards available`
                    }
                  </p>
                  <Button>
                    <Plus className="w-4 h-4 mr-2" />
                    Create Dashboard
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filterDashboards(dashboards, activeTab).map((dashboard) => (
                  <DashboardCard
                    key={dashboard.id}
                    dashboard={dashboard}
                    onView={viewDashboard}
                    onRefresh={refreshDashboard}
                    isRefreshing={refreshingDashboards.has(dashboard.id)}
                  />
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  )
}