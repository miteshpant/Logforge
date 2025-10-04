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

  // Update time ranges every minute to keep "now" current
  useEffect(() => {
    const interval = setInterval(() => {
      if (!currentTimeRange.isCustom) {
        const updatedRanges = createTimeRanges()
        const updatedCurrent = updatedRanges.find(range => range.value === currentTimeRange.value)
        if (updatedCurrent) {
          setCurrentTimeRange(updatedCurrent)
        }
      }
    }, 60000) // Update every minute

    return () => clearInterval(interval)
  }, [currentTimeRange])

  const setTimeRange = useCallback((timeRange: TimeRange) => {
    setCurrentTimeRange(timeRange)
    setLastRefresh(new Date())
    
    // Trigger all registered refresh callbacks with the NEW time range
    refreshCallbacks.forEach(callback => {
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
      setRefreshCallbacks(prev => new Set([...prev, refreshFn]))
      
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

  const value: TimeRangeContextType = {
    currentTimeRange,
    setTimeRange,
    refreshData,
    lastRefresh,
    isRefreshing,
    availableRanges,
    getApiTimeRange,
    createCustomRange,
    useAutoRefresh
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