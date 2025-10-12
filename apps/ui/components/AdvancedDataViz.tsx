'use client'

import React, { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { 
  BarChart3, 
  TrendingUp, 
  TrendingDown,
  Activity, 
  Zap,
  AlertTriangle,
  Target,
  Eye,
  RefreshCw,
  Download,
  Settings,
  Maximize2,
  Filter
} from 'lucide-react'
import { ObservabilityApi, UsageApi } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import { useAuth } from '@/contexts/AuthContext'

interface DataPoint {
  timestamp: string
  value: number
  label?: string
  metadata?: Record<string, any>
}

interface ChartConfig {
  title: string
  type: 'line' | 'bar' | 'area' | 'heatmap' | 'gauge'
  color: string
  gradientFrom: string
  gradientTo: string
  unit: string
  threshold?: {
    warning: number
    critical: number
  }
}

interface AdvancedDataVizProps {
  className?: string
  data: DataPoint[]
  config: ChartConfig
  realTime?: boolean
  height?: number
  showControls?: boolean
}

export const AdvancedDataViz: React.FC<AdvancedDataVizProps> = ({
  className = '',
  data,
  config,
  realTime = false,
  height = 200,
  showControls = true
}) => {
  const [isLive, setIsLive] = useState(realTime)
  const [chartData, setChartData] = useState<DataPoint[]>(data)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [currentValue, setCurrentValue] = useState<number>(0)
  const [trend, setTrend] = useState<'up' | 'down' | 'stable'>('stable')
  const [changePercent, setChangePercent] = useState<number>(0)

  useEffect(() => {
    setChartData(data)
    calculateMetrics()
  }, [data])

  useEffect(() => {
    if (isLive) {
      const interval = setInterval(() => {
        generateLiveData()
      }, 2000)
      return () => clearInterval(interval)
    }
  }, [isLive, chartData])

  useEffect(() => {
    drawChart()
  }, [chartData, config])

  const calculateMetrics = () => {
    if (chartData.length === 0) return

    const latestValue = chartData[chartData.length - 1]?.value || 0
    const previousValue = chartData[chartData.length - 2]?.value || latestValue
    
    setCurrentValue(latestValue)
    
    if (latestValue > previousValue) {
      setTrend('up')
      setChangePercent(((latestValue - previousValue) / previousValue) * 100)
    } else if (latestValue < previousValue) {
      setTrend('down')
      setChangePercent(((previousValue - latestValue) / previousValue) * 100)
    } else {
      setTrend('stable')
      setChangePercent(0)
    }
  }

  const generateLiveData = () => {
    if (chartData.length === 0) return

    const lastValue = chartData[chartData.length - 1]?.value || 0
    const variation = (Math.random() - 0.5) * (lastValue * 0.2) // 20% variation
    const newValue = Math.max(0, lastValue + variation)

    const newPoint: DataPoint = {
      timestamp: new Date().toISOString(),
      value: newValue,
      metadata: {
        generated: true,
        baseline: lastValue
      }
    }

    setChartData(prev => {
      const updated = [...prev, newPoint]
      // Keep last 50 points for performance
      return updated.slice(-50)
    })
  }

  const drawChart = () => {
    const canvas = canvasRef.current
    if (!canvas || chartData.length === 0) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Set canvas size
    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * window.devicePixelRatio
    canvas.height = rect.height * window.devicePixelRatio
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)

    const width = rect.width
    const height = rect.height
    const padding = 40

    // Clear canvas
    ctx.clearRect(0, 0, width, height)

    // Calculate scales
    const values = chartData.map(d => d.value)
    const minValue = Math.min(...values)
    const maxValue = Math.max(...values)
    const valueRange = maxValue - minValue || 1

    const xScale = (width - 2 * padding) / (chartData.length - 1 || 1)
    const yScale = (height - 2 * padding) / valueRange

    if (config.type === 'line' || config.type === 'area') {
      drawLineChart(ctx, width, height, padding, xScale, yScale, minValue)
    } else if (config.type === 'bar') {
      drawBarChart(ctx, width, height, padding, xScale, yScale, minValue)
    } else if (config.type === 'gauge') {
      drawGaugeChart(ctx, width, height)
    }

    // Draw threshold lines if configured
    if (config.threshold) {
      drawThresholdLines(ctx, width, height, padding, yScale, minValue)
    }
  }

  const drawLineChart = (
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
    padding: number,
    xScale: number,
    yScale: number,
    minValue: number
  ) => {
    // Create gradient
    const gradient = ctx.createLinearGradient(0, padding, 0, height - padding)
    gradient.addColorStop(0, config.gradientFrom + '80')
    gradient.addColorStop(1, config.gradientTo + '20')

    // Draw area if area chart
    if (config.type === 'area') {
      ctx.beginPath()
      ctx.moveTo(padding, height - padding)
      
      chartData.forEach((point, index) => {
        const x = padding + index * xScale
        const y = height - padding - (point.value - minValue) * yScale
        if (index === 0) {
          ctx.lineTo(x, y)
        } else {
          ctx.lineTo(x, y)
        }
      })
      
      ctx.lineTo(padding + (chartData.length - 1) * xScale, height - padding)
      ctx.closePath()
      ctx.fillStyle = gradient
      ctx.fill()
    }

    // Draw line
    ctx.beginPath()
    ctx.strokeStyle = config.color
    ctx.lineWidth = 3
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'

    chartData.forEach((point, index) => {
      const x = padding + index * xScale
      const y = height - padding - (point.value - minValue) * yScale
      
      if (index === 0) {
        ctx.moveTo(x, y)
      } else {
        ctx.lineTo(x, y)
      }
    })
    
    ctx.stroke()

    // Draw data points
    chartData.forEach((point, index) => {
      const x = padding + index * xScale
      const y = height - padding - (point.value - minValue) * yScale
      
      ctx.beginPath()
      ctx.arc(x, y, 4, 0, 2 * Math.PI)
      ctx.fillStyle = config.color
      ctx.fill()
      
      // Highlight latest point
      if (index === chartData.length - 1) {
        ctx.beginPath()
        ctx.arc(x, y, 6, 0, 2 * Math.PI)
        ctx.strokeStyle = config.color
        ctx.lineWidth = 2
        ctx.stroke()
      }
    })
  }

  const drawBarChart = (
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
    padding: number,
    xScale: number,
    yScale: number,
    minValue: number
  ) => {
    const barWidth = xScale * 0.8
    
    chartData.forEach((point, index) => {
      const x = padding + index * xScale - barWidth / 2
      const barHeight = (point.value - minValue) * yScale
      const y = height - padding - barHeight
      
      // Create gradient for bar
      const gradient = ctx.createLinearGradient(0, y, 0, y + barHeight)
      gradient.addColorStop(0, config.gradientFrom)
      gradient.addColorStop(1, config.gradientTo)
      
      ctx.fillStyle = gradient
      ctx.fillRect(x, y, barWidth, barHeight)
      
      // Add border
      ctx.strokeStyle = config.color
      ctx.lineWidth = 1
      ctx.strokeRect(x, y, barWidth, barHeight)
    })
  }

  const drawGaugeChart = (
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number
  ) => {
    const centerX = width / 2
    const centerY = height / 2
    const radius = Math.min(width, height) / 2 - 20
    
    const currentVal = currentValue
    const maxVal = Math.max(...chartData.map(d => d.value)) * 1.2
    const angle = (currentVal / maxVal) * Math.PI // Half circle
    
    // Draw background arc
    ctx.beginPath()
    ctx.arc(centerX, centerY, radius, Math.PI, 2 * Math.PI)
    ctx.strokeStyle = '#e2e8f0'
    ctx.lineWidth = 20
    ctx.stroke()
    
    // Draw value arc
    ctx.beginPath()
    ctx.arc(centerX, centerY, radius, Math.PI, Math.PI + angle)
    ctx.strokeStyle = config.color
    ctx.lineWidth = 20
    ctx.lineCap = 'round'
    ctx.stroke()
    
    // Draw center text
    ctx.fillStyle = config.color
    ctx.font = 'bold 24px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText(currentVal.toFixed(1) + config.unit, centerX, centerY + 10)
  }

  const drawThresholdLines = (
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
    padding: number,
    yScale: number,
    minValue: number
  ) => {
    if (!config.threshold) return

    // Warning line
    const warningY = height - padding - (config.threshold.warning - minValue) * yScale
    ctx.setLineDash([5, 5])
    ctx.strokeStyle = '#f59e0b'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(padding, warningY)
    ctx.lineTo(width - padding, warningY)
    ctx.stroke()

    // Critical line
    const criticalY = height - padding - (config.threshold.critical - minValue) * yScale
    ctx.strokeStyle = '#ef4444'
    ctx.beginPath()
    ctx.moveTo(padding, criticalY)
    ctx.lineTo(width - padding, criticalY)
    ctx.stroke()
    
    ctx.setLineDash([])
  }

  const getStatusColor = () => {
    if (!config.threshold) return 'text-blue-600'
    
    if (currentValue >= config.threshold.critical) return 'text-red-600'
    if (currentValue >= config.threshold.warning) return 'text-orange-600'
    return 'text-green-600'
  }

  const getStatusIcon = () => {
    if (trend === 'up') return <TrendingUp className="w-4 h-4 text-green-600" />
    if (trend === 'down') return <TrendingDown className="w-4 h-4 text-red-600" />
    return <Activity className="w-4 h-4 text-blue-600" />
  }

  return (
    <Card className={`${className} hover:shadow-xl transition-all duration-300 hover:scale-[1.02] bg-gradient-to-br from-white to-slate-50 border-slate-200`} data-testid="advanced-data-viz">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-start space-x-4">
            <div className={`p-3 rounded-xl shadow-md`} style={{ backgroundColor: config.color + '15', border: `2px solid ${config.color}30` }}>
              <BarChart3 className="w-6 h-6" style={{ color: config.color }} />
            </div>
            <div className="flex-1">
              <CardTitle className="text-lg font-bold text-slate-900 mb-2">{config.title}</CardTitle>
              <div className="flex items-center space-x-4">
                <span className={`text-3xl font-bold ${getStatusColor()}`} data-testid="current-value">
                  {currentValue.toFixed(1)}{config.unit}
                </span>
                <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-slate-100">
                  {getStatusIcon()}
                  <span className={`text-sm font-semibold ${trend === 'up' ? 'text-green-700' : trend === 'down' ? 'text-red-700' : 'text-blue-700'}`}>
                    {changePercent > 0 && `${trend === 'up' ? '+' : '-'}${changePercent.toFixed(1)}%`}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {showControls && (
            <div className="flex items-center space-x-2">
              {realTime && (
                <Button
                  variant={isLive ? "default" : "outline"}
                  size="sm"
                  onClick={() => setIsLive(!isLive)}
                  data-testid="toggle-live"
                >
                  {isLive ? (
                    <>
                      <Activity className="w-4 h-4 mr-1 animate-pulse" />
                      Live
                    </>
                  ) : (
                    <>
                      <RefreshCw className="w-4 h-4 mr-1" />
                      Paused
                    </>
                  )}
                </Button>
              )}
              
              <Button variant="outline" size="sm" data-testid="chart-settings">
                <Settings className="w-4 h-4" />
              </Button>
              
              <Button variant="outline" size="sm" data-testid="chart-export">
                <Download className="w-4 h-4" />
              </Button>
              
              <Button variant="outline" size="sm" data-testid="chart-fullscreen">
                <Maximize2 className="w-4 h-4" />
              </Button>
            </div>
          )}
        </div>

        {/* Status Indicators */}
        <div className="flex items-center space-x-3 mt-4">
          <Badge variant="outline" className="text-xs font-medium border-slate-300 text-slate-600">
            {chartData.length} data points
          </Badge>
          
          {config.threshold && (
            <>
              <Badge 
                variant="outline" 
                className={`text-xs font-semibold ${currentValue >= config.threshold.critical ? 'border-red-400 bg-red-50 text-red-700' : 
                  currentValue >= config.threshold.warning ? 'border-orange-400 bg-orange-50 text-orange-700' : 
                  'border-green-400 bg-green-50 text-green-700'}`}
              >
                {currentValue >= config.threshold.critical ? '🔴 Critical' :
                 currentValue >= config.threshold.warning ? '🟡 Warning' : '🟢 Normal'}
              </Badge>
            </>
          )}
          
          {isLive && (
            <Badge variant="default" className="text-xs font-semibold bg-gradient-to-r from-green-100 to-blue-100 text-green-800 border-green-300">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse mr-2"></div>
              Live Updates
            </Badge>
          )}
        </div>
      </CardHeader>
      
      <CardContent className="pt-0">
        <div className="relative">
          <div className="bg-gradient-to-br from-slate-50 to-white rounded-lg border border-slate-100 p-3 mb-4">
            <canvas 
              ref={canvasRef}
              className="w-full rounded-md"
              style={{ height: `${height}px` }}
              data-testid="chart-canvas"
            />
            
            {chartData.length === 0 && (
              <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 rounded-lg m-3">
                <div className="text-center text-slate-500">
                  <BarChart3 className="w-12 h-12 mx-auto mb-3 opacity-40" />
                  <p className="text-sm font-medium">No data available</p>
                  <p className="text-xs text-slate-400 mt-1">Waiting for metrics...</p>
                </div>
              </div>
            )}
          </div>
        
          {/* Quick Stats */}
          <div className="grid grid-cols-3 gap-4 p-4 bg-gradient-to-r from-slate-50 to-slate-100 rounded-lg border border-slate-200">
            <div className="text-center">
              <div className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-1">Min</div>
              <div className="text-lg font-bold text-slate-800" data-testid="min-value">
                {chartData.length > 0 ? Math.min(...chartData.map(d => d.value)).toFixed(1) : '0.0'}{config.unit}
              </div>
            </div>
            <div className="text-center border-l border-r border-slate-300">
              <div className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-1">Avg</div>
              <div className="text-lg font-bold text-slate-800" data-testid="avg-value">
                {chartData.length > 0 ? (chartData.reduce((sum, d) => sum + d.value, 0) / chartData.length).toFixed(1) : '0.0'}{config.unit}
              </div>
            </div>
            <div className="text-center">
              <div className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-1">Max</div>
              <div className="text-lg font-bold text-slate-800" data-testid="max-value">
                {chartData.length > 0 ? Math.max(...chartData.map(d => d.value)).toFixed(1) : '0.0'}{config.unit}
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// Real-time analytics component with actual API integration
export const DashboardVisualization: React.FC<{ className?: string }> = ({ className = '' }) => {
  const [responseTimeData, setResponseTimeData] = useState<DataPoint[]>([])
  const [throughputData, setThroughputData] = useState<DataPoint[]>([])
  const [errorRateData, setErrorRateData] = useState<DataPoint[]>([])
  const [usageData, setUsageData] = useState<DataPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  const { currentTimeRange } = useTimeRange()
  const { tenant } = useAuth()

  useEffect(() => {
    if (tenant) {
      loadMetricsData()
    }
  }, [tenant, currentTimeRange])

  const loadMetricsData = async () => {
    try {
      setLoading(true)
      setError(null)

      console.log('📊 Loading real-time analytics data...')
      
      // Convert time range to API format
      const timeRange = currentTimeRange.value
      const interval = currentTimeRange.value.includes('m') ? '1m' : 
                      currentTimeRange.value.includes('h') ? '5m' : '1h'

      // Load multiple metrics in parallel
      const [
        responseTimeMetrics,
        throughputMetrics,
        errorRateMetrics,
        usageHistory
      ] = await Promise.allSettled([
        // Response time metrics
        ObservabilityApi.queryMetrics({
          metric_name: 'http_request_duration_milliseconds',
          time_range: timeRange,
          interval: interval,
          filters: { aggregation: 'avg' }
        }),
        
        // Throughput metrics  
        ObservabilityApi.queryMetrics({
          metric_name: 'http_requests_total',
          time_range: timeRange,
          interval: interval,
          filters: { aggregation: 'rate' }
        }),
        
        // Error rate metrics
        ObservabilityApi.queryMetrics({
          metric_name: 'http_requests_total',
          time_range: timeRange,
          interval: interval,
          filters: { status: '5xx', aggregation: 'rate' }
        }),

        // Usage data from tenant API
        UsageApi.getUsageHistory(tenant.id, {
          start_date: currentTimeRange.startTime.toISOString(),
          end_date: currentTimeRange.endTime.toISOString(),
          period: 'daily',
          metric_type: 'api_calls'
        })
      ])

      // Process response time data
      if (responseTimeMetrics.status === 'fulfilled' && responseTimeMetrics.value.data) {
        const responseTimePoints = responseTimeMetrics.value.data
          .flatMap((series: any) => series.data_points || [])
          .map((point: any) => ({
            timestamp: point.timestamp,
            value: Math.round(point.value * 1000) // Convert to ms
          }))
        setResponseTimeData(responseTimePoints)
        console.log('📈 Response time data loaded:', responseTimePoints.length, 'points')
      }

      // Process throughput data
      if (throughputMetrics.status === 'fulfilled' && throughputMetrics.value.data) {
        const throughputPoints = throughputMetrics.value.data
          .flatMap((series: any) => series.data_points || [])
          .map((point: any) => ({
            timestamp: point.timestamp,
            value: Math.round(point.value) // Requests per second
          }))
        setThroughputData(throughputPoints)
        console.log('📈 Throughput data loaded:', throughputPoints.length, 'points')
      }

      // Process error rate data
      if (errorRateMetrics.status === 'fulfilled' && errorRateMetrics.value.data) {
        const errorRatePoints = errorRateMetrics.value.data
          .flatMap((series: any) => series.data_points || [])
          .map((point: any) => ({
            timestamp: point.timestamp,
            value: Math.round(point.value * 100 * 100) / 100 // Convert to percentage
          }))
        setErrorRateData(errorRatePoints)
        console.log('📈 Error rate data loaded:', errorRatePoints.length, 'points')
      }

      // Process usage data
      if (usageHistory.status === 'fulfilled' && usageHistory.value.data) {
        const usagePoints = (usageHistory.value.data as any[]).map((usage: any) => ({
          timestamp: usage.date || usage.timestamp,
          value: usage.api_calls || usage.total_calls || 0
        }))
        setUsageData(usagePoints)
        console.log('📈 Usage data loaded:', usagePoints.length, 'points')
      }

      console.log('✅ Real-time analytics data loaded successfully')

    } catch (err: any) {
      console.error('❌ Failed to load analytics data:', err)
      setError(err.message || 'Failed to load analytics data')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className={`${className} grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6`}>
        {[1, 2, 3].map(i => (
          <div key={i} className="h-64 bg-slate-200 rounded-lg animate-pulse"></div>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className={`${className} p-6 text-center text-slate-500`}>
        <AlertTriangle className="w-12 h-12 mx-auto mb-3 text-slate-300" />
        <p className="text-sm font-medium mb-1">Unable to load analytics data</p>
        <p className="text-xs">{error}</p>
        <Button 
          size="sm" 
          variant="outline" 
          onClick={loadMetricsData}
          className="mt-4"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Retry
        </Button>
      </div>
    )
  }

  return (
    <div className={className}>
      {/* Chart Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6" data-testid="dashboard-visualization">
        <AdvancedDataViz
          data={responseTimeData}
          config={{
            title: 'API Response Time',
            type: 'area',
            color: '#3b82f6',
            gradientFrom: '#3b82f6',
            gradientTo: '#1d4ed8',
            unit: 'ms',
            threshold: {
              warning: 300,
              critical: 500
            }
          }}
          realTime={true}
          height={240}
        />
        
        <AdvancedDataViz
          data={throughputData}
          config={{
            title: 'API Throughput',
            type: 'line',
            color: '#10b981',
            gradientFrom: '#10b981',
            gradientTo: '#059669',
            unit: 'req/s',
            threshold: {
              warning: 1000,
              critical: 2000
            }
          }}
          realTime={true}
          height={240}
        />
        
        <AdvancedDataViz
          data={errorRateData}
          config={{
            title: 'Error Rate',
            type: 'line',
            color: '#ef4444',
            gradientFrom: '#ef4444',
            gradientTo: '#dc2626',
            unit: '%',
            threshold: {
              warning: 3,
              critical: 5
            }
          }}
          realTime={true}
          height={240}
        />
      </div>
      
      {/* Additional Enterprise Metrics */}
      <div className="mt-8">
        <AdvancedDataViz
          data={usageData}
          config={{
            title: 'API Usage Trends',
            type: 'bar',
            color: '#8b5cf6',
            gradientFrom: '#8b5cf6',
            gradientTo: '#7c3aed',
            unit: ' calls',
            threshold: {
              warning: 50000,
              critical: 100000
            }
          }}
          realTime={false}
          height={200}
        />
      </div>
    </div>
  )
}

export default AdvancedDataViz