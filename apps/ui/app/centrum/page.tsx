'use client'

import { useEffect, useState, useRef } from 'react'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import DashboardLayout from '@/components/layout/DashboardLayout'
import LogsOverviewWidget from '@/components/centrum/LogsOverviewWidget'
import AlertsOverviewWidget from '@/components/centrum/AlertsOverviewWidget'
import SecurityEventsWidget from '@/components/centrum/SecurityEventsWidget'
import ObservabilityStatsWidgets from '@/components/centrum/ObservabilityStatsWidgets'
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
  const abortControllerRef = useRef<AbortController | null>(null)
  const alertsAbortControllerRef = useRef<AbortController | null>(null)
  const securityAbortControllerRef = useRef<AbortController | null>(null)
  const observabilityAbortControllerRef = useRef<AbortController | null>(null)

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

  useEffect(() => {
    loadLogsOverview()

    // Cleanup function to abort request on unmount or dependency change
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentTimeRange.value]) // Reload when time range changes

  useEffect(() => {
    loadAlertsOverview()

    // Cleanup function to abort request on unmount or dependency change
    return () => {
      if (alertsAbortControllerRef.current) {
        alertsAbortControllerRef.current.abort()
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentTimeRange.value]) // Reload when time range changes

  useEffect(() => {
    loadSecurityOverview()

    // Cleanup function to abort request on unmount or dependency change
    return () => {
      if (securityAbortControllerRef.current) {
        securityAbortControllerRef.current.abort()
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentTimeRange.value]) // Reload when time range changes

  useEffect(() => {
    loadObservabilityOverview()

    // Cleanup function to abort request on unmount or dependency change
    return () => {
      if (observabilityAbortControllerRef.current) {
        observabilityAbortControllerRef.current.abort()
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentTimeRange.value]) // Reload when time range changes

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-7xl mx-auto" data-testid="centrum-container">
        {/* Observability Stats - Top Row */}
        <ObservabilityStatsWidgets
          data={observabilityData}
          isLoading={isLoadingObservability}
        />

        {/* Main Widgets - Logs, Alerts, and Security Overview */}
        <div className="flex flex-wrap gap-6">
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
      </div>
    </DashboardLayout>
  )
}
