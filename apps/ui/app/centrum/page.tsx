'use client'

import { useEffect, useState, useRef } from 'react'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import DashboardLayout from '@/components/layout/DashboardLayout'
import LogsOverviewWidget from '@/components/centrum/LogsOverviewWidget'
import { apiClient } from '@/lib/api'

export default function CentrumPage() {
  const { getApiTimeRange, currentTimeRange } = useTimeRange()
  const [logsData, setLogsData] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(true)
  const abortControllerRef = useRef<AbortController | null>(null)

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

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-7xl mx-auto" data-testid="centrum-container">
        {/* Header */}
        {/* Widgets Grid */}
        <div className="grid grid-cols-1 gap-6">
          <LogsOverviewWidget
            data={logsData}
            isLoading={isLoading}
            timeRange={currentTimeRange.label}
          />
        </div>
      </div>
    </DashboardLayout>
  )
}
