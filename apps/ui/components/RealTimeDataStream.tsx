'use client'

import React, { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { 
  Activity, 
  Wifi, 
  WifiOff, 
  Zap, 
  TrendingUp, 
  AlertTriangle,
  CheckCircle,
  Clock,
  Database,
  Shield,
  Brain,
  Eye,
  Play,
  Pause,
  Settings
} from 'lucide-react'
import { ObservabilityApi, SecurityApi, AlertsApi, QueryApi, UsageApi, AiApi } from '@/lib/api'
import { apiClient } from '@/lib/api/client'
import { useAuth } from '@/contexts/AuthContext'

interface StreamEvent {
  id: string
  timestamp: string
  type: 'log' | 'alert' | 'metric' | 'security' | 'ai_insight'
  severity: 'low' | 'medium' | 'high' | 'critical'
  service: string
  message: string
  metadata?: Record<string, any>
}

interface RealTimeDataStreamProps {
  className?: string
  maxEvents?: number
  showControls?: boolean
  types?: string[]
}

export const RealTimeDataStream: React.FC<RealTimeDataStreamProps> = ({
  className = '',
  maxEvents = 50,
  showControls = true,
  types = ['traces', 'alert', 'metric', 'security']
}) => {
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [eventsPerSecond, setEventsPerSecond] = useState(0)
  const [totalEvents, setTotalEvents] = useState(0)
  const wsRef = useRef<WebSocket | null>(null)
  const eventsContainerRef = useRef<HTMLDivElement>(null)
  const eventCountRef = useRef(0)
  const lastSecondRef = useRef(Date.now())

  const { tenant } = useAuth()

  useEffect(() => {
    if (tenant && !isPaused) {
      startRealTimeStreaming()
    } else {
      stopRealTimeStreaming()
    }

    return () => {
      stopRealTimeStreaming()
    }
  }, [tenant, isPaused, types])

  const streamCleanupRefs = useRef<Array<() => void>>([])

  const startRealTimeStreaming = async () => {
    try {
      setIsConnected(true)
      console.log('🔴 Starting real-time streams for types:', types)

      // 1. Start observability metrics streaming
      if (types.includes('metric')) {
        console.log('📊 Starting metrics stream...')
        const metricsCleanup = await ObservabilityApi.streamMetrics(
          // Metric names to stream
          [
            'http_request_duration_milliseconds',
            'http_requests_total', 
            'cpu_usage_percent',
            'memory_usage_percent',
            'disk_io_bytes',
            'network_throughput_bytes'
          ],
          // Callback for each metric
          (metricData) => {
            const event: StreamEvent = {
              id: `metric-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              timestamp: new Date().toISOString(),
              type: 'metric',
              severity: metricData.value > 0.8 ? 'high' : metricData.value > 0.6 ? 'medium' : 'low',
              service: metricData.labels?.service_name || 'system',
              message: `${metricData.metric_name}: ${formatMetricValue(metricData.value, metricData.metric_name)}`,
              metadata: metricData.labels
            }
            addEvent(event)
          },
          // Error callback
          (error) => console.error('Metrics stream error:', error)
        )
        streamCleanupRefs.current.push(metricsCleanup)
      }

      // 2. Start security events streaming
      if (types.includes('security')) {
        console.log('🛡️ Starting security events stream...')
        const securityCleanup = await SecurityApi.streamSecurityEvents(
          (securityEvent) => {
            const event: StreamEvent = {
              id: `security-${securityEvent.id || Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              timestamp: securityEvent.timestamp || new Date().toISOString(),
              type: 'security',
              severity: (securityEvent.severity as StreamEvent['severity']) || 'medium',
              service: 'security-engine',
              message: `${securityEvent.rule_name || 'Security Event'}: ${securityEvent.description || 'Security detection triggered'}`,
              metadata: { 
                rule_id: securityEvent.rule_id || 'unknown', 
                mitre: securityEvent.mitre_technique || 'N/A',
                source_ip: securityEvent.source_ip || 'N/A',
                target_ip: securityEvent.target_ip || 'N/A'
              }
            }
            addEvent(event)
          },
          (error) => {
            console.error('Security stream error:', error)
            // Add error event to stream for visibility
            const errorEvent: StreamEvent = {
              id: `security-error-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              timestamp: new Date().toISOString(),
              type: 'security',
              severity: 'medium',
              service: 'security-engine',
              message: `Security streaming error: ${error.message || 'Connection failed'}`,
              metadata: { error: true }
            }
            addEvent(errorEvent)
          },
          { severity: ['medium', 'high', 'critical'] }
        )
        streamCleanupRefs.current.push(securityCleanup)
      }

      // 3. Start alert events streaming
      if (types.includes('alert')) {
        console.log('🚨 Starting alert events stream...')
        const alertsCleanup = await AlertsApi.streamAlertEvents(
          (alertEvent) => {
            const event: StreamEvent = {
              id: `alert-${alertEvent.id || Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              timestamp: alertEvent.triggered_at || new Date().toISOString(),
              type: 'alert',
              severity: (alertEvent.severity as StreamEvent['severity']) || 'medium',
              service: alertEvent.rule_name || 'alert-engine',
              message: `Alert: ${alertEvent.message || alertEvent.description || 'Alert triggered'}`,
              metadata: {
                rule_id: alertEvent.rule_id || 'unknown',
                condition: alertEvent.condition || 'N/A',
                threshold: alertEvent.threshold || 'N/A'
              }
            }
            addEvent(event)
          },
          (error) => {
            console.error('Alerts stream error:', error)
            // Add error event to stream for visibility
            const errorEvent: StreamEvent = {
              id: `alert-error-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              timestamp: new Date().toISOString(),
              type: 'alert',
              severity: 'medium',
              service: 'alert-engine',
              message: `Alert: Alerts streaming error: ${error.message || 'Connection failed'}`,
              metadata: { error: true }
            }
            addEvent(errorEvent)
          },
          { severity: ['medium', 'high', 'critical'] }
        )
        streamCleanupRefs.current.push(alertsCleanup)
      }

      // 4. Start usage tracking streaming (using correct /v1/stream/usage endpoint)
      if (types.includes('log') && tenant) {
        console.log('📈 Starting usage stream...')
        const usageCleanup = await apiClient.getStream(
          '/v1/stream/usage',
          (usageData) => {
            // Usage stream returns: {"api_calls": 15420, "data_ingested_gb": 12.5, "storage_used_gb": 145.2, "cost_today": 25.80}
            if (usageData && typeof usageData === 'object') {
              const metrics = [
                { key: 'api_calls', value: usageData.api_calls, label: 'API Calls' },
                { key: 'data_ingested_gb', value: usageData.data_ingested_gb, label: 'Data Ingested (GB)' },
                { key: 'storage_used_gb', value: usageData.storage_used_gb, label: 'Storage Used (GB)' },
                { key: 'cost_today', value: usageData.cost_today, label: 'Cost Today ($)' }
              ].filter(metric => metric.value !== undefined && metric.value !== null)
              
              metrics.forEach(metric => {
                const event: StreamEvent = {
                  id: `usage-${metric.key}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                  timestamp: new Date().toISOString(),
                  type: 'log',
                  severity: metric.value > 1000 ? 'high' : 'low',
                  service: 'usage-tracker',
                  message: `${metric.label}: ${formatMetricValue(metric.value, metric.key)}`,
                  metadata: {
                    tenant_id: tenant.id,
                    metric_type: metric.key,
                    value: metric.value
                  }
                }
                addEvent(event)
              })
            }
          },
          (error) => console.error('Usage stream error:', error)
        )
        streamCleanupRefs.current.push(usageCleanup)
      }

      // 5. Start distributed tracing streaming
      if (types.includes('log')) {
        console.log('🔍 Starting traces stream...')
        const tracesCleanup = await ObservabilityApi.streamTraces(
          (traceData) => {
            const event: StreamEvent = {
              id: `trace-${traceData.trace_id || Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              timestamp: traceData.start_time,
              type: 'log',
              severity: traceData.duration > 5000 ? 'high' : traceData.duration > 1000 ? 'medium' : 'low',
              service: traceData.service_name,
              message: `Trace completed: ${traceData.operation_name} (${traceData.duration}ms)`,
              metadata: {
                trace_id: traceData.trace_id,
                span_count: traceData.span_count,
                operation: traceData.operation_name,
                duration_ms: traceData.duration
              }
            }
            addEvent(event)
          },
          (error) => console.error('Traces stream error:', error),
          { 
            min_duration: 100, // Only show traces > 100ms
            status: ['error', 'timeout'] // Focus on problematic traces
          }
        )
        streamCleanupRefs.current.push(tracesCleanup)
      }

      // 6. Start AI insights streaming  
      if (types.includes('ai_insight')) {
        console.log('🧠 Starting AI insights stream...')
        // Note: AI streaming requires an analysis ID, so we'll start a general monitoring analysis
        try {
          const analysisResponse = await AiApi.performRootCauseAnalysis({
            symptoms: ['Real-time monitoring analysis'],
            time_range: '5m',
            affected_services: [],
            incident_context: { 
              scope: 'platform'
            }
          })
          
          if (analysisResponse.data?.id) {
            const aiCleanup = await AiApi.streamAnalysisResults(
              analysisResponse.data.id,
              (aiResult) => {
                // Only process insights and results, skip progress updates
                if (aiResult.type !== 'progress') {
                  const event: StreamEvent = {
                    id: `ai-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                    timestamp: new Date().toISOString(),
                    type: 'ai_insight',
                    severity: (aiResult.data?.confidence || 0.5) > 0.8 ? 'high' : (aiResult.data?.confidence || 0.5) > 0.6 ? 'medium' : 'low',
                    service: 'ai-engine',
                    message: `AI ${aiResult.type}: ${aiResult.data?.finding || aiResult.data?.result || aiResult.data?.message || 'Analysis update'}`,
                    metadata: {
                      analysis_id: analysisResponse.data.id,
                      update_type: aiResult.type,
                      confidence: aiResult.data?.confidence,
                      category: aiResult.data?.category
                    }
                  }
                  addEvent(event)
                }
              },
              (error) => console.error('AI insights stream error:', error)
            )
            streamCleanupRefs.current.push(aiCleanup)
          }
        } catch (error) {
          console.warn('AI insights streaming not available:', error)
        }
      }

      console.log('✅ Real-time streaming started for', streamCleanupRefs.current.length, 'streams')

    } catch (error) {
      console.error('Failed to start real-time streaming:', error)
      setIsConnected(false)
    }
  }

  const formatMetricValue = (value: number, metricName: string): string => {
    if (metricName.includes('bytes') || metricName.includes('size')) {
      return formatBytes(value)
    } else if (metricName.includes('rate') || metricName.includes('rps')) {
      return `${value.toFixed(1)}/s`
    } else if (metricName.includes('duration') || metricName.includes('latency')) {
      return `${value.toFixed(1)}ms`
    } else if (metricName.includes('percent') || metricName.includes('ratio')) {
      return `${(value * 100).toFixed(1)}%`
    } else {
      return value.toFixed(2)
    }
  }

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
  }

  const stopRealTimeStreaming = () => {
    console.log('🔴 Stopping real-time streams')
    streamCleanupRefs.current.forEach(cleanup => cleanup())
    streamCleanupRefs.current = []
    setIsConnected(false)
  }

  // Real streaming implementation - dummy data generation removed

  const addEvent = (newEvent: StreamEvent) => {
    setEvents(prev => {
      const updated = [newEvent, ...prev].slice(0, maxEvents)
      return updated
    })

    // Update metrics
    eventCountRef.current++
    setTotalEvents(prev => prev + 1)

    // Calculate events per second
    const now = Date.now()
    if (now - lastSecondRef.current >= 1000) {
      setEventsPerSecond(eventCountRef.current)
      eventCountRef.current = 0
      lastSecondRef.current = now
    }

    // Auto-scroll to top
    if (eventsContainerRef.current) {
      eventsContainerRef.current.scrollTop = 0
    }
  }

  const getEventIcon = (type: StreamEvent['type']) => {
    switch (type) {
      case 'log': return <Database className="w-4 h-4" />
      case 'alert': return <AlertTriangle className="w-4 h-4" />
      case 'metric': return <TrendingUp className="w-4 h-4" />
      case 'security': return <Shield className="w-4 h-4" />
      case 'ai_insight': return <Brain className="w-4 h-4" />
      default: return <Activity className="w-4 h-4" />
    }
  }

  const getEventColor = (type: StreamEvent['type'], severity: StreamEvent['severity']) => {
    if (severity === 'critical') return 'bg-red-100 border-red-200 text-red-800'
    if (severity === 'high') return 'bg-orange-100 border-orange-200 text-orange-800'
    
    switch (type) {
      case 'log': return 'bg-blue-100 border-blue-200 text-blue-800'
      case 'alert': return 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
      case 'metric': return 'bg-green-500/10 border-green-500/30 text-green-400'
      case 'security': return 'bg-purple-500/10 border-purple-500/30 text-purple-400'
      case 'ai_insight': return 'bg-indigo-500/10 border-indigo-500/30 text-indigo-400'
      default: return 'bg-slate-500/10 border-slate-500/30 text-slate-400'
    }
  }

  const getSeverityColor = (severity: StreamEvent['severity']) => {
    switch (severity) {
      case 'critical': return 'bg-red-500'
      case 'high': return 'bg-orange-500'
      case 'medium': return 'bg-yellow-500'
      case 'low': return 'bg-green-500'
      default: return 'bg-slate-500'
    }
  }

  const formatTime = (timestamp: string) => {
    try {
      const date = new Date(timestamp)
      if (isNaN(date.getTime())) {
        return new Date().toLocaleTimeString('en-US', {
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        })
      }
      return date.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      })
    } catch (error) {
      return new Date().toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      })
    }
  }

  const formatTimeAgo = (timestamp: string) => {
    try {
      const now = Date.now()
      const time = new Date(timestamp).getTime()
      
      if (isNaN(time)) {
        return 'just now'
      }
      
      const diff = now - time
      
      if (diff < 1000) return 'just now'
      if (diff < 60000) return `${Math.floor(diff / 1000)}s ago`
      if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
      return `${Math.floor(diff / 3600000)}h ago`
    } catch (error) {
      return 'just now'
    }
  }

  return (
    <Card className={`${className} bg-gradient-to-br from-slate-900 to-slate-800 text-white border-slate-700`} data-testid="real-time-stream">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="relative">
              {isConnected ? (
                <Wifi className="w-5 h-5 text-green-400" />
              ) : (
                <WifiOff className="w-5 h-5 text-red-400" />
              )}
              {isConnected && (
                <div className="absolute -top-1 -right-1 w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
              )}
            </div>
            <div>
              <CardTitle className="text-lg text-white">Live Data Stream</CardTitle>
              <div className="flex items-center space-x-4 text-sm text-slate-300 mt-1">
                <span className="flex items-center space-x-1">
                  <Activity className="w-3 h-3" />
                  <span>{eventsPerSecond} events/sec</span>
                </span>
                <span>•</span>
                <span>{totalEvents.toLocaleString()} total</span>
                <span>•</span>
                <span className={isConnected ? 'text-green-400' : 'text-red-400'}>
                  {isConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>
          </div>

          {showControls && (
            <div className="flex items-center space-x-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsPaused(!isPaused)}
                className="text-white hover:bg-slate-700"
                data-testid="stream-toggle"
              >
                {isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setEvents([])}
                className="text-white hover:bg-slate-700"
                data-testid="stream-clear"
              >
                Clear
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-white hover:bg-slate-700"
                data-testid="stream-settings"
              >
                <Settings className="w-4 h-4" />
              </Button>
            </div>
          )}
        </div>
      </CardHeader>
      
      <CardContent className="p-0">
        <div 
          ref={eventsContainerRef}
          className="h-80 overflow-y-auto space-y-2 px-4 pb-4"
          data-testid="stream-events"
        >
          {events.length === 0 ? (
            <div className="flex items-center justify-center h-full text-slate-400">
              <div className="text-center">
                <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p>Waiting for live events...</p>
              </div>
            </div>
          ) : (
            events.map((event, index) => (
              <div
                key={event.id}
                className="flex items-start space-x-3 p-3 bg-slate-800/50 rounded-lg border border-slate-700/50 hover:bg-slate-700/50 transition-all duration-200"
                data-testid={`stream-event-${index}`}
                style={{
                  animation: index === 0 ? 'slideInFromTop 0.3s ease-out' : undefined
                }}
              >
                <div className="flex items-center space-x-2 flex-shrink-0">
                  <div className={`w-2 h-2 rounded-full ${getSeverityColor(event.severity)}`}></div>
                  <Badge className={`${getEventColor(event.type, event.severity)} border text-xs`}>
                    {getEventIcon(event.type)}
                    <span className="ml-1 capitalize">{event.type.replace('_', ' ')}</span>
                  </Badge>
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <Badge variant="outline" className="text-xs text-slate-300 border-slate-600">
                      {event.service}
                    </Badge>
                    <div className="flex items-center space-x-2 text-xs text-slate-400">
                      <Clock className="w-3 h-3" />
                      <span>{formatTime(event.timestamp)}</span>
                      <span>({formatTimeAgo(event.timestamp)})</span>
                    </div>
                  </div>
                  <p className="text-sm text-slate-200 leading-relaxed">{event.message}</p>
                  
                  {event.metadata && (
                    <div className="flex items-center space-x-3 mt-2 text-xs text-slate-400">
                      {event.metadata.region && (
                        <span>📍 {event.metadata.region}</span>
                      )}
                      {event.metadata.environment && (
                        <span>🏷️ {event.metadata.environment}</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
      
      <style jsx>{`
        @keyframes slideInFromTop {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </Card>
  )
}

export default RealTimeDataStream