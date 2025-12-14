'use client'

import { useEffect, useState, useRef } from 'react'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import DashboardLayout from '@/components/layout/DashboardLayout'
import LogsOverviewWidget from '@/components/centrum/LogsOverviewWidget'
import AlertsOverviewWidget from '@/components/centrum/AlertsOverviewWidget'
import SecurityEventsWidget from '@/components/centrum/SecurityEventsWidget'
import ObservabilityStatsWidgets from '@/components/centrum/ObservabilityStatsWidgets'
import UsageStatsWidgets from '@/components/centrum/UsageStatsWidgets'
import APMPerformanceWidgets from '@/components/centrum/APMPerformanceWidgets'
import LiveStreamingPanel from '@/components/centrum/LiveStreamingPanel'
import { apiClient } from '@/lib/api'

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
        params: {
          start_time: start_time,
          end_time: end_time
        }
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

      // Call the security dashboard endpoint
      const response = await apiClient.get('/v1/security/dashboard', {
        params: {
          time_range: '24h'
        }
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
        params: {
          start_time: start_time,
          end_time: end_time
        }
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
        params: {
          start_time: start_time,
          end_time: end_time
        }
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
        params: {
          start_time: start_time,
          end_time: end_time
        },
        headers: {
          'X-Customer-ID': 'default' // This will be replaced by middleware
        }
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

  // Single useEffect to load all data with staggered timing to prevent overwhelming the API
  useEffect(() => {
    // Load data in batches with slight delays to prevent request cancellation
    const loadAllData = async () => {
      // Batch 1: Critical widgets (load immediately)
      loadUsageOverview()
      loadLogsOverview()

      // Batch 2: Secondary widgets (small delay)
      setTimeout(() => {
        loadAlertsOverview()
        loadObservabilityOverview()
      }, 50)

      // Batch 3: Additional widgets (slightly longer delay)
      setTimeout(() => {
        loadSecurityOverview()
        loadAPMOverview()
      }, 100)
    }

    loadAllData()

    // Cleanup function to abort all requests on unmount or dependency change
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
      if (alertsAbortControllerRef.current) {
        alertsAbortControllerRef.current.abort()
      }
      if (securityAbortControllerRef.current) {
        securityAbortControllerRef.current.abort()
      }
      if (observabilityAbortControllerRef.current) {
        observabilityAbortControllerRef.current.abort()
      }
      if (usageAbortControllerRef.current) {
        usageAbortControllerRef.current.abort()
      }
      if (apmAbortControllerRef.current) {
        apmAbortControllerRef.current.abort()
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentTimeRange.value]) // Reload when time range changes

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-7xl mx-auto" data-testid="centrum-container">
        {/* Usage Stats - Top Row */}
        <UsageStatsWidgets
          data={usageData}
          isLoading={isLoadingUsage}
        />

        {/* Observability Stats - Second Row */}
        <ObservabilityStatsWidgets
          data={observabilityData}
          isLoading={isLoadingObservability}
        />

        {/* APM Performance Stats - Third Row */}
        <APMPerformanceWidgets
          data={apmData}
          isLoading={isLoadingApm}
        />

        {/* Main Widgets - Logs, Alerts, and Security Overview */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <LogsOverviewWidget
            data={logsData}
            isLoading={isLoading}
            timeRange={currentTimeRange.label}
          />
          <AlertsOverviewWidget
            data={alertsData}
            isLoading={isLoadingAlerts}
            timeRange={currentTimeRange.label}
          />
          <SecurityEventsWidget
            data={securityData}
            isLoading={isLoadingSecurity}
            timeRange={currentTimeRange.label}
          />
        </div>

        {/* Live Streaming Panel - Fourth Row */}
        <LiveStreamingPanel />
      </div>
    </DashboardLayout>
  )
}
