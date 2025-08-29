'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Activity, Zap, Network, BarChart3, Clock, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'

// Types for observability data
interface Span {
  trace_id: string
  span_id: string
  parent_span_id?: string
  operation_name: string
  service_name: string
  start_time: string
  end_time?: string
  duration_ms: number
  kind: string
  status: 'ok' | 'error' | 'unset'
  attributes: Record<string, any>
}

interface Service {
  name: string
  total_spans: number
  avg_latency_ms: number
  error_rate: number
  operation_count: number
}

interface ServiceDependency {
  from_service: string
  to_service: string
  call_count: number
  avg_latency_ms: number
}

interface APMMetrics {
  request_rate: Array<{ time: string; rpm: number }>
  latency: {
    p50_ms: number
    p95_ms: number
    p99_ms: number
    avg_ms: number
  }
  error_rate: Array<{ time: string; error_rate: number }>
}

export default function ObservabilityPage() {
  const [activeTab, setActiveTab] = useState('overview')
  const [services, setServices] = useState<Service[]>([])
  const [dependencies, setDependencies] = useState<ServiceDependency[]>([])
  const [selectedService, setSelectedService] = useState<string>('')
  const [apmMetrics, setApmMetrics] = useState<APMMetrics | null>(null)
  const [traces, setTraces] = useState<Span[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [timeRange, setTimeRange] = useState('1h')

  // Search filters
  const [traceSearch, setTraceSearch] = useState({
    service_name: '',
    operation_name: '',
    status: '',
    min_duration_ms: '',
    max_duration_ms: ''
  })

  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080'
  const customerId = 'demo-customer' // In real app, get from auth context

  useEffect(() => {
    loadServiceMap()
  }, [timeRange])

  useEffect(() => {
    if (selectedService) {
      loadAPMMetrics(selectedService)
    }
  }, [selectedService, timeRange])

  const loadServiceMap = async () => {
    try {
      setLoading(true)
      setError(null)

      const timeRangeHours = timeRange === '1h' ? 1 : timeRange === '24h' ? 24 : 168
      
      const response = await fetch(
        `${baseUrl}/v1/observability/service-map?time_range_hours=${timeRangeHours}`,
        {
          headers: {
            'X-Customer-ID': customerId,
            'Content-Type': 'application/json'
          }
        }
      )

      if (!response.ok) {
        throw new Error('Failed to load service map')
      }

      const data = await response.json()
      setServices(data.services || [])
      setDependencies(data.dependencies || [])

      if (data.services?.length > 0 && !selectedService) {
        setSelectedService(data.services[0].name)
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load service map')
      console.error('Service map error:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadAPMMetrics = async (serviceName: string) => {
    try {
      const timeRangeHours = timeRange === '1h' ? 1 : timeRange === '24h' ? 24 : 168
      
      const response = await fetch(
        `${baseUrl}/v1/observability/apm/${serviceName}?time_range_hours=${timeRangeHours}`,
        {
          headers: {
            'X-Customer-ID': customerId,
            'Content-Type': 'application/json'
          }
        }
      )

      if (!response.ok) {
        throw new Error('Failed to load APM metrics')
      }

      const data = await response.json()
      setApmMetrics(data.metrics)

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load APM metrics')
      console.error('APM metrics error:', err)
    }
  }

  const searchTraces = async () => {
    try {
      setLoading(true)
      setError(null)

      const searchParams: any = {
        limit: 50
      }

      if (traceSearch.service_name) searchParams.service_name = traceSearch.service_name
      if (traceSearch.operation_name) searchParams.operation_name = traceSearch.operation_name
      if (traceSearch.status) searchParams.status = traceSearch.status
      if (traceSearch.min_duration_ms) searchParams.min_duration_ms = parseInt(traceSearch.min_duration_ms)
      if (traceSearch.max_duration_ms) searchParams.max_duration_ms = parseInt(traceSearch.max_duration_ms)

      const response = await fetch(
        `${baseUrl}/v1/observability/traces/search`,
        {
          method: 'POST',
          headers: {
            'X-Customer-ID': customerId,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(searchParams)
        }
      )

      if (!response.ok) {
        throw new Error('Failed to search traces')
      }

      const data = await response.json()
      setTraces(data.traces || [])

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to search traces')
      console.error('Trace search error:', err)
    } finally {
      setLoading(false)
    }
  }

  const formatDuration = (ms: number) => {
    if (ms < 1) return `${(ms * 1000).toFixed(0)}μs`
    if (ms < 1000) return `${ms.toFixed(1)}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'ok': return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'error': return <XCircle className="w-4 h-4 text-red-500" />
      default: return <Clock className="w-4 h-4 text-gray-500" />
    }
  }

  const getErrorRateColor = (rate: number) => {
    if (rate < 1) return 'text-green-600'
    if (rate < 5) return 'text-yellow-600'
    return 'text-red-600'
  }

  return (
    <div className="container mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Observability & APM</h1>
        <div className="flex items-center gap-4">
          <Select value={timeRange} onValueChange={setTimeRange}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1h">Last 1 hour</SelectItem>
              <SelectItem value="24h">Last 24 hours</SelectItem>
              <SelectItem value="7d">Last 7 days</SelectItem>
            </SelectContent>
          </Select>
          <Button 
            onClick={loadServiceMap}
            disabled={loading}
            variant="outline"
          >
            {loading ? 'Loading...' : 'Refresh'}
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview" className="flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="services" className="flex items-center gap-2">
            <Network className="w-4 h-4" />
            Service Map
          </TabsTrigger>
          <TabsTrigger value="apm" className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4" />
            APM Metrics
          </TabsTrigger>
          <TabsTrigger value="traces" className="flex items-center gap-2">
            <Zap className="w-4 h-4" />
            Trace Search
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Services</CardTitle>
                <Network className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{services.length}</div>
                <p className="text-xs text-muted-foreground">Active services</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Dependencies</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{dependencies.length}</div>
                <p className="text-xs text-muted-foreground">Service dependencies</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Avg Latency</CardTitle>
                <Clock className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {services.length > 0 
                    ? formatDuration(services.reduce((sum, s) => sum + s.avg_latency_ms, 0) / services.length)
                    : '0ms'
                  }
                </div>
                <p className="text-xs text-muted-foreground">Across all services</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Error Rate</CardTitle>
                <AlertTriangle className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {services.length > 0 
                    ? `${(services.reduce((sum, s) => sum + s.error_rate, 0) / services.length).toFixed(2)}%`
                    : '0%'
                  }
                </div>
                <p className="text-xs text-muted-foreground">Across all services</p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Service Health Overview</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {services.map((service) => (
                  <div key={service.name} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="w-3 h-3 rounded-full bg-green-500"></div>
                      <div>
                        <div className="font-medium">{service.name}</div>
                        <div className="text-sm text-muted-foreground">
                          {service.operation_count} operations
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-6 text-sm">
                      <div>
                        <div className="font-medium">{formatDuration(service.avg_latency_ms)}</div>
                        <div className="text-muted-foreground">Latency</div>
                      </div>
                      <div>
                        <div className={`font-medium ${getErrorRateColor(service.error_rate)}`}>
                          {service.error_rate.toFixed(2)}%
                        </div>
                        <div className="text-muted-foreground">Errors</div>
                      </div>
                      <div>
                        <div className="font-medium">{service.total_spans.toLocaleString()}</div>
                        <div className="text-muted-foreground">Spans</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="services" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Service Dependency Map</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {services.map((service) => (
                    <Card key={service.name} className="p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-semibold">{service.name}</h3>
                        <Badge variant="outline">{service.total_spans} spans</Badge>
                      </div>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span>Latency:</span>
                          <span>{formatDuration(service.avg_latency_ms)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Error Rate:</span>
                          <span className={getErrorRateColor(service.error_rate)}>
                            {service.error_rate.toFixed(2)}%
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Operations:</span>
                          <span>{service.operation_count}</span>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>

                {dependencies.length > 0 && (
                  <div className="mt-8">
                    <h3 className="text-lg font-semibold mb-4">Service Dependencies</h3>
                    <div className="space-y-2">
                      {dependencies.map((dep, index) => (
                        <div key={index} className="flex items-center justify-between p-3 bg-muted rounded-lg">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{dep.from_service}</span>
                            <span>→</span>
                            <span className="font-medium">{dep.to_service}</span>
                          </div>
                          <div className="flex items-center gap-4 text-sm">
                            <span>{dep.call_count} calls</span>
                            <span>{formatDuration(dep.avg_latency_ms)} avg</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="apm" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>APM Metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-4">
                <Select value={selectedService} onValueChange={setSelectedService}>
                  <SelectTrigger className="w-64">
                    <SelectValue placeholder="Select service..." />
                  </SelectTrigger>
                  <SelectContent>
                    {services.map((service) => (
                      <SelectItem key={service.name} value={service.name}>
                        {service.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {apmMetrics && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">P50 Latency</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">
                        {formatDuration(apmMetrics.latency.p50_ms)}
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">P95 Latency</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">
                        {formatDuration(apmMetrics.latency.p95_ms)}
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">P99 Latency</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">
                        {formatDuration(apmMetrics.latency.p99_ms)}
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">Avg Latency</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">
                        {formatDuration(apmMetrics.latency.avg_ms)}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="traces" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Trace Search</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-4">
                <Input
                  placeholder="Service name"
                  value={traceSearch.service_name}
                  onChange={(e) => setTraceSearch({...traceSearch, service_name: e.target.value})}
                />
                <Input
                  placeholder="Operation name"
                  value={traceSearch.operation_name}
                  onChange={(e) => setTraceSearch({...traceSearch, operation_name: e.target.value})}
                />
                <Select 
                  value={traceSearch.status} 
                  onValueChange={(value) => setTraceSearch({...traceSearch, status: value})}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">All statuses</SelectItem>
                    <SelectItem value="ok">OK</SelectItem>
                    <SelectItem value="error">Error</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  placeholder="Min duration (ms)"
                  type="number"
                  value={traceSearch.min_duration_ms}
                  onChange={(e) => setTraceSearch({...traceSearch, min_duration_ms: e.target.value})}
                />
                <Button onClick={searchTraces} disabled={loading}>
                  {loading ? 'Searching...' : 'Search'}
                </Button>
              </div>

              <div className="space-y-2">
                {traces.map((span) => (
                  <div key={`${span.trace_id}-${span.span_id}`} 
                       className="p-4 border rounded-lg hover:bg-muted/50">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        {getStatusIcon(span.status)}
                        <span className="font-medium">{span.service_name}</span>
                        <Badge variant="outline">{span.operation_name}</Badge>
                      </div>
                      <div className="flex items-center gap-4 text-sm">
                        <span>{formatDuration(span.duration_ms)}</span>
                        <span className="text-muted-foreground">
                          {new Date(span.start_time).toLocaleTimeString()}
                        </span>
                      </div>
                    </div>
                    <div className="text-xs text-muted-foreground font-mono">
                      Trace: {span.trace_id}
                    </div>
                  </div>
                ))}
                
                {traces.length === 0 && !loading && (
                  <div className="text-center py-8 text-muted-foreground">
                    No traces found. Try adjusting your search criteria.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}