'use client'

import React, { useState, useRef, useEffect } from 'react'
import { useTimeRange, TimeRange, AutoRefreshInterval } from '@/contexts/TimeRangeContext'
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
  ArrowRight,
  Play,
  Pause,
  Settings
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
    availableRanges,
    autoRefreshInterval,
    setAutoRefreshInterval,
    autoRefreshIntervals,
    setCustomAutoRefreshInterval
  } = useTimeRange()

  const [isOpen, setIsOpen] = useState(false)
  const [showCustomPicker, setShowCustomPicker] = useState(false)
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')
  const [isAutoRefreshOpen, setIsAutoRefreshOpen] = useState(false)
  const [showCustomIntervalInput, setShowCustomIntervalInput] = useState(false)
  const [customIntervalValue, setCustomIntervalValue] = useState('')
  const [customIntervalUnit, setCustomIntervalUnit] = useState<'s' | 'm' | 'h'>('s')
  const dropdownRef = useRef<HTMLDivElement>(null)
  const autoRefreshRef = useRef<HTMLDivElement>(null)

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
        setShowCustomPicker(false)
      }
      if (autoRefreshRef.current && !autoRefreshRef.current.contains(event.target as Node)) {
        setIsAutoRefreshOpen(false)
        setShowCustomIntervalInput(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleAutoRefreshSelect = (interval: AutoRefreshInterval) => {
    setAutoRefreshInterval(interval)
    setIsAutoRefreshOpen(false)
    setShowCustomIntervalInput(false)
  }

  const handleCustomIntervalSubmit = () => {
    const value = parseInt(customIntervalValue, 10)
    if (isNaN(value) || value <= 0) return

    let seconds = value
    if (customIntervalUnit === 'm') seconds = value * 60
    if (customIntervalUnit === 'h') seconds = value * 3600

    setCustomAutoRefreshInterval(seconds)
    setIsAutoRefreshOpen(false)
    setShowCustomIntervalInput(false)
    setCustomIntervalValue('')
  }

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
      <div className={`flex items-center gap-2 ${className}`} data-testid="time-range-selector">
        {/* Time Range Button */}
        <div className="relative" ref={dropdownRef}>
          <Button
            variant="outline"
            onClick={() => setIsOpen(!isOpen)}
            className="h-9 px-3 bg-slate-800/80 backdrop-blur-sm border-white/10 hover:bg-slate-700/80 hover:border-white/20 transition-all duration-200"
            data-testid="time-range-button"
          >
            <Clock className="w-4 h-4 mr-2 text-slate-400" />
            <span className="font-medium text-slate-300" data-testid="current-time-range">{currentTimeRange.label}</span>
            <ChevronDown className={`w-4 h-4 ml-2 text-slate-500 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
          </Button>

          {isOpen && (
          <Card className="absolute top-full right-0 mt-2 w-80 shadow-xl border-white/10 bg-slate-800/95 backdrop-blur-md z-50 animate-in slide-in-from-top-2 duration-200">
            <CardContent className="p-3">
              {!showCustomPicker ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-semibold text-white text-sm">Select Time Range</h3>
                  </div>

                  <div className="space-y-1">
                    {availableRanges.map((range) => (
                      <button
                        key={range.value}
                        onClick={() => handleTimeRangeSelect(range)}
                        className={`w-full flex items-center justify-between p-2 rounded-lg transition-all duration-150 ${
                          currentTimeRange.value === range.value
                            ? 'bg-blue-500/20 text-blue-400 shadow-sm'
                            : 'hover:bg-white/5 text-slate-300'
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
                  <div className="pt-2 border-t border-white/10">
                    <Button
                      variant="outline"
                      onClick={() => setShowCustomPicker(true)}
                      className="w-full justify-between text-sm hover:bg-white/5"
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
                    <h3 className="font-semibold text-white text-sm">Custom Range</h3>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowCustomPicker(false)}
                      className="text-slate-400 hover:text-white h-auto py-1"
                    >
                      Back
                    </Button>
                  </div>

                  <div className="space-y-2">
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1">Start Date & Time</label>
                      <input
                        type="datetime-local"
                        value={customStart}
                        onChange={(e) => setCustomStart(e.target.value)}
                        className="w-full px-2 py-1.5 text-sm text-white bg-slate-700/50 border border-white/10 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        data-testid="custom-start-input"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1">End Date & Time</label>
                      <input
                        type="datetime-local"
                        value={customEnd}
                        onChange={(e) => setCustomEnd(e.target.value)}
                        className="w-full px-2 py-1.5 text-sm text-white bg-slate-700/50 border border-white/10 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        data-testid="custom-end-input"
                      />
                    </div>

                    <Button
                      onClick={handleCustomRangeSubmit}
                      disabled={!customStart || !customEnd}
                      className="w-full bg-blue-600 hover:bg-blue-700 text-white text-sm py-2 rounded-lg"
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

        {/* Compact Auto-Refresh Button */}
        <div className="relative" ref={autoRefreshRef}>
          <Button
            variant="outline"
            onClick={() => setIsAutoRefreshOpen(!isAutoRefreshOpen)}
            className={`h-9 px-2.5 backdrop-blur-sm border-white/10 transition-all duration-200 ${
              autoRefreshInterval.ms > 0
                ? 'bg-blue-600/20 hover:bg-blue-600/30 border-blue-500/30'
                : 'bg-slate-800/80 hover:bg-slate-700/80 hover:border-white/20'
            }`}
            title={autoRefreshInterval.ms > 0 ? `Auto-refresh: ${autoRefreshInterval.label}` : 'Auto-refresh off'}
          >
            {autoRefreshInterval.ms > 0 ? (
              <Play className="w-4 h-4 text-blue-400" />
            ) : (
              <Pause className="w-4 h-4 text-slate-400" />
            )}
            {autoRefreshInterval.ms > 0 && (
              <span className="ml-1.5 text-xs font-medium text-blue-400">
                {autoRefreshInterval.value === 'custom' ? 'On' : autoRefreshInterval.value}
              </span>
            )}
          </Button>

          {/* Compact Auto-Refresh Dropdown */}
          {isAutoRefreshOpen && (
            <Card className="absolute top-full right-0 mt-2 w-56 shadow-xl border-white/10 bg-slate-800/95 backdrop-blur-md z-50 animate-in slide-in-from-top-2 duration-200">
              <CardContent className="p-2">
                {!showCustomIntervalInput ? (
                  <div className="space-y-1">
                    <div className="px-2 py-1.5 text-xs font-semibold text-slate-400 uppercase tracking-wide">
                      Auto Refresh
                    </div>
                    {autoRefreshIntervals.map((interval) => (
                      <button
                        key={interval.value}
                        onClick={() => handleAutoRefreshSelect(interval)}
                        className={`w-full flex items-center justify-between px-2 py-1.5 rounded-md transition-all duration-150 text-sm ${
                          autoRefreshInterval.value === interval.value
                            ? 'bg-blue-500/20 text-blue-400'
                            : 'hover:bg-white/5 text-slate-300'
                        }`}
                      >
                        <span>{interval.label}</span>
                        {autoRefreshInterval.value === interval.value && (
                          <CheckCircle className="w-3.5 h-3.5" />
                        )}
                      </button>
                    ))}
                    <div className="border-t border-white/10 pt-1 mt-1">
                      <button
                        onClick={() => setShowCustomIntervalInput(true)}
                        className="w-full flex items-center justify-between px-2 py-1.5 rounded-md hover:bg-white/5 text-slate-300 text-sm"
                      >
                        <span>Custom...</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2 p-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-slate-400">Custom Interval</span>
                      <button
                        onClick={() => setShowCustomIntervalInput(false)}
                        className="text-xs text-slate-400 hover:text-white"
                      >
                        Back
                      </button>
                    </div>
                    <div className="flex gap-1.5">
                      <input
                        type="number"
                        min="1"
                        value={customIntervalValue}
                        onChange={(e) => setCustomIntervalValue(e.target.value)}
                        placeholder="15"
                        className="flex-1 px-2 py-1.5 text-sm text-white bg-slate-700/50 border border-white/10 rounded focus:ring-1 focus:ring-blue-500 w-16"
                      />
                      <select
                        value={customIntervalUnit}
                        onChange={(e) => setCustomIntervalUnit(e.target.value as 's' | 'm' | 'h')}
                        className="px-2 py-1.5 text-sm text-white bg-slate-700/50 border border-white/10 rounded focus:ring-1 focus:ring-blue-500"
                      >
                        <option value="s">sec</option>
                        <option value="m">min</option>
                        <option value="h">hr</option>
                      </select>
                    </div>
                    <Button
                      onClick={handleCustomIntervalSubmit}
                      disabled={!customIntervalValue || parseInt(customIntervalValue, 10) <= 0}
                      size="sm"
                      className="w-full bg-blue-600 hover:bg-blue-700 text-white text-xs py-1.5"
                    >
                      Apply
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      <div className="flex items-center space-x-3 bg-slate-800/80 backdrop-blur-md rounded-xl border border-white/10 shadow-sm p-3">

        {/* Time Range Button */}
        <Button
          variant="ghost"
          onClick={() => setIsOpen(!isOpen)}
          className="h-auto p-3 bg-slate-700/50 hover:bg-slate-700/80 border border-white/10 hover:border-white/20 rounded-lg transition-all duration-200 group"
        >
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <div className="p-1.5 rounded-md bg-gradient-to-br from-blue-500 to-blue-600 text-white">
                <Calendar className="w-4 h-4" />
              </div>
              <div className="text-left">
                <div className="font-semibold text-white text-sm">{currentTimeRange.label}</div>
                {currentTimeRange.description && (
                  <div className="text-xs text-slate-400">{currentTimeRange.description}</div>
                )}
              </div>
            </div>
            <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 group-hover:text-slate-300 ${isOpen ? 'rotate-180' : ''}`} />
          </div>
        </Button>

        {/* Live Status Indicator */}
        <div className="flex items-center space-x-2 px-3 py-2 bg-emerald-500/10 rounded-lg border border-emerald-500/20">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <span className="text-xs font-medium text-emerald-400">Live Data</span>
        </div>

        {/* Auto-Refresh Dropdown */}
        <div className="relative" ref={autoRefreshRef}>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsAutoRefreshOpen(!isAutoRefreshOpen)}
            className={`h-auto p-2.5 border border-white/10 rounded-lg transition-all duration-200 flex items-center gap-2 ${
              autoRefreshInterval.ms > 0
                ? 'bg-blue-600/20 hover:bg-blue-600/30 border-blue-500/30'
                : 'bg-slate-700/50 hover:bg-slate-700/80 hover:border-white/20'
            }`}
          >
            {autoRefreshInterval.ms > 0 ? (
              <Play className="w-4 h-4 text-blue-400" />
            ) : (
              <Pause className="w-4 h-4 text-slate-400" />
            )}
            <span className={`text-xs font-medium ${autoRefreshInterval.ms > 0 ? 'text-blue-400' : 'text-slate-400'}`}>
              {autoRefreshInterval.ms > 0 ? autoRefreshInterval.label.replace('seconds', 's').replace('minutes', 'm').replace('minute', 'm').replace('hour', 'h') : 'Auto'}
            </span>
            <ChevronDown className={`w-3 h-3 text-slate-400 transition-transform ${isAutoRefreshOpen ? 'rotate-180' : ''}`} />
          </Button>

          {/* Auto-Refresh Dropdown Menu */}
          {isAutoRefreshOpen && (
            <Card className="absolute top-full right-0 mt-2 w-64 shadow-xl border-white/10 bg-slate-800/95 backdrop-blur-md z-50 animate-in slide-in-from-top-2 duration-200">
              <CardContent className="p-3">
                {!showCustomIntervalInput ? (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="font-semibold text-white text-sm">Auto Refresh</h3>
                      {autoRefreshInterval.ms > 0 && (
                        <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30 text-[10px]">
                          Active
                        </Badge>
                      )}
                    </div>

                    <div className="space-y-1">
                      {autoRefreshIntervals.map((interval) => (
                        <button
                          key={interval.value}
                          onClick={() => handleAutoRefreshSelect(interval)}
                          className={`w-full flex items-center justify-between p-2 rounded-lg transition-all duration-150 ${
                            autoRefreshInterval.value === interval.value
                              ? 'bg-blue-500/20 text-blue-400 shadow-sm'
                              : 'hover:bg-white/5 text-slate-300'
                          }`}
                        >
                          <div className="flex items-center space-x-2">
                            {interval.ms === 0 ? (
                              <Pause className="w-4 h-4" />
                            ) : (
                              <RefreshCw className="w-4 h-4" />
                            )}
                            <span className="font-medium text-sm">{interval.label}</span>
                          </div>
                          {autoRefreshInterval.value === interval.value && (
                            <CheckCircle className="w-4 h-4" />
                          )}
                        </button>
                      ))}
                    </div>

                    {/* Custom Interval Button */}
                    <div className="pt-2 border-t border-white/10">
                      <Button
                        variant="outline"
                        onClick={() => setShowCustomIntervalInput(true)}
                        className="w-full justify-between text-sm hover:bg-white/5"
                      >
                        <div className="flex items-center space-x-2">
                          <Settings className="w-4 h-4" />
                          <span>Custom Interval</span>
                        </div>
                        <ArrowRight className="w-4 h-4" />
                      </Button>
                    </div>

                    {/* Info text */}
                    <p className="text-[10px] text-slate-500 pt-2 text-center">
                      Time window slides forward with each refresh
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="font-semibold text-white text-sm">Custom Interval</h3>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowCustomIntervalInput(false)}
                        className="text-slate-400 hover:text-white h-auto py-1 text-xs"
                      >
                        Back
                      </Button>
                    </div>

                    <div className="flex gap-2">
                      <input
                        type="number"
                        min="1"
                        value={customIntervalValue}
                        onChange={(e) => setCustomIntervalValue(e.target.value)}
                        placeholder="Value"
                        className="flex-1 px-3 py-2 text-sm text-white bg-slate-700/50 border border-white/10 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      />
                      <select
                        value={customIntervalUnit}
                        onChange={(e) => setCustomIntervalUnit(e.target.value as 's' | 'm' | 'h')}
                        className="px-3 py-2 text-sm text-white bg-slate-700/50 border border-white/10 rounded-lg focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="s">sec</option>
                        <option value="m">min</option>
                        <option value="h">hour</option>
                      </select>
                    </div>

                    <Button
                      onClick={handleCustomIntervalSubmit}
                      disabled={!customIntervalValue || parseInt(customIntervalValue, 10) <= 0}
                      className="w-full bg-blue-600 hover:bg-blue-700 text-white text-sm py-2 rounded-lg"
                    >
                      Apply Custom Interval
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Refresh Button */}
        {showRefresh && (
          <Button
            variant="ghost"
            size="sm"
            onClick={refreshData}
            disabled={isRefreshing}
            className="h-auto p-2.5 bg-slate-700/50 hover:bg-slate-700/80 border border-white/10 hover:border-white/20 rounded-lg transition-all duration-200"
            title="Refresh now"
          >
            <RefreshCw className={`w-4 h-4 text-slate-400 ${isRefreshing ? 'animate-spin' : ''}`} />
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
        <Card className="absolute top-full left-0 mt-2 w-full max-w-md shadow-2xl border-white/10 bg-slate-800/95 backdrop-blur-xl z-50 animate-in slide-in-from-top-2 duration-300">
          <CardContent className="p-4">
            {!showCustomPicker ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-white">Select Time Range</h3>
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
                          ? 'border-blue-500/50 bg-blue-500/10 shadow-sm'
                          : 'border-white/5 hover:border-white/10 hover:bg-white/5'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center space-x-2">
                          {getRangeIcon(range.value)}
                          <span className="font-medium text-white text-sm">{range.label}</span>
                        </div>
                        {currentTimeRange.value === range.value && (
                          <CheckCircle className="w-4 h-4 text-blue-500" />
                        )}
                      </div>
                      {range.description && (
                        <p className="text-xs text-slate-400">{range.description}</p>
                      )}
                    </button>
                  ))}
                </div>

                <div className="pt-3 border-t border-white/10">
                  <Button
                    variant="outline"
                    onClick={() => setShowCustomPicker(true)}
                    className="w-full justify-between group hover:bg-white/5"
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
                  <h3 className="font-semibold text-white">Custom Range</h3>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowCustomPicker(false)}
                    className="text-slate-400 hover:text-white"
                  >
                    Back
                  </Button>
                </div>

                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-slate-400 mb-1">Start Date & Time</label>
                    <input
                      type="datetime-local"
                      value={customStart}
                      onChange={(e) => setCustomStart(e.target.value)}
                      className="w-full px-3 py-2 text-white bg-slate-700/50 border border-white/10 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-400 mb-1">End Date & Time</label>
                    <input
                      type="datetime-local"
                      value={customEnd}
                      onChange={(e) => setCustomEnd(e.target.value)}
                      className="w-full px-3 py-2 text-white bg-slate-700/50 border border-white/10 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                    />
                  </div>

                  <Button
                    onClick={handleCustomRangeSubmit}
                    disabled={!customStart || !customEnd}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 rounded-lg transition-all duration-200"
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
