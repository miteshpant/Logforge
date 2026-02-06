'use client'

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'

export interface TimeRange {
  label: string
  value: string
  startTime: Date
  endTime: Date
  isCustom?: boolean
  description?: string
}

export interface AutoRefreshInterval {
  label: string
  value: string
  ms: number
}

export const AUTO_REFRESH_INTERVALS: AutoRefreshInterval[] = [
  { label: 'Off', value: 'off', ms: 0 },
  { label: '15 seconds', value: '15s', ms: 15 * 1000 },
  { label: '30 seconds', value: '30s', ms: 30 * 1000 },
  { label: '1 minute', value: '1m', ms: 60 * 1000 },
  { label: '5 minutes', value: '5m', ms: 5 * 60 * 1000 },
  { label: '10 minutes', value: '10m', ms: 10 * 60 * 1000 },
  { label: '30 minutes', value: '30m', ms: 30 * 60 * 1000 },
  { label: '1 hour', value: '1h', ms: 60 * 60 * 1000 },
]

export interface TimeRangeContextType {
  currentTimeRange: TimeRange
  setTimeRange: (timeRange: TimeRange) => void
  refreshData: () => void
  lastRefresh: Date
  isRefreshing: boolean
  availableRanges: TimeRange[]
  getApiTimeRange: () => { start_time: string; end_time: string; time_range: string }
  createCustomRange: (start: Date, end: Date) => TimeRange
  // New centralized auto-refresh functionality
  useAutoRefresh: (refreshFn: (newTimeRange: TimeRange) => void | Promise<void>, dependencies?: any[]) => void
  // Auto-refresh with sliding window
  autoRefreshInterval: AutoRefreshInterval
  setAutoRefreshInterval: (interval: AutoRefreshInterval) => void
  autoRefreshIntervals: AutoRefreshInterval[]
  setCustomAutoRefreshInterval: (seconds: number) => void
  // Refresh trigger counter - increments on every auto-refresh or manual refresh
  refreshTrigger: number
}

const TimeRangeContext = createContext<TimeRangeContextType | undefined>(undefined)

// Predefined time ranges with enterprise-grade options
const createTimeRanges = (): TimeRange[] => {
  const now = new Date()
  
  return [
    {
      label: 'Last 15 minutes',
      value: '15m',
      startTime: new Date(now.getTime() - 15 * 60 * 1000),
      endTime: now,
      description: 'Real-time monitoring'
    },
    {
      label: 'Last 30 minutes', 
      value: '30m',
      startTime: new Date(now.getTime() - 30 * 60 * 1000),
      endTime: now,
      description: 'Recent activity'
    },
    {
      label: 'Last hour',
      value: '1h',
      startTime: new Date(now.getTime() - 60 * 60 * 1000),
      endTime: now,
      description: 'Hourly overview'
    },
    {
      label: 'Last 4 hours',
      value: '4h', 
      startTime: new Date(now.getTime() - 4 * 60 * 60 * 1000),
      endTime: now,
      description: 'Extended monitoring'
    },
    {
      label: 'Last 12 hours',
      value: '12h',
      startTime: new Date(now.getTime() - 12 * 60 * 60 * 1000),
      endTime: now,
      description: 'Half-day analysis'
    },
    {
      label: 'Last 24 hours',
      value: '24h',
      startTime: new Date(now.getTime() - 24 * 60 * 60 * 1000),
      endTime: now,
      description: 'Daily insights'
    },
    {
      label: 'Last 3 days',
      value: '3d',
      startTime: new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000),
      endTime: now,
      description: 'Multi-day trends'
    },
    {
      label: 'Last 7 days',
      value: '7d',
      startTime: new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000),
      endTime: now,
      description: 'Weekly patterns'
    },
    {
      label: 'Last 30 days',
      value: '30d',
      startTime: new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000),
      endTime: now,
      description: 'Monthly analysis'
    },
    {
      label: 'Last 90 days',
      value: '90d',
      startTime: new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000),
      endTime: now,
      description: 'Quarterly trends'
    }
  ]
}

interface TimeRangeProviderProps {
  children: React.ReactNode
  defaultRange?: string
}

export const TimeRangeProvider: React.FC<TimeRangeProviderProps> = ({
  children,
  defaultRange = '24h'
}) => {
  const [availableRanges] = useState<TimeRange[]>(createTimeRanges())
  const [currentTimeRange, setCurrentTimeRange] = useState<TimeRange>(() => {
    const defaultTimeRange = availableRanges.find(range => range.value === defaultRange)
    return defaultTimeRange || availableRanges[5] // Default to 24h
  })
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [refreshCallbacks, setRefreshCallbacks] = useState<Set<(newTimeRange: TimeRange) => void | Promise<void>>>(new Set())
  const [autoRefreshInterval, setAutoRefreshIntervalState] = useState<AutoRefreshInterval>(AUTO_REFRESH_INTERVALS[0]) // Off by default
  const [autoRefreshIntervals] = useState<AutoRefreshInterval[]>(AUTO_REFRESH_INTERVALS)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  // Auto-refresh with sliding window - slides the time window forward at the specified interval
  useEffect(() => {
    // If auto-refresh is off or no interval, do nothing
    if (autoRefreshInterval.ms === 0) {
      console.log('🔄 Auto-refresh: OFF')
      return
    }

    console.log(`🔄 Auto-refresh: Starting with interval ${autoRefreshInterval.label} (${autoRefreshInterval.ms}ms)`)

    const intervalId = setInterval(() => {
      console.log('🔄 Auto-refresh: Triggering refresh...')
      setIsRefreshing(true)

      // Slide the time window forward
      if (!currentTimeRange.isCustom) {
        // For preset ranges, recalculate based on current time
        const updatedRanges = createTimeRanges()
        const updatedCurrent = updatedRanges.find(range => range.value === currentTimeRange.value)
        if (updatedCurrent) {
          console.log('🔄 Auto-refresh: Sliding time window', {
            from: currentTimeRange.startTime.toISOString(),
            to: updatedCurrent.startTime.toISOString()
          })
          setCurrentTimeRange(updatedCurrent)
          setLastRefresh(new Date())
          setRefreshTrigger(prev => prev + 1) // Increment trigger to notify components
        }
      } else {
        // For custom ranges, slide by the auto-refresh interval
        const slideDuration = currentTimeRange.endTime.getTime() - currentTimeRange.startTime.getTime()
        const now = new Date()
        const newRange: TimeRange = {
          ...currentTimeRange,
          startTime: new Date(now.getTime() - slideDuration),
          endTime: now,
          description: `${new Date(now.getTime() - slideDuration).toLocaleString()} - ${now.toLocaleString()}`
        }
        console.log('🔄 Auto-refresh: Sliding custom time window', {
          from: currentTimeRange.startTime.toISOString(),
          to: newRange.startTime.toISOString()
        })
        setCurrentTimeRange(newRange)
        setLastRefresh(new Date())
        setRefreshTrigger(prev => prev + 1) // Increment trigger to notify components
      }

      setTimeout(() => setIsRefreshing(false), 300)
    }, autoRefreshInterval.ms)

    return () => {
      console.log('🔄 Auto-refresh: Clearing interval')
      clearInterval(intervalId)
    }
  }, [autoRefreshInterval.ms, currentTimeRange.value, currentTimeRange.isCustom])

  const setTimeRange = useCallback((timeRange: TimeRange) => {
    setCurrentTimeRange(timeRange)
    setLastRefresh(new Date())
    
    // Trigger all registered refresh callbacks with the NEW time range
    Array.from(refreshCallbacks).forEach(callback => {
      try {
        const result = callback(timeRange)
        if (result instanceof Promise) {
          result.catch(console.error)
        }
      } catch (error) {
        console.error('Error in refresh callback:', error)
      }
    })
  }, [refreshCallbacks])

  const refreshData = useCallback(async () => {
    setIsRefreshing(true)
    setLastRefresh(new Date())
    
    // Small delay to show refresh animation
    setTimeout(() => {
      setIsRefreshing(false)
    }, 500)
  }, [])

  const getApiTimeRange = useCallback(() => {
    return {
      start_time: currentTimeRange.startTime.toISOString(),
      end_time: currentTimeRange.endTime.toISOString(),
      time_range: currentTimeRange.value
    }
  }, [currentTimeRange])

  const createCustomRange = useCallback((start: Date, end: Date): TimeRange => {
    const duration = end.getTime() - start.getTime()
    const hours = Math.round(duration / (1000 * 60 * 60))
    const days = Math.round(duration / (1000 * 60 * 60 * 24))
    
    let label = 'Custom Range'
    if (days > 1) {
      label = `${days} days`
    } else if (hours > 1) {
      label = `${hours} hours`
    } else {
      label = `${Math.round(duration / (1000 * 60))} minutes`
    }

    return {
      label,
      value: 'custom',
      startTime: start,
      endTime: end,
      isCustom: true,
      description: `${start.toLocaleDateString()} - ${end.toLocaleDateString()}`
    }
  }, [])

  // Centralized auto-refresh functionality
  const useAutoRefresh = useCallback((refreshFn: (newTimeRange: TimeRange) => void | Promise<void>, dependencies: any[] = []) => {
    useEffect(() => {
      // Register this refresh function
      setRefreshCallbacks(prev => new Set([...Array.from(prev), refreshFn]))

      // Cleanup: unregister when component unmounts or dependencies change
      return () => {
        setRefreshCallbacks(prev => {
          const newSet = new Set(prev)
          newSet.delete(refreshFn)
          return newSet
        })
      }
    }, dependencies) // eslint-disable-line react-hooks/exhaustive-deps
  }, [])

  // Set auto-refresh interval
  const setAutoRefreshInterval = useCallback((interval: AutoRefreshInterval) => {
    setAutoRefreshIntervalState(interval)
  }, [])

  // Set custom auto-refresh interval in seconds
  const setCustomAutoRefreshInterval = useCallback((seconds: number) => {
    if (seconds <= 0) {
      setAutoRefreshIntervalState(AUTO_REFRESH_INTERVALS[0]) // Off
      return
    }

    // Format label based on duration
    let label: string
    if (seconds < 60) {
      label = `${seconds} seconds`
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60)
      label = `${minutes} minute${minutes > 1 ? 's' : ''}`
    } else {
      const hours = Math.floor(seconds / 3600)
      label = `${hours} hour${hours > 1 ? 's' : ''}`
    }

    const customInterval: AutoRefreshInterval = {
      label: `Custom (${label})`,
      value: 'custom',
      ms: seconds * 1000
    }

    setAutoRefreshIntervalState(customInterval)
  }, [])

  const value: TimeRangeContextType = {
    currentTimeRange,
    setTimeRange,
    refreshData,
    lastRefresh,
    isRefreshing,
    availableRanges,
    getApiTimeRange,
    createCustomRange,
    useAutoRefresh,
    autoRefreshInterval,
    setAutoRefreshInterval,
    autoRefreshIntervals,
    setCustomAutoRefreshInterval,
    refreshTrigger
  }

  return (
    <TimeRangeContext.Provider value={value}>
      {children}
    </TimeRangeContext.Provider>
  )
}

export const useTimeRange = (): TimeRangeContextType => {
  const context = useContext(TimeRangeContext)
  if (context === undefined) {
    throw new Error('useTimeRange must be used within a TimeRangeProvider')
  }
  return context
}

export default TimeRangeProvider