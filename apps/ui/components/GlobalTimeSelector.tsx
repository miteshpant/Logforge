'use client'

import React, { useState, useRef, useEffect } from 'react'
import { useTimeRange, TimeRange } from '@/contexts/TimeRangeContext'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import {
  Calendar,
  Clock,
  RefreshCw,
  ChevronDown,
  CheckCircle,
  Zap,
  Activity,
  BarChart3,
  Timer,
  ArrowRight
} from 'lucide-react'

interface GlobalTimeSelectorProps {
  className?: string
  variant?: 'compact' | 'full'
  showRefresh?: boolean
  showLastUpdate?: boolean
}

const GlobalTimeSelector: React.FC<GlobalTimeSelectorProps> = ({
  className = '',
  variant = 'full',
  showRefresh = true,
  showLastUpdate = true
}) => {
  const {
    currentTimeRange,
    setTimeRange,
    refreshData,
    lastRefresh,
    isRefreshing,
    availableRanges
  } = useTimeRange()

  const [isOpen, setIsOpen] = useState(false)
  const [showCustomPicker, setShowCustomPicker] = useState(false)
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
        setShowCustomPicker(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleTimeRangeSelect = (range: TimeRange) => {
    setTimeRange(range)
    setIsOpen(false)
    setShowCustomPicker(false)
  }

  const handleCustomRangeSubmit = () => {
    if (customStart && customEnd) {
      const start = new Date(customStart)
      const end = new Date(customEnd)

      if (start < end) {
        const customRange: TimeRange = {
          label: 'Custom Range',
          value: 'custom',
          startTime: start,
          endTime: end,
          isCustom: true,
          description: `${start.toLocaleDateString()} - ${end.toLocaleDateString()}`
        }
        handleTimeRangeSelect(customRange)
      }
    }
  }

  const getRangeIcon = (value: string) => {
    if (value.includes('m')) return <Zap className="w-4 h-4" />
    if (value.includes('h')) return <Activity className="w-4 h-4" />
    if (value.includes('d')) return <BarChart3 className="w-4 h-4" />
    return <Timer className="w-4 h-4" />
  }

  const formatLastUpdate = (date: Date) => {
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const seconds = Math.floor(diff / 1000)
    const minutes = Math.floor(seconds / 60)

    if (seconds < 60) return `${seconds}s ago`
    if (minutes < 60) return `${minutes}m ago`
    return date.toLocaleTimeString()
  }

  if (variant === 'compact') {
    return (
      <div className={`relative ${className}`} ref={dropdownRef} data-testid="time-range-selector">
        <Button
          variant="outline"
          onClick={() => setIsOpen(!isOpen)}
          className="h-9 px-3 bg-white/95 backdrop-blur-sm border-slate-200/60 hover:bg-slate-50/80 hover:border-slate-300/80 transition-all duration-200"
          data-testid="time-range-button"
        >
          <Clock className="w-4 h-4 mr-2 text-slate-600" />
          <span className="font-medium text-slate-700" data-testid="current-time-range">{currentTimeRange.label}</span>
          <ChevronDown className={`w-4 h-4 ml-2 text-slate-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
        </Button>

        {isOpen && (
          <Card className="absolute top-full right-0 mt-16 w-80 shadow-xl border-0 bg-white/95 backdrop-blur-md z-50 animate-in slide-in-from-top-2 duration-200">
            <CardContent className="p-3">
              {!showCustomPicker ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-semibold text-slate-900 text-sm">Select Time Range</h3>
                  </div>

                  <div className="space-y-1">
                    {availableRanges.map((range) => (
                      <button
                        key={range.value}
                        onClick={() => handleTimeRangeSelect(range)}
                        className={`w-full flex items-center justify-between p-2 rounded-lg transition-all duration-150 ${
                          currentTimeRange.value === range.value
                            ? 'bg-blue-500 text-white shadow-sm'
                            : 'hover:bg-slate-100 text-slate-700'
                        }`}
                        data-testid={`time-range-${range.value}`}
                      >
                        <div className="flex items-center space-x-2">
                          {getRangeIcon(range.value)}
                          <span className="font-medium text-sm">{range.label}</span>
                        </div>
                        {currentTimeRange.value === range.value && (
                          <CheckCircle className="w-4 h-4" />
                        )}
                      </button>
                    ))}
                  </div>

                  {/* Custom Range Button */}
                  <div className="pt-2 border-t border-slate-200">
                    <Button
                      variant="outline"
                      onClick={() => setShowCustomPicker(true)}
                      className="w-full justify-between text-sm hover:bg-slate-50"
                      data-testid="custom-range-button"
                    >
                      <div className="flex items-center space-x-2">
                        <Calendar className="w-4 h-4" />
                        <span>Custom Date Range</span>
                      </div>
                      <ArrowRight className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-slate-900 text-sm">Custom Range</h3>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowCustomPicker(false)}
                      className="text-slate-500 hover:text-slate-700 h-auto py-1"
                    >
                      Back
                    </Button>
                  </div>

                  <div className="space-y-2">
                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1">Start Date & Time</label>
                      <input
                        type="datetime-local"
                        value={customStart}
                        onChange={(e) => setCustomStart(e.target.value)}
                        className="w-full px-2 py-1.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        data-testid="custom-start-input"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1">End Date & Time</label>
                      <input
                        type="datetime-local"
                        value={customEnd}
                        onChange={(e) => setCustomEnd(e.target.value)}
                        className="w-full px-2 py-1.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        data-testid="custom-end-input"
                      />
                    </div>

                    <Button
                      onClick={handleCustomRangeSubmit}
                      disabled={!customStart || !customEnd}
                      className="w-full bg-blue-500 hover:bg-blue-600 text-white text-sm py-2 rounded-lg"
                      data-testid="apply-custom-range"
                    >
                      Apply Custom Range
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    )
  }

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      <div className="flex items-center space-x-3 bg-gradient-to-r from-white/90 to-slate-50/90 backdrop-blur-md rounded-xl border border-slate-200/60 shadow-sm p-3">

        {/* Time Range Button */}
        <Button
          variant="ghost"
          onClick={() => setIsOpen(!isOpen)}
          className="h-auto p-3 bg-white/80 hover:bg-white/90 border border-slate-200/80 hover:border-slate-300/80 rounded-lg transition-all duration-200 group"
        >
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <div className="p-1.5 rounded-md bg-gradient-to-br from-blue-500 to-blue-600 text-white">
                <Calendar className="w-4 h-4" />
              </div>
              <div className="text-left">
                <div className="font-semibold text-slate-900 text-sm">{currentTimeRange.label}</div>
                {currentTimeRange.description && (
                  <div className="text-xs text-slate-500">{currentTimeRange.description}</div>
                )}
              </div>
            </div>
            <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 group-hover:text-slate-600 ${isOpen ? 'rotate-180' : ''}`} />
          </div>
        </Button>

        {/* Live Status Indicator */}
        <div className="flex items-center space-x-2 px-3 py-2 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border border-green-200/60">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <span className="text-xs font-medium text-green-700">Live Data</span>
        </div>

        {/* Refresh Button */}
        {showRefresh && (
          <Button
            variant="ghost"
            size="sm"
            onClick={refreshData}
            disabled={isRefreshing}
            className="h-auto p-2.5 bg-white/80 hover:bg-white/90 border border-slate-200/80 hover:border-slate-300/80 rounded-lg transition-all duration-200"
          >
            <RefreshCw className={`w-4 h-4 text-slate-600 ${isRefreshing ? 'animate-spin' : ''}`} />
          </Button>
        )}

        {/* Last Update */}
        {showLastUpdate && (
          <div className="flex items-center space-x-2 text-xs text-slate-500">
            <Clock className="w-3 h-3" />
            <span>Updated {formatLastUpdate(lastRefresh)}</span>
          </div>
        )}
      </div>

      {/* Dropdown Menu */}
      {isOpen && (
        <Card className="absolute top-full left-0 mt-2 w-full max-w-md shadow-2xl border-0 bg-white/95 backdrop-blur-xl z-50 animate-in slide-in-from-top-2 duration-300">
          <CardContent className="p-4">
            {!showCustomPicker ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-slate-900">Select Time Range</h3>
                  <Badge variant="outline" className="text-xs">
                    {availableRanges.length} presets
                  </Badge>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  {availableRanges.map((range) => (
                    <button
                      key={range.value}
                      onClick={() => handleTimeRangeSelect(range)}
                      className={`group p-3 rounded-lg border-2 transition-all duration-200 text-left ${
                        currentTimeRange.value === range.value
                          ? 'border-blue-500 bg-blue-50 shadow-sm'
                          : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center space-x-2">
                          {getRangeIcon(range.value)}
                          <span className="font-medium text-slate-900 text-sm">{range.label}</span>
                        </div>
                        {currentTimeRange.value === range.value && (
                          <CheckCircle className="w-4 h-4 text-blue-500" />
                        )}
                      </div>
                      {range.description && (
                        <p className="text-xs text-slate-500">{range.description}</p>
                      )}
                    </button>
                  ))}
                </div>

                <div className="pt-3 border-t border-slate-200">
                  <Button
                    variant="outline"
                    onClick={() => setShowCustomPicker(true)}
                    className="w-full justify-between group hover:bg-gradient-to-r hover:from-slate-50 hover:to-slate-100"
                  >
                    <div className="flex items-center space-x-2">
                      <Calendar className="w-4 h-4" />
                      <span>Custom Date Range</span>
                    </div>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-slate-900">Custom Range</h3>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowCustomPicker(false)}
                    className="text-slate-500 hover:text-slate-700"
                  >
                    Back
                  </Button>
                </div>

                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Start Date & Time</label>
                    <input
                      type="datetime-local"
                      value={customStart}
                      onChange={(e) => setCustomStart(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">End Date & Time</label>
                    <input
                      type="datetime-local"
                      value={customEnd}
                      onChange={(e) => setCustomEnd(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                    />
                  </div>

                  <Button
                    onClick={handleCustomRangeSubmit}
                    disabled={!customStart || !customEnd}
                    className="w-full bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white font-medium py-2 rounded-lg transition-all duration-200"
                  >
                    Apply Custom Range
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default GlobalTimeSelector
