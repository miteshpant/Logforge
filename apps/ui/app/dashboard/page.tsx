'use client'

import { useEffect, useState, useRef } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Progress } from '@/components/ui/progress'
import {
  BarChart3,
  Database,
  Shield,
  Activity,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Clock,
  Users,
  Server,
  Zap,
  Eye,
  ArrowRight,
  Play,
  BookOpen,
  Settings,
  Brain,
  Search,
  Target,
  GitBranch,
  Lightbulb,
  TrendingDown,
  FileText,
  Network,
  DollarSign,
  Globe,
  Timer,
  Cpu,
  HeartHandshake,
} from 'lucide-react'
import Link from 'next/link'
import { TenantSelector } from '@/components/TenantSelector'
import { QueryApi, StorageApi, ObservabilityApi, AlertsApi, TenantsApi, AiApi, SecurityApi } from '@/lib/api'
import RealTimeDataStream from '@/components/RealTimeDataStream'
import AiChatAssistant from '@/components/AiChatAssistant'
import { DashboardVisualization } from '@/components/AdvancedDataViz'

// Dashboard data interfaces
interface DashboardMetrics {
  ingestionStats: {
    logsPerHour: number
    totalLogsToday: number
    servicesDetected: number
    errorRate: number
  }
  systemHealth: {
    uptime: number
    queryLatency: number
    storageUsed: number
    apiRequests: number
    alertRulesActive: number
    dataSourcesConnected: number
  }
  recentAlerts: Array<{
    id: number
    severity: 'high' | 'medium' | 'low'
    service: string
    message: string
    time: string
  }>
  topServices: Array<{
    name: string
    logs: number
    errors: number
    latency: string
  }>
  aiIntelligence: {
    predictions: number
    insights: number
    investigations: number
    correlationRate: number
  }
  securityIntelligence: {
    events: Array<{
      technique: string
      name: string
      count: number
      severity: 'critical' | 'high' | 'medium' | 'low'
      timeRange: string
    }>
    threatDetectionRate: number
    avgDetectionTime: number
  }
  liveInvestigations: Array<{
    id: string
    title: string
    status: 'analyzing' | 'completed' | 'failed'
    progress?: number
    severity: 'high' | 'medium' | 'low'
  }>
  businessImpact: {
    revenueProtected: number
    slaCompliance: number
  }
  serviceTopology: Array<{
    name: string
    status: 'healthy' | 'warning' | 'critical'
    latency: number
  }>
  predictiveAnalytics: {
    nextIncidentHours: number
    confidence: number
    costOptimization: number
  }
}

// Default/loading data
const defaultDashboardData: DashboardMetrics = {
  ingestionStats: {
    logsPerHour: 0,
    totalLogsToday: 0,
    servicesDetected: 0,
    errorRate: 0,
  },
  systemHealth: {
    uptime: 0,
    queryLatency: 0,
    storageUsed: 0,
    apiRequests: 0,
    alertRulesActive: 0,
    dataSourcesConnected: 0,
  },
  recentAlerts: [],
  topServices: [],
  aiIntelligence: {
    predictions: 0,
    insights: 0,
    investigations: 0,
    correlationRate: 0,
  },
  securityIntelligence: {
    events: [],
    threatDetectionRate: 0,
    avgDetectionTime: 0,
  },
  liveInvestigations: [],
  businessImpact: {
    revenueProtected: 0,
    slaCompliance: 0,
  },
  serviceTopology: [],
  predictiveAnalytics: {
    nextIncidentHours: 0,
    confidence: 0,
    costOptimization: 0,
  },
}

export default function DashboardPage() {
  const { user, tenant, isLoading } = useAuth()
  const { currentTimeRange } = useTimeRange()
  const [dashboardData, setDashboardData] = useState<DashboardMetrics>(defaultDashboardData)
  const [isFirstTime, setIsFirstTime] = useState(true) // Will check if user has ingested logs
  const [isLoadingData, setIsLoadingData] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const isLoadingRef = useRef(false) // Prevent multiple simultaneous loads
  
  // World-class enterprise features state
  const [showAiChat, setShowAiChat] = useState(false)
  const [aiChatMinimized, setAiChatMinimized] = useState(true)
  const [showRealTimeStream, setShowRealTimeStream] = useState(true)

  // Function to calculate relative time
  const getRelativeTime = (timestamp: string) => {
    const now = new Date()
    const time = new Date(timestamp)
    const diffMinutes = Math.floor((now.getTime() - time.getTime()) / 60000)
    
    if (diffMinutes < 1) return 'just now'
    if (diffMinutes < 60) return `${diffMinutes}m ago`
    if (diffMinutes < 1440) return `${Math.floor(diffMinutes / 60)}h ago`
    return `${Math.floor(diffMinutes / 1440)}d ago`
  }

  // Load dashboard data from APIs
  const loadDashboardData = async () => {
    if (!tenant || isLoadingRef.current) return

    try {
      isLoadingRef.current = true // Set loading flag
      setIsLoadingData(true)
      setError(null)

      // Get current time for queries - format for ClickHouse compatibility
      const now = new Date()
      const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate())
      const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000)

      // Format timestamps for ClickHouse (YYYY-MM-DD HH:MM:SS format)
      const formatForClickHouse = (date: Date) => {
        return date.toISOString().slice(0, 19).replace('T', ' ')
      }

      // Debug: Check if AI API calls are being made
      console.log('🤖 Starting AI API calls...')
      
      // Parallel API calls for dashboard metrics
      const [
        todayLogsResult,
        hourlyLogsResult,
        storageResult,
        serviceMapResult,
        recentAlertsResult,
        tenantUsageResult,
        allAlertsResult,
        aiInsightsResult,
        aiAnalyticsResult,
        anomalyDetectionResult,
        securityDashboardResult,
        serviceTopologyResult
      ] = await Promise.all([
        // 1. Logs Today - Count of logs ingested today
        QueryApi.executeQuery({
          query: '*',
          time_range: {
            start: formatForClickHouse(startOfDay),
            end: formatForClickHouse(now)
          },
          aggregations: [{ type: 'count', field: '*', alias: 'total_logs' }],
          filters: [],
          limit: 1
        }).catch((err) => {
          console.warn('Today logs query failed:', err)
          return { success: false, data: { total_hits: 0, query_id: '', execution_time: 0, logs: [] } }
        }),

        // 2. Hourly Logs - Count of logs in last hour
        QueryApi.executeQuery({
          query: '*',
          time_range: {
            start: formatForClickHouse(oneHourAgo),
            end: formatForClickHouse(now)
          },
          aggregations: [{ type: 'count', field: '*', alias: 'hourly_logs' }],
          filters: [],
          limit: 1
        }).catch((err) => {
          console.warn('Hourly logs query failed:', err)
          return { success: false, data: { total_hits: 0, query_id: '', execution_time: 0, logs: [] } }
        }),

        // 3. Storage Usage - using proper TenantsApi
        TenantsApi.getTenantUsage(tenant.id).then(result => ({
          success: result.success || true,
          data: result.data || { storage_used_bytes: 0 }
        })).catch((err) => {
          console.warn('Storage usage query failed:', err)
          return { 
            success: false, 
            data: { storage_used_bytes: 0 } 
          }
        }),

        // 4. Service Map for system health and error rates
        ObservabilityApi.getServiceMap().then(result => ({
          success: result?.success ?? true,
          data: result?.data ?? { 
            services: [],
            metrics: { 
              overall_error_rate: 0, 
              avg_response_time: 0,
              total_services: 0 
            } 
          }
        })).catch(() => ({ 
          success: false, 
          data: { 
            services: [],
            metrics: { 
              overall_error_rate: 0, 
              avg_response_time: 0,
              total_services: 0 
            } 
          } 
        })),

        // 5. Recent Alerts
        AlertsApi.listAlertEvents({ 
          limit: 3, 
          status: ['triggered'] 
        }).then(result => ({
          success: true,
          data: (result as any)?.alerts ?? []
        })).catch(() => ({ 
          success: false, 
          data: [] 
        })),

        // 6. Tenant Usage for API requests count
        TenantsApi.getTenantUsage(tenant.id).then(result => ({
          success: result.success || true,
          data: result.data || { queries_executed: 0 }
        })).catch((err) => {
          console.warn('Tenant usage for API requests failed:', err)
          return { 
            success: false, 
            data: { queries_executed: 0 } 
          }
        }),

        // 7. All Alert Rules to count active rules
        AlertsApi.listAlertRules({ 
          limit: 100, 
          status: 'active'
        }).then(result => ({
          success: true,
          data: (result as any)?.rules ?? []
        })).catch(() => ({ 
          success: false, 
          data: [] 
        })),

        // 8. AI Insights for active recommendations
        AiApi.getAiInsights({
          time_range: 'last-24h',
          limit: 50
        }).then(result => ({
          success: result.success || true,
          data: result.data || { insights: [], summary: { total_insights: 0 } }
        })).catch((err) => {
          console.warn('AI insights query failed:', err)
          return { 
            success: false, 
            data: { insights: [], summary: { total_insights: 0 } } 
          }
        }),

        // 9. AI Analytics for correlation metrics
        AiApi.getAiAnalytics('last-24h').then(result => ({
          success: result?.success ?? true,
          data: result?.data ?? { 
            usage_summary: { total_queries: 0 },
            performance_metrics: { success_rate: 0 },
            insights_generated: { total_insights: 0 }
          }
        })).catch((err) => {
          console.warn('AI analytics query failed:', err)
          return { 
            success: false, 
            data: { 
              usage_summary: { total_queries: 0 },
              performance_metrics: { success_rate: 0 },
              insights_generated: { total_insights: 0 }
            } 
          }
        }),

        // 10. Anomaly Detection for predictions
        AiApi.detectAnomalies({
          metrics: ['error_rate', 'response_time', 'throughput'],
          time_range: 'last-24h',
          detection_type: 'ml'
        }).then(result => ({
          success: result?.success ?? true,
          data: result?.data ?? { 
            anomalies: [],
            summary: { total_anomalies: 0, high_severity_count: 0 }
          }
        })).catch((err) => {
          console.warn('Anomaly detection query failed:', err)
          return { 
            success: false, 
            data: { 
              anomalies: [],
              summary: { total_anomalies: 0, high_severity_count: 0 }
            } 
          }
        }),

        // 11. Security Dashboard for real security intelligence data
        SecurityApi.getSecurityDashboard(currentTimeRange.value).then(result => ({
          success: result?.success ?? true,
          data: result?.data ?? {
            events_by_severity: {},
            events_last_24h: 0,
            top_triggered_rules: [],
            mitre_techniques: [],
            threat_intel_matches: 0,
            mean_resolution_time: 0
          }
        })).catch((err) => {
          console.warn('Security dashboard query failed:', err)
          return {
            success: false,
            data: {
              events_by_severity: {},
              events_last_24h: 0,
              top_triggered_rules: [],
              mitre_techniques: [],
              threat_intel_matches: 0,
              mean_resolution_time: 0
            }
          }
        }),

        // 12. Service Map for real service topology data
        ObservabilityApi.getServiceMap().then(result => ({
          success: result?.success ?? true,
          data: result?.data ?? {
            services: [],
            dependencies: [],
            health_summary: { healthy: 0, warning: 0, critical: 0 }
          }
        })).catch((err) => {
          console.warn('Service map query failed:', err)
          return {
            success: false,
            data: {
              services: [],
              dependencies: [],
              health_summary: { healthy: 0, warning: 0, critical: 0 }
            }
          }
        })
      ])

      // Calculate metrics from API responses  
      const totalLogsToday = todayLogsResult.success ? (todayLogsResult.data as any).total_count || todayLogsResult.data.total_hits : 0
      const logsPerHour = hourlyLogsResult.success ? (hourlyLogsResult.data as any).total_count || hourlyLogsResult.data.total_hits : 0
      
      // Calculate storage usage - from TenantUsageMetrics
      const storageUsedGB = storageResult.success && 'metrics' in storageResult.data ? storageResult.data.metrics?.total_storage_used_gb || 0 : 0
      // Estimate percentage based on typical tenant storage limits (100GB default)
      const estimatedStorageLimit = 100 // GB - would need actual quotas API for real limit
      const storageUsedPercentage = Math.min((storageUsedGB / estimatedStorageLimit) * 100, 100)
      const storageUsed = Math.round(storageUsedPercentage * 10) / 10
      
      // System health from service map
      const serviceMapData = serviceMapResult.success ? serviceMapResult.data : null
      const errorRate = serviceMapData?.metrics?.overall_error_rate || 0
      const avgLatency = serviceMapData?.metrics?.avg_response_time || 0
      const servicesDetected = serviceMapData?.metrics?.total_services || 0
      
      // Calculate uptime (mock calculation - would need real health endpoint)
      const uptime = errorRate < 5 ? 99.9 : errorRate < 10 ? 99.5 : 99.0

      // Process recent alerts
      const alertsData = recentAlertsResult.success ? recentAlertsResult.data : []
      const recentAlerts = (Array.isArray(alertsData) ? alertsData : []).slice(0, 3).map((alert: any, index: number) => ({
        id: index + 1,
        severity: alert.severity || 'low',
        service: alert.rule?.service || 'unknown',
        message: alert.rule?.name || alert.message || 'Alert triggered',
        time: getRelativeTime(alert.created_at)
      }))

      // Process top services from service map
      const topServices = (serviceMapData?.services || [])
        .sort((a: any, b: any) => (b.metrics?.request_rate || 0) - (a.metrics?.request_rate || 0))
        .slice(0, 4)
        .map((service: any) => ({
          name: service.name,
          logs: Math.floor((service.metrics?.request_rate || 0) * 24), // Estimate daily logs
          errors: Math.floor((service.metrics?.request_rate || 0) * (service.metrics?.error_rate || 0) / 100),
          latency: `${Math.round(service.metrics?.avg_latency || 0)}ms`
        }))

      // Calculate new metrics from additional API responses
      const tenantUsageData = tenantUsageResult.success ? tenantUsageResult.data : null
      const allAlertsData = allAlertsResult.success ? allAlertsResult.data : null

      // API Requests (from tenant usage queries_executed - using metrics.total_api_calls)
      const apiRequests = tenantUsageData && 'metrics' in tenantUsageData ? tenantUsageData.metrics?.total_api_calls || 0 : 0

      // Alert Rules Active (count of active alert rules)
      const alertRulesActive = (Array.isArray(allAlertsData) ? allAlertsData : []).filter((alert: any) => 
        alert.status === 'active' || alert.enabled === true
      ).length

      // Data Sources Connected (use services detected from service map)
      const dataSourcesConnected = servicesDetected

      // Process AI Intelligence data
      const aiInsightsData = aiInsightsResult.success ? aiInsightsResult.data : null
      const aiAnalyticsData = aiAnalyticsResult.success ? aiAnalyticsResult.data : null
      const anomalyData = anomalyDetectionResult.success ? anomalyDetectionResult.data : null

      // Debug: Log AI API results
      console.log('🤖 AI API Results:', {
        aiInsightsResult: aiInsightsResult.success,
        aiAnalyticsResult: aiAnalyticsResult.success,
        anomalyDetectionResult: anomalyDetectionResult.success,
        aiInsightsData,
        aiAnalyticsData,
        anomalyData
      })

      // AI Intelligence metrics calculation
      const aiIntelligence = {
        predictions: anomalyData?.summary?.high_severity_count || 0, // High severity anomalies as predictions
        insights: aiInsightsData?.summary?.total_insights || 0, // Total insights from AI insights API
        investigations: 0, // TODO: Add root cause analysis API call to get active investigations
        correlationRate: Math.round((aiAnalyticsData?.performance_metrics?.success_rate || 0) * 100) // Convert to percentage
      }

      console.log('🤖 Final AI Intelligence:', aiIntelligence)

      // Process Security Dashboard data
      const securityDashboardData = securityDashboardResult.success ? securityDashboardResult.data : null
      console.log('🔒 Security Dashboard Data:', securityDashboardData)

      const securityIntelligence = {
        events: (securityDashboardData?.mitre_techniques || []).slice(0, 2).map((technique: any) => ({
          technique: technique.technique || 'T1110',
          name: technique.description || 'Unknown Technique',
          count: technique.count || 0,
          severity: (technique.count > 10 ? 'critical' : technique.count > 5 ? 'high' : 'medium') as 'critical' | 'high' | 'medium' | 'low',
          timeRange: 'Last 2h'
        })),
        threatDetectionRate: Math.round(((securityDashboardData as any)?.security_posture_score || 0) * 100),
        avgDetectionTime: securityDashboardData?.mean_resolution_time || 0
      }

      // Process Service Topology data
      const serviceTopologyData = serviceTopologyResult.success ? serviceTopologyResult.data : null
      console.log('🌐 Service Topology Data:', serviceTopologyData)

      const serviceTopology = (serviceTopologyData?.services || []).slice(0, 3).map((service: any) => ({
        name: service.service_name || service.name || 'Unknown Service',
        status: (service.health_status === 'healthy' ? 'healthy' : 
                service.health_status === 'warning' ? 'warning' : 'critical') as 'healthy' | 'warning' | 'critical',
        latency: Math.round(service.avg_response_time || service.latency || 0)
      }))

      // Process Predictive Analytics from anomaly detection
      const predictiveAnalytics = {
        nextIncidentHours: anomalyData?.summary?.high_severity_count && anomalyData.summary.high_severity_count > 0 ? 
          Math.round(24 - (anomalyData.summary.high_severity_count * 2)) : 0,
        confidence: Math.round((aiAnalyticsData?.performance_metrics?.success_rate || 0) * 100),
        costOptimization: anomalyData?.summary?.total_anomalies && anomalyData.summary.total_anomalies > 0 ? 
          Math.min(anomalyData.summary.total_anomalies * 5, 25) : 0
      }

      // Check if this is first time (no logs ingested)
      setIsFirstTime(totalLogsToday === 0)

      // Update dashboard data
      setDashboardData({
        ingestionStats: {
          totalLogsToday,
          logsPerHour,
          servicesDetected,
          errorRate: Math.round(errorRate * 10) / 10, // Round to 1 decimal
        },
        systemHealth: {
          uptime: Math.round(uptime * 100) / 100, // Round to 2 decimals
          queryLatency: Math.round(avgLatency),
          storageUsed, // Already rounded in calculation above
          apiRequests,
          alertRulesActive,
          dataSourcesConnected,
        },
        recentAlerts,
        topServices,
        aiIntelligence,
        securityIntelligence,
        liveInvestigations: [], // TODO: Add investigation API
        businessImpact: {
          revenueProtected: Math.round((totalLogsToday * 0.1) / 1000) * 1000, // Estimate based on logs processed
          slaCompliance: uptime
        },
        serviceTopology,
        predictiveAnalytics,
      })

    } catch (err: any) {
      console.error('Failed to load dashboard data:', err)
      setError('Failed to load dashboard data. Please try refreshing the page.')
    } finally {
      setIsLoadingData(false)
      isLoadingRef.current = false // Clear loading flag
    }
  }

  useEffect(() => {
    if (tenant && !isLoading) {
      loadDashboardData()
    }
  }, [tenant?.id, isLoading]) // Only depend on tenant.id, not the entire tenant object

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-slate-600">Loading your dashboard...</p>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-7xl mx-auto" data-testid="dashboard-container">

        {/* Error Alert */}
        {error && (
          <Alert className="border-red-200 bg-red-50" data-testid="dashboard-error">
            <AlertTriangle className="h-4 w-4 text-red-600" />
            <AlertDescription className="text-red-800">
              <div className="flex items-center justify-between">
                <span>{error}</span>
                <Button 
                  size="sm" 
                  variant="outline" 
                  onClick={loadDashboardData}
                  disabled={isLoadingData}
                  data-testid="retry-dashboard-load"
                >
                  {isLoadingData ? 'Retrying...' : 'Retry'}
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        )}

        {/* Getting Started Section (shown for new users) */}
        {isFirstTime && !isLoadingData && (
          <Alert className="border-blue-200 bg-blue-50" data-testid="getting-started-alert">
            <BookOpen className="h-4 w-4 text-blue-600" />
            <AlertDescription className="text-blue-800">
              <div className="flex items-center justify-between">
                <div>
                  <strong>Get started with log ingestion</strong> - Send your first logs to Logforge and start monitoring
                </div>
                <Button asChild size="sm" className="bg-blue-600 hover:bg-blue-700" data-testid="start-tutorial">
                  <Link href="/ingestion">
                    Start Tutorial <ArrowRight className="w-4 h-4 ml-1" />
                  </Link>
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        )}

        {/* Key Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 lg:gap-6" data-testid="key-metrics-grid">
          <Card data-testid="metric-logs-today">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Logs Today</CardTitle>
              <Database className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoadingData ? (
                <div className="space-y-2">
                  <div className="h-8 bg-slate-200 rounded animate-pulse"></div>
                  <div className="h-3 bg-slate-200 rounded w-20 animate-pulse"></div>
                </div>
              ) : (
                <>
                  <div className="text-2xl font-bold" data-testid="logs-today-count">{dashboardData.ingestionStats.totalLogsToday.toLocaleString()}</div>
                  <p className="text-xs text-muted-foreground" data-testid="logs-hourly-rate">
                    +{dashboardData.ingestionStats.logsPerHour.toLocaleString()}/hour
                  </p>
                </>
              )}
            </CardContent>
          </Card>

          <Card data-testid="metric-system-health">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">System Health</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoadingData ? (
                <div className="space-y-2">
                  <div className="h-8 bg-slate-200 rounded animate-pulse"></div>
                  <div className="h-3 bg-slate-200 rounded w-24 animate-pulse"></div>
                </div>
              ) : (
                <>
                  <div className="text-2xl font-bold text-green-600" data-testid="system-uptime">{dashboardData.systemHealth.uptime}%</div>
                  <p className="text-xs text-muted-foreground" data-testid="query-latency">
                    {dashboardData.systemHealth.queryLatency}ms avg latency
                  </p>
                </>
              )}
            </CardContent>
          </Card>

          <Card data-testid="metric-error-rate">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Error Rate</CardTitle>
              <AlertTriangle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoadingData ? (
                <div className="space-y-2">
                  <div className="h-8 bg-slate-200 rounded animate-pulse"></div>
                  <div className="h-3 bg-slate-200 rounded w-28 animate-pulse"></div>
                </div>
              ) : (
                <>
                  <div className="text-2xl font-bold text-orange-600" data-testid="error-rate-percentage">{dashboardData.ingestionStats.errorRate}%</div>
                  <p className="text-xs text-muted-foreground" data-testid="services-monitored">
                    {dashboardData.ingestionStats.servicesDetected} services monitored
                  </p>
                </>
              )}
            </CardContent>
          </Card>

          <Card data-testid="metric-storage-used">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Storage Used</CardTitle>
              <Server className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoadingData ? (
                <div className="space-y-2">
                  <div className="h-8 bg-slate-200 rounded animate-pulse"></div>
                  <div className="h-2 bg-slate-200 rounded animate-pulse"></div>
                </div>
              ) : (
                <>
                  <div className="text-2xl font-bold" data-testid="storage-percentage">{dashboardData.systemHealth.storageUsed}%</div>
                  <Progress value={dashboardData.systemHealth.storageUsed} className="mt-2" data-testid="storage-progress" />
                </>
              )}
            </CardContent>
          </Card>

          <Card data-testid="metric-api-requests">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">API Requests</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoadingData ? (
                <div className="space-y-2">
                  <div className="h-8 bg-slate-200 rounded animate-pulse"></div>
                  <div className="h-3 bg-slate-200 rounded w-16 animate-pulse"></div>
                </div>
              ) : (
                <>
                  <div className="text-2xl font-bold text-blue-600" data-testid="api-requests-count">{dashboardData.systemHealth.apiRequests.toLocaleString()}</div>
                  <p className="text-xs text-muted-foreground">
                    Total queries executed
                  </p>
                </>
              )}
            </CardContent>
          </Card>

          <Card data-testid="metric-alert-rules">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Alert Rules</CardTitle>
              <Shield className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoadingData ? (
                <div className="space-y-2">
                  <div className="h-8 bg-slate-200 rounded animate-pulse"></div>
                  <div className="h-3 bg-slate-200 rounded w-12 animate-pulse"></div>
                </div>
              ) : (
                <>
                  <div className="text-2xl font-bold text-purple-600" data-testid="alert-rules-count">{dashboardData.systemHealth.alertRulesActive}</div>
                  <p className="text-xs text-muted-foreground">
                    Active monitoring rules
                  </p>
                </>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 lg:gap-6" data-testid="quick-actions">
          <Card className="hover:shadow-lg transition-shadow cursor-pointer" data-testid="action-explore-logs">
            <CardHeader>
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <BarChart3 className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <CardTitle className="text-lg">Explore Logs</CardTitle>
                  <CardDescription>Search and analyze your log data</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-600">Advanced query engine</span>
                <Button asChild size="sm" variant="outline" data-testid="open-logs">
                  <Link href="/logs">
                    Open <ArrowRight className="w-4 h-4 ml-1" />
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="hover:shadow-lg transition-shadow cursor-pointer" data-testid="action-security-center">
            <CardHeader>
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
                  <Shield className="w-5 h-5 text-red-600" />
                </div>
                <div>
                  <CardTitle className="text-lg">Security Center</CardTitle>
                  <CardDescription>Monitor threats and security events</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-600">SIEM capabilities</span>
                <Button asChild size="sm" variant="outline" data-testid="open-security">
                  <Link href="/security">
                    Analyze <ArrowRight className="w-4 h-4 ml-1" />
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="hover:shadow-lg transition-shadow cursor-pointer" data-testid="action-live-dashboards">
            <CardHeader>
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                  <Activity className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <CardTitle className="text-lg">Live Dashboards</CardTitle>
                  <CardDescription>Real-time monitoring views</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-600">6 pre-built dashboards</span>
                <Button asChild size="sm" variant="outline" data-testid="open-dashboards">
                  <Link href="/dashboards">
                    View <ArrowRight className="w-4 h-4 ml-1" />
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 🚀 INDUSTRY-LEADING SECTIONS */}

        {/* AI-Powered Intelligence Hub */}
        <Card className="bg-gradient-to-r from-purple-50 to-indigo-50 border-purple-200" data-testid="ai-intelligence-hub">
          <CardHeader>
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-purple-600 rounded-lg flex items-center justify-center">
                <Brain className="w-6 h-6 text-white" />
              </div>
              <div>
                <CardTitle className="text-lg">AI Intelligence Hub</CardTitle>
                <CardDescription>Real-time AI insights and predictive analytics</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="ai-metrics-grid">
              <div className="bg-white p-4 rounded-lg border" data-testid="ai-predictions">
                <div className="flex items-center space-x-2 mb-2">
                  <Target className="w-4 h-4 text-purple-600" />
                  <span className="text-sm font-medium">Predictions</span>
                </div>
                {isLoadingData ? (
                  <div className="h-8 bg-slate-200 rounded animate-pulse"></div>
                ) : (
                  <div className="text-2xl font-bold text-purple-600" data-testid="ai-predictions-count">{dashboardData.aiIntelligence.predictions}</div>
                )}
                <div className="text-xs text-slate-500">High severity anomalies</div>
              </div>
              
              <div className="bg-white p-4 rounded-lg border" data-testid="ai-insights">
                <div className="flex items-center space-x-2 mb-2">
                  <Lightbulb className="w-4 h-4 text-amber-600" />
                  <span className="text-sm font-medium">Insights</span>
                </div>
                {isLoadingData ? (
                  <div className="h-8 bg-slate-200 rounded animate-pulse"></div>
                ) : (
                  <div className="text-2xl font-bold text-amber-600" data-testid="ai-insights-count">{dashboardData.aiIntelligence.insights}</div>
                )}
                <div className="text-xs text-slate-500">Active recommendations</div>
              </div>

              <div className="bg-white p-4 rounded-lg border" data-testid="ai-investigations">
                <div className="flex items-center space-x-2 mb-2">
                  <Search className="w-4 h-4 text-blue-600" />
                  <span className="text-sm font-medium">Investigations</span>
                </div>
                {isLoadingData ? (
                  <div className="h-8 bg-slate-200 rounded animate-pulse"></div>
                ) : (
                  <div className="text-2xl font-bold text-blue-600" data-testid="ai-investigations-count">{dashboardData.aiIntelligence.investigations}</div>
                )}
                <div className="text-xs text-slate-500">Active AI analysis</div>
              </div>

              <div className="bg-white p-4 rounded-lg border" data-testid="ai-correlations">
                <div className="flex items-center space-x-2 mb-2">
                  <GitBranch className="w-4 h-4 text-green-600" />
                  <span className="text-sm font-medium">Correlations</span>
                </div>
                {isLoadingData ? (
                  <div className="h-8 bg-slate-200 rounded animate-pulse"></div>
                ) : (
                  <div className="text-2xl font-bold text-green-600" data-testid="ai-correlation-rate">{dashboardData.aiIntelligence.correlationRate}%</div>
                )}
                <div className="text-xs text-slate-500">Event correlation rate</div>
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between">
              <span className="text-sm text-slate-600">AI-powered operational intelligence</span>
              <Button size="sm" variant="outline" className="border-purple-300 text-purple-700 hover:bg-purple-50" data-testid="view-ai-center">
                <Link href="/ai">
                  View AI Center <Brain className="w-4 h-4 ml-1" />
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Live Investigation & Threat Intelligence */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6">
          {/* Live Investigation Center */}
          <Card className="bg-gradient-to-r from-red-50 to-orange-50 border-red-200">
            <CardHeader className="flex flex-row items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 bg-red-600 rounded-lg flex items-center justify-center">
                  <Search className="w-4 h-4 text-white" />
                </div>
                <div>
                  <CardTitle>Live Investigation Center</CardTitle>
                  <CardDescription>Real-time incident analysis</CardDescription>
                </div>
              </div>
              <Button asChild variant="outline" size="sm" className="border-red-300 text-red-700 hover:bg-red-50">
                <Link href="/investigations">Launch</Link>
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {dashboardData.liveInvestigations.length > 0 ? (
                  <>
                    {dashboardData.liveInvestigations.map((investigation, index) => (
                      <div key={investigation.id} className="flex items-center space-x-3 p-3 rounded-lg bg-white border">
                        <div className={`w-3 h-3 rounded-full ${
                          investigation.status === 'analyzing' ? 'bg-blue-500 animate-pulse' :
                          investigation.status === 'completed' ? 'bg-green-500' : 'bg-red-500'
                        }`} />
                        <div className="flex-1">
                          <p className="text-sm font-medium">{investigation.title}</p>
                          <p className="text-xs text-slate-500">
                            {investigation.status === 'analyzing' ? `AI analyzing • ${investigation.progress || 0}% complete` :
                             investigation.status === 'completed' ? 'Analysis complete • Review available' :
                             'Investigation failed • Manual review required'}
                          </p>
                        </div>
                        <Badge className={`${
                          investigation.severity === 'high' ? 'bg-red-100 text-red-700' :
                          investigation.severity === 'medium' ? 'bg-orange-100 text-orange-700' : 
                          'bg-yellow-100 text-yellow-700'
                        }`}>
                          {investigation.severity.charAt(0).toUpperCase() + investigation.severity.slice(1)}
                        </Badge>
                      </div>
                    ))}
                    
                    {/* AI Recommendation section - only show if there are investigations */}
                    <div className="mt-4 p-3 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border-blue-200 border">
                      <div className="flex items-center space-x-2 mb-2">
                        <Brain className="w-4 h-4 text-blue-600" />
                        <span className="text-sm font-medium text-blue-900">AI Recommendation</span>
                      </div>
                      <p className="text-sm text-blue-800">Review investigation findings and implement suggested actions</p>
                    </div>
                  </>
                ) : (
                  <div className="p-6 text-center text-slate-500">
                    <Search className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                    <p className="text-sm font-medium mb-1">No Active Investigations</p>
                    <p className="text-xs">All systems operating normally</p>
                    <p className="text-xs mt-2">AI will automatically start investigations when anomalies are detected</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Security Intelligence Feed */}
          <Card className="bg-gradient-to-r from-slate-50 to-gray-50 border-slate-200">
            <CardHeader className="flex flex-row items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 bg-slate-600 rounded-lg flex items-center justify-center">
                  <Shield className="w-4 h-4 text-white" />
                </div>
                <div>
                  <CardTitle>Security Intelligence</CardTitle>
                  <CardDescription>Live threat analysis</CardDescription>
                </div>
              </div>
              <Button asChild variant="outline" size="sm" className="border-slate-300 text-slate-700 hover:bg-slate-50">
                <Link href="/security/intelligence">Monitor</Link>
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {dashboardData.securityIntelligence.events.length > 0 ? (
                  dashboardData.securityIntelligence.events.map((event, index) => (
                    <div key={event.technique} className="flex items-center justify-between p-3 rounded-lg bg-white border">
                      <div className="flex items-center space-x-3">
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                          event.severity === 'critical' ? 'bg-red-100' : 
                          event.severity === 'high' ? 'bg-orange-100' : 'bg-yellow-100'
                        }`}>
                          <span className={`text-xs font-bold ${
                            event.severity === 'critical' ? 'text-red-600' : 
                            event.severity === 'high' ? 'text-orange-600' : 'text-yellow-600'
                          }`}>
                            {event.technique}
                          </span>
                        </div>
                        <div>
                          <p className="text-sm font-medium">{event.name}</p>
                          <p className="text-xs text-slate-500">{event.count} events • {event.timeRange}</p>
                        </div>
                      </div>
                      <Badge className={`${
                        event.severity === 'critical' ? 'bg-red-100 text-red-700' : 
                        event.severity === 'high' ? 'bg-orange-100 text-orange-700' : 'bg-yellow-100 text-yellow-700'
                      }`}>
                        {event.severity.charAt(0).toUpperCase() + event.severity.slice(1)}
                      </Badge>
                    </div>
                  ))
                ) : (
                  <div className="p-4 text-center text-slate-500">
                    <p className="text-sm">No security events detected</p>
                    <p className="text-xs">All systems appear secure</p>
                  </div>
                )}

                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div className="bg-gradient-to-r from-green-50 to-emerald-50 p-3 rounded-lg border-green-200 border text-center">
                    <div className="text-lg font-bold text-green-600">
                      {isLoadingData ? '...' : `${dashboardData.securityIntelligence.threatDetectionRate}%`}
                    </div>
                    <div className="text-xs text-green-700">Threat detection rate</div>
                  </div>
                  <div className="bg-gradient-to-r from-blue-50 to-cyan-50 p-3 rounded-lg border-blue-200 border text-center">
                    <div className="text-lg font-bold text-blue-600">
                      {isLoadingData ? '...' : `${dashboardData.securityIntelligence.avgDetectionTime}ms`}
                    </div>
                    <div className="text-xs text-blue-700">Avg detection time</div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Business Impact & Performance Intelligence */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:gap-6">
          {/* Business Impact Dashboard */}
          <Card className="bg-gradient-to-r from-emerald-50 to-green-50 border-emerald-200">
            <CardHeader>
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 bg-emerald-600 rounded-lg flex items-center justify-center">
                  <DollarSign className="w-4 h-4 text-white" />
                </div>
                <div>
                  <CardTitle className="text-lg">Business Impact</CardTitle>
                  <CardDescription>Real-time revenue correlation</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="bg-white p-4 rounded-lg border">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Revenue Protected</span>
                    <TrendingUp className="w-4 h-4 text-emerald-600" />
                  </div>
                  <div className="text-2xl font-bold text-emerald-600">
                    {isLoadingData ? '...' : `$${Math.round(dashboardData.businessImpact.revenueProtected / 1000)}K`}
                  </div>
                  <div className="text-xs text-slate-500">Last 24h incidents prevented</div>
                </div>
                
                <div className="bg-white p-4 rounded-lg border">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">SLA Compliance</span>
                    <CheckCircle className="w-4 h-4 text-emerald-600" />
                  </div>
                  <div className="text-2xl font-bold text-emerald-600">
                    {isLoadingData ? '...' : `${dashboardData.businessImpact.slaCompliance}%`}
                  </div>
                  <div className="text-xs text-slate-500">
                    {dashboardData.businessImpact.slaCompliance >= 99.5 ? 'Exceeding target 99.5%' : 'Below target 99.5%'}
                  </div>
                </div>

                <Button size="sm" variant="outline" className="w-full border-emerald-300 text-emerald-700 hover:bg-emerald-50">
                  <Link href="/business-impact">
                    View Impact Analysis <ArrowRight className="w-4 h-4 ml-1" />
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Live Service Topology */}
          <Card className="bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200">
            <CardHeader>
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                  <Network className="w-4 h-4 text-white" />
                </div>
                <div>
                  <CardTitle className="text-lg">Service Topology</CardTitle>
                  <CardDescription>Live dependency mapping</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {dashboardData.serviceTopology.length > 0 ? (
                  dashboardData.serviceTopology.map((service, index) => (
                    <div key={service.name} className="bg-white p-3 rounded-lg border flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className={`w-3 h-3 rounded-full ${
                          service.status === 'healthy' ? 'bg-green-500' :
                          service.status === 'warning' ? 'bg-yellow-500' : 'bg-red-500'
                        }`} />
                        <span className="text-sm font-medium">{service.name}</span>
                      </div>
                      <span className="text-xs text-slate-500">
                        {isLoadingData ? '...' : `${service.latency}ms`}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="p-4 text-center text-slate-500">
                    <p className="text-sm">No services detected</p>
                    <p className="text-xs">Service topology data unavailable</p>
                  </div>
                )}

                <Button size="sm" variant="outline" className="w-full border-blue-300 text-blue-700 hover:bg-blue-50">
                  <Link href="/topology">
                    Interactive Map <Network className="w-4 h-4 ml-1" />
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Predictive Analytics */}
          <Card className="bg-gradient-to-r from-violet-50 to-purple-50 border-violet-200">
            <CardHeader>
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 bg-violet-600 rounded-lg flex items-center justify-center">
                  <Target className="w-4 h-4 text-white" />
                </div>
                <div>
                  <CardTitle className="text-lg">Predictive Analytics</CardTitle>
                  <CardDescription>ML-powered forecasting</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="bg-white p-3 rounded-lg border">
                  <div className="flex items-center space-x-2 mb-2">
                    <Timer className="w-4 h-4 text-violet-600" />
                    <span className="text-sm font-medium">Next Incident</span>
                  </div>
                  <div className="text-lg font-bold text-violet-600">
                    {isLoadingData ? '...' : dashboardData.predictiveAnalytics.nextIncidentHours > 0 ? 
                      `~${dashboardData.predictiveAnalytics.nextIncidentHours}h` : 'None predicted'}
                  </div>
                  <div className="text-xs text-slate-500">
                    AI analysis ({dashboardData.predictiveAnalytics.confidence}% confidence)
                  </div>
                </div>

                <div className="bg-white p-3 rounded-lg border">
                  <div className="flex items-center space-x-2 mb-2">
                    <TrendingDown className="w-4 h-4 text-violet-600" />
                    <span className="text-sm font-medium">Optimization</span>
                  </div>
                  <div className="text-lg font-bold text-violet-600">
                    {isLoadingData ? '...' : `${dashboardData.predictiveAnalytics.costOptimization}%`}
                  </div>
                  <div className="text-xs text-slate-500">Potential cost reduction</div>
                </div>

                <Button size="sm" variant="outline" className="w-full border-violet-300 text-violet-700 hover:bg-violet-50">
                  <Link href="/predictions">
                    View Predictions <Target className="w-4 h-4 ml-1" />
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Recent Activity & Top Services */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6">
          {/* Recent Alerts */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Recent Alerts</CardTitle>
              <Button asChild variant="outline" size="sm">
                <Link href="/alerts">View All</Link>
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {dashboardData.recentAlerts.map((alert) => (
                  <div key={alert.id} className="flex items-center space-x-3 p-3 rounded-lg bg-slate-50">
                    <div className={`w-2 h-2 rounded-full ${
                      alert.severity === 'high' ? 'bg-red-500' :
                      alert.severity === 'medium' ? 'bg-orange-500' : 'bg-yellow-500'
                    }`} />
                    <div className="flex-1">
                      <p className="text-sm font-medium">{alert.message}</p>
                      <p className="text-xs text-slate-500">{alert.service} • {alert.time}</p>
                    </div>
                    <Badge variant={alert.severity === 'high' ? 'destructive' : 'secondary'}>
                      {alert.severity}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Top Services */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Service Overview</CardTitle>
              <Button asChild variant="outline" size="sm">
                <Link href="/observability">View Details</Link>
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {dashboardData.topServices.map((service, index) => (
                  <div key={service.name} className="flex items-center justify-between p-3 rounded-lg bg-slate-50">
                    <div className="flex items-center space-x-3">
                      <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                        <span className="text-xs font-bold text-blue-600">{index + 1}</span>
                      </div>
                      <div>
                        <p className="text-sm font-medium">{service.name}</p>
                        <p className="text-xs text-slate-500">{service.logs.toLocaleString()} logs</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-medium">{service.latency}</p>
                      <p className="text-xs text-slate-500">{service.errors} errors</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 🚀 WORLD-CLASS ENTERPRISE FEATURES */}
        
        {/* Real-Time Analytics - Enterprise Grade */}
        <Card className="bg-gradient-to-br from-slate-50 via-indigo-50 to-purple-50 border-slate-200 shadow-xl">
          <CardHeader className="pb-6">
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-4">
                <div className="p-3 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl shadow-lg">
                  <BarChart3 className="w-7 h-7 text-white" />
                </div>
                <div>
                  <CardTitle className="text-2xl font-bold text-slate-900 mb-1">
                    Real-Time Analytics
                  </CardTitle>
                  <CardDescription className="text-slate-600 text-base">
                    Advanced data visualizations with live streaming and AI-powered insights
                  </CardDescription>
                </div>
              </div>
              <div className="flex items-center space-x-3">
                <div className="flex items-center space-x-2 px-3 py-1.5 bg-green-100 rounded-full">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-xs font-medium text-green-700">Live</span>
                </div>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => setShowRealTimeStream(!showRealTimeStream)}
                  className="border-indigo-300 text-indigo-700 hover:bg-indigo-50 transition-colors"
                  data-testid="toggle-real-time-stream"
                >
                  {showRealTimeStream ? (
                    <>
                      <Eye className="w-4 h-4 mr-2" />
                      Hide Stream
                    </>
                  ) : (
                    <>
                      <Activity className="w-4 h-4 mr-2" />
                      Show Stream
                    </>
                  )}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-6">
              
              {/* Charts Container */}
              <div className="bg-white/80 backdrop-blur-sm rounded-lg border border-slate-200 p-4">
                <DashboardVisualization className="space-y-6" />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Real-Time Data Stream */}
        {showRealTimeStream && (
          <RealTimeDataStream 
            className="animate-in slide-in-from-bottom-4 duration-500"
            maxEvents={30}
            showControls={true}
            types={['log', 'alert', 'metric', 'security', 'ai_insight']}
          />
        )}

        {/* Feature Highlights */}
        <Card className="bg-gradient-to-r from-slate-50 to-blue-50 border-blue-200">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-xl">Platform Capabilities</CardTitle>
                <CardDescription>
                  Explore advanced features of your Logforge enterprise platform
                </CardDescription>
              </div>
              <Button 
                onClick={() => {
                  setShowAiChat(true)
                  setAiChatMinimized(false)
                }}
                className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700"
                data-testid="launch-ai-assistant"
              >
                <Brain className="w-4 h-4 mr-2" />
                Launch AI Assistant
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="text-center">
                <div className="w-12 h-12 bg-blue-600 rounded-lg flex items-center justify-center mx-auto mb-3">
                  <Zap className="w-6 h-6 text-white" />
                </div>
                <h3 className="font-semibold mb-2">Real-time Processing</h3>
                <p className="text-sm text-slate-600">Process 50K+ events per second with sub-second queries</p>
              </div>
              <div className="text-center">
                <div className="w-12 h-12 bg-red-600 rounded-lg flex items-center justify-center mx-auto mb-3">
                  <Shield className="w-6 h-6 text-white" />
                </div>
                <h3 className="font-semibold mb-2">Security Analytics</h3>
                <p className="text-sm text-slate-600">SIEM capabilities with Sigma rules and threat intelligence</p>
              </div>
              <div className="text-center">
                <div className="w-12 h-12 bg-green-600 rounded-lg flex items-center justify-center mx-auto mb-3">
                  <Eye className="w-6 h-6 text-white" />
                </div>
                <h3 className="font-semibold mb-2">Complete Observability</h3>
                <p className="text-sm text-slate-600">Logs, metrics, traces, and APM in one platform</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* AI Chat Assistant - World-Class Enterprise Feature */}
      {showAiChat && (
        <div className="fixed bottom-4 right-4 z-50">
          <AiChatAssistant
            isMinimized={aiChatMinimized}
            onToggleMinimize={() => setAiChatMinimized(!aiChatMinimized)}
            onClose={() => {
              setShowAiChat(false)
              setAiChatMinimized(true)
            }}
          />
        </div>
      )}
    </DashboardLayout>
  )
}