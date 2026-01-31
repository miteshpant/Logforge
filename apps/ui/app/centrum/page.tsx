'use client'

import { useEffect, useState, useRef, memo, useCallback, lazy, Suspense } from 'react'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import DashboardLayout from '@/components/layout/DashboardLayout'
import LogsOverviewWidget from '@/components/centrum/LogsOverviewWidget'
import AlertsOverviewWidget from '@/components/centrum/AlertsOverviewWidget'
import SecurityEventsWidget from '@/components/centrum/SecurityEventsWidget'
import ObservabilityStatsWidgets from '@/components/centrum/ObservabilityStatsWidgets'
import UsageStatsWidgets from '@/components/centrum/UsageStatsWidgets'
import APMPerformanceWidgets from '@/components/centrum/APMPerformanceWidgets'
import IncidentCommandCenter from '@/components/centrum/IncidentCommandCenter'
import AIInsightsWidget from '@/components/centrum/AIInsightsWidget'
import AnomalyStatsWidget from '@/components/centrum/AnomalyStatsWidget'
import { apiClient } from '@/lib/api'

// Lazy load streaming panel to improve initial page load
const LiveStreamingPanel = lazy(() => import('@/components/centrum/LiveStreamingPanel'))

// Memoized widget components to prevent unnecessary re-renders
const MemoizedUsageStats = memo(UsageStatsWidgets)
const MemoizedObservabilityStats = memo(ObservabilityStatsWidgets)
const MemoizedAPMPerformance = memo(APMPerformanceWidgets)
const MemoizedLogsOverview = memo(LogsOverviewWidget)
const MemoizedAlertsOverview = memo(AlertsOverviewWidget)
const MemoizedSecurityEvents = memo(SecurityEventsWidget)
const MemoizedAIInsights = memo(AIInsightsWidget)
const MemoizedAnomalyStats = memo(AnomalyStatsWidget)

export default function CentrumPage() {
  const { getApiTimeRange, currentTimeRange } = useTimeRange()
  const [logsData, setLogsData] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [alertsData, setAlertsData] = useState<any>(null)
  const [isLoadingAlerts, setIsLoadingAlerts] = useState(true)
  const [securityData, setSecurityData] = useState<any>(null)
  const [isLoadingSecurity, setIsLoadingSecurity] = useState(true)
  const [observabilityData, setObservabilityData] = useState<any>(null)
  const [isLoadingObservability, setIsLoadingObservability] = useState(true)
  const [usageData, setUsageData] = useState<any>(null)
  const [isLoadingUsage, setIsLoadingUsage] = useState(true)
  const [apmData, setApmData] = useState<any>(null)
  const [isLoadingApm, setIsLoadingApm] = useState(true)

  // Progressive loading flags - enable widgets one by one
  const [enableUsage, setEnableUsage] = useState(false)
  const [enableLogs, setEnableLogs] = useState(false)
  const [enableAlerts, setEnableAlerts] = useState(false)
  const [enableObservability, setEnableObservability] = useState(false)
  const [enableSecurity, setEnableSecurity] = useState(false)
  const [enableAPM, setEnableAPM] = useState(false)

  const abortControllerRef = useRef<AbortController | null>(null)
  const alertsAbortControllerRef = useRef<AbortController | null>(null)
  const securityAbortControllerRef = useRef<AbortController | null>(null)
  const observabilityAbortControllerRef = useRef<AbortController | null>(null)
  const usageAbortControllerRef = useRef<AbortController | null>(null)
  const apmAbortControllerRef = useRef<AbortController | null>(null)

  const loadLogsOverview = async () => {
    try {
      // Cancel any pending request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }

      // Create new abort controller for this request
      abortControllerRef.current = new AbortController()

      setIsLoading(true)
      const { start_time, end_time } = getApiTimeRange()

      // Call the advanced query endpoint directly with group_by support
      const response = await apiClient.post('/v1/query/advanced', {
        start_time: start_time,
        end_time: end_time,
        aggregations: [
          {
            type: 'count',
            field: '*',
            alias: 'total_logs'
          },
          {
            type: 'unique',
            field: 'service',
            alias: 'affected_services'
          },
          {
            type: 'cardinality',
            field: 'host',
            alias: 'affected_hosts'
          }
        ],
        group_by: ['level']
      })

      // Handle both wrapped and unwrapped response formats
      const data = response?.data || response

      if (data) {
        setLogsData(data)
      }
    } catch (error: any) {
      // Don't log aborted requests as errors
      if (error.name !== 'AbortError' && error.name !== 'CanceledError') {
        console.error('Failed to load logs overview:', error)
      }
    } finally {
      setIsLoading(false)
    }
  }

  const loadAlertsOverview = async () => {
    try {
      // Cancel any pending request
      if (alertsAbortControllerRef.current) {
        alertsAbortControllerRef.current.abort()
      }

      // Create new abort controller for this request
      alertsAbortControllerRef.current = new AbortController()

      setIsLoadingAlerts(true)
      const { start_time, end_time } = getApiTimeRange()

      // Call the alerts overview endpoint
      const response = await apiClient.get('/v1/alerts/stats/overview', {
        start_time: start_time,
        end_time: end_time
      })

      // Handle both wrapped and unwrapped response formats
      const data = response?.data || response

      if (data) {
        setAlertsData(data)
      }
    } catch (error: any) {
      // Don't log aborted requests as errors
      if (error.name !== 'AbortError' && error.name !== 'CanceledError') {
        console.error('Failed to load alerts overview:', error)
      }
    } finally {
      setIsLoadingAlerts(false)
    }
  }

  const loadSecurityOverview = async () => {
    try {
      // Cancel any pending request
      if (securityAbortControllerRef.current) {
        securityAbortControllerRef.current.abort()
      }

      // Create new abort controller for this request
      securityAbortControllerRef.current = new AbortController()

      setIsLoadingSecurity(true)
      const { start_time, end_time } = getApiTimeRange()

      // Call the security dashboard endpoint with the selected time range
      const response = await apiClient.get('/v1/security/dashboard', {
        start_time: start_time,
        end_time: end_time
      })

      // Handle both wrapped and unwrapped response formats
      const data = response?.data || response

      if (data) {
        setSecurityData(data)
      }
    } catch (error: any) {
      // Don't log aborted requests as errors
      if (error.name !== 'AbortError' && error.name !== 'CanceledError') {
        console.error('Failed to load security overview:', error)
      }
    } finally {
      setIsLoadingSecurity(false)
    }
  }

  const loadObservabilityOverview = async () => {
    try {
      // Cancel any pending request
      if (observabilityAbortControllerRef.current) {
        observabilityAbortControllerRef.current.abort()
      }

      // Create new abort controller for this request
      observabilityAbortControllerRef.current = new AbortController()

      setIsLoadingObservability(true)
      const { start_time, end_time } = getApiTimeRange()

      // Call the observability overview endpoint
      const response = await apiClient.get('/v1/observability/overview/stats', {
        start_time: start_time,
        end_time: end_time
      })

      // Handle both wrapped and unwrapped response formats
      const data = response?.data || response

      if (data) {
        setObservabilityData(data)
      }
    } catch (error: any) {
      // Don't log aborted requests as errors
      if (error.name !== 'AbortError' && error.name !== 'CanceledError') {
        console.error('Failed to load observability overview:', error)
      }
    } finally {
      setIsLoadingObservability(false)
    }
  }

  const loadUsageOverview = async () => {
    try {
      // Cancel any pending request
      if (usageAbortControllerRef.current) {
        usageAbortControllerRef.current.abort()
      }

      // Create new abort controller for this request
      usageAbortControllerRef.current = new AbortController()

      setIsLoadingUsage(true)
      const { start_time, end_time } = getApiTimeRange()

      // Call the usage overview endpoint with time range
      const response = await apiClient.get('/v1/usage/overview/stats', {
        start_time: start_time,
        end_time: end_time
      })

      // Handle both wrapped and unwrapped response formats
      const data = response?.data || response

      if (data) {
        setUsageData(data)
      }
    } catch (error: any) {
      // Don't log aborted requests as errors
      if (error.name !== 'AbortError' && error.name !== 'CanceledError') {
        console.error('Failed to load usage overview:', error)
      }
    } finally {
      setIsLoadingUsage(false)
    }
  }

  const loadAPMOverview = async () => {
    try {
      // Cancel any pending request
      if (apmAbortControllerRef.current) {
        apmAbortControllerRef.current.abort()
      }

      // Create new abort controller for this request
      apmAbortControllerRef.current = new AbortController()

      setIsLoadingApm(true)
      const { start_time, end_time } = getApiTimeRange()

      // Call the APM overview stats endpoint
      const response = await apiClient.get('/v1/observability/apm/overview/stats', {
        start_time: start_time,
        end_time: end_time
      })

      // Handle both wrapped and unwrapped response formats
      const data = response?.data || response

      if (data) {
        setApmData(data)
      }
    } catch (error: any) {
      // Don't log aborted requests as errors
      if (error.name !== 'AbortError' && error.name !== 'CanceledError') {
        console.error('Failed to load APM overview:', error)
      }
    } finally {
      setIsLoadingApm(false)
    }
  }

  // Progressive loading - Enable widgets one by one for better performance
  useEffect(() => {
    console.log('🚀 Progressive loading started')

    // Reset all flags
    setEnableUsage(false)
    setEnableLogs(false)
    setEnableAlerts(false)
    setEnableObservability(false)
    setEnableSecurity(false)
    setEnableAPM(false)

    // Priority 1: Usage (immediate)
    setEnableUsage(true)

    // Priority 2: Logs (300ms delay)
    const timer1 = setTimeout(() => {
      console.log('✅ Enabling Logs widget')
      setEnableLogs(true)
    }, 300)

    // Priority 3: Alerts (600ms delay)
    const timer2 = setTimeout(() => {
      console.log('✅ Enabling Alerts widget')
      setEnableAlerts(true)
    }, 600)

    // Priority 4: Observability (900ms delay)
    const timer3 = setTimeout(() => {
      console.log('✅ Enabling Observability widget')
      setEnableObservability(true)
    }, 900)

    // Priority 5: Security (1200ms delay)
    const timer4 = setTimeout(() => {
      console.log('✅ Enabling Security widget')
      setEnableSecurity(true)
    }, 1200)

    // Priority 6: APM (1500ms delay)
    const timer5 = setTimeout(() => {
      console.log('✅ Enabling APM widget')
      setEnableAPM(true)
    }, 1500)

    // Cleanup function
    return () => {
      clearTimeout(timer1)
      clearTimeout(timer2)
      clearTimeout(timer3)
      clearTimeout(timer4)
      clearTimeout(timer5)

      // Abort all pending requests
      if (abortControllerRef.current) abortControllerRef.current.abort()
      if (alertsAbortControllerRef.current) alertsAbortControllerRef.current.abort()
      if (securityAbortControllerRef.current) securityAbortControllerRef.current.abort()
      if (observabilityAbortControllerRef.current) observabilityAbortControllerRef.current.abort()
      if (usageAbortControllerRef.current) usageAbortControllerRef.current.abort()
      if (apmAbortControllerRef.current) apmAbortControllerRef.current.abort()
    }
  }, [currentTimeRange.value])

  // Load Usage when enabled - immediate
  useEffect(() => {
    if (enableUsage) {
      console.log('📊 Loading Usage data...')
      loadUsageOverview()
    }
  }, [enableUsage, currentTimeRange.value])

  // Load Logs when enabled - 100ms delay to stagger API calls
  useEffect(() => {
    if (enableLogs) {
      const timer = setTimeout(() => {
        console.log('📝 Loading Logs data...')
        loadLogsOverview()
      }, 100)
      return () => clearTimeout(timer)
    }
  }, [enableLogs, currentTimeRange.value])

  // Load Alerts when enabled - 200ms delay
  useEffect(() => {
    if (enableAlerts) {
      const timer = setTimeout(() => {
        console.log('🚨 Loading Alerts data...')
        loadAlertsOverview()
      }, 200)
      return () => clearTimeout(timer)
    }
  }, [enableAlerts, currentTimeRange.value])

  // Load Observability when enabled - 300ms delay
  useEffect(() => {
    if (enableObservability) {
      const timer = setTimeout(() => {
        console.log('👁️ Loading Observability data...')
        loadObservabilityOverview()
      }, 300)
      return () => clearTimeout(timer)
    }
  }, [enableObservability, currentTimeRange.value])

  // Load Security when enabled - 400ms delay
  useEffect(() => {
    if (enableSecurity) {
      const timer = setTimeout(() => {
        console.log('🔒 Loading Security data...')
        loadSecurityOverview()
      }, 400)
      return () => clearTimeout(timer)
    }
  }, [enableSecurity, currentTimeRange.value])

  // Load APM when enabled - 500ms delay
  useEffect(() => {
    if (enableAPM) {
      const timer = setTimeout(() => {
        console.log('⚡ Loading APM data...')
        loadAPMOverview()
      }, 500)
      return () => clearTimeout(timer)
    }
  }, [enableAPM, currentTimeRange.value])

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-7xl mx-auto" data-testid="centrum-container">
        {/* Usage Stats - Top Row */}
        <MemoizedUsageStats
          data={usageData}
          isLoading={isLoadingUsage}
        />

        {/* Observability + APM Stats */}
        <MemoizedObservabilityStats
          data={observabilityData}
          isLoading={isLoadingObservability}
        />

        {/* Incident Command Center - Full Width */}
        <IncidentCommandCenter timeRange={currentTimeRange.label} />

        {/* Main Widgets - Logs, Alerts, and Security Overview */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <MemoizedLogsOverview
            data={logsData}
            isLoading={isLoading}
            timeRange={currentTimeRange.label}
          />
          <MemoizedAlertsOverview
            data={alertsData}
            isLoading={isLoadingAlerts}
            timeRange={currentTimeRange.label}
          />
          <MemoizedSecurityEvents
            data={securityData}
            isLoading={isLoadingSecurity}
            timeRange={currentTimeRange.label}
          />
        </div>

        {/* AI Intelligence Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <MemoizedAIInsights />
          <MemoizedAnomalyStats />
        </div>

        {/* Live Streaming Panel - Bottom Row (Lazy Loaded) */}
        <Suspense fallback={
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6">
            <div className="animate-pulse">
              <div className="h-4 bg-slate-700 rounded w-1/4 mb-4"></div>
              <div className="h-32 bg-slate-700 rounded"></div>
            </div>
          </div>
        }>
          <LiveStreamingPanel />
        </Suspense>
      </div>
    </DashboardLayout>
  )
}
