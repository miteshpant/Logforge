'use client'

import React, { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { ObservabilityApi, ServiceMap, ServiceNode, Trace, ApmSummary, ErrorAnalysis } from '@/lib/api/observability'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { 
  Activity, 
  AlertTriangle, 
  BarChart3, 
  Clock, 
  RefreshCw,
  Search,
  TrendingUp,
  Database,
  Globe,
  Layers,
  Zap,
  Target,
  Eye,
  ExternalLink,
  Filter,
  Download,
  Network,
  Server,
  Timer,
  Bug,
  CheckCircle,
  XCircle,
  ArrowRight,
  LineChart
} from 'lucide-react'

interface ServiceMapVisualizationProps {
  serviceMap: ServiceMap | null
}

const ServiceMapVisualization: React.FC<ServiceMapVisualizationProps> = ({ serviceMap }) => {
  const getHealthColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'bg-green-100 border-green-300 text-green-800'
      case 'warning': return 'bg-yellow-100 border-yellow-300 text-yellow-800'
      case 'critical': return 'bg-red-100 border-red-300 text-red-800'
      default: return 'bg-gray-100 border-gray-300 text-gray-800'
    }
  }

  const getServiceIcon = (type: string) => {
    switch (type) {
      case 'web': return <Globe className="w-4 h-4" />
      case 'database': return <Database className="w-4 h-4" />
      case 'cache': return <Zap className="w-4 h-4" />
      case 'queue': return <Layers className="w-4 h-4" />
      case 'external': return <ExternalLink className="w-4 h-4" />
      default: return <Server className="w-4 h-4" />
    }
  }

  if (!serviceMap) return null

  return (
    <div className="space-y-4">
      {/* Service Map Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center space-x-2">
            <Server className="w-5 h-5 text-blue-600" />
            <div>
              <p className="text-sm font-medium">Total Services</p>
              <p className="text-xl font-bold">{serviceMap.metrics.total_services}</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center space-x-2">
            <Activity className="w-5 h-5 text-green-600" />
            <div>
              <p className="text-sm font-medium">Total Requests</p>
              <p className="text-xl font-bold">{serviceMap.metrics.total_requests.toLocaleString()}</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-5 h-5 text-orange-600" />
            <div>
              <p className="text-sm font-medium">Error Rate</p>
              <p className="text-xl font-bold">{(serviceMap.metrics.overall_error_rate * 100).toFixed(2)}%</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center space-x-2">
            <Timer className="w-5 h-5 text-purple-600" />
            <div>
              <p className="text-sm font-medium">Avg Response</p>
              <p className="text-xl font-bold">{serviceMap.metrics.avg_response_time}ms</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Service Nodes */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {serviceMap.services.map((service) => (
          <Card key={service.name} className={`hover:shadow-md transition-shadow border-2 ${getHealthColor(service.health_status)}`}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  {getServiceIcon(service.type)}
                  <div>
                    <CardTitle className="text-base">{service.name}</CardTitle>
                    <CardDescription className="text-sm capitalize">{service.type} • {service.environment}</CardDescription>
                  </div>
                </div>
                <Badge className={getHealthColor(service.health_status)}>
                  {service.health_status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-gray-600">Requests/min:</span>
                    <span className="font-medium ml-1">{service.metrics.request_rate}</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Error Rate:</span>
                    <span className="font-medium ml-1">{(service.metrics.error_rate * 100).toFixed(1)}%</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Latency:</span>
                    <span className="font-medium ml-1">{service.metrics.avg_latency}ms</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Apdex:</span>
                    <span className="font-medium ml-1">{service.metrics.apdex_score.toFixed(2)}</span>
                  </div>
                </div>
                {service.version && (
                  <div className="text-xs text-gray-500">
                    Version: {service.version}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

interface TraceCardProps {
  trace: Trace
  onViewDetails: (traceId: string) => void
}

const TraceCard: React.FC<TraceCardProps> = ({ trace, onViewDetails }) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success': return 'bg-green-100 text-green-800'
      case 'error': return 'bg-red-100 text-red-800'
      case 'timeout': return 'bg-orange-100 text-orange-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getDurationColor = (duration: number) => {
    if (duration > 1000) return 'text-red-600'
    if (duration > 500) return 'text-orange-600'
    return 'text-green-600'
  }

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Network className="w-4 h-4 text-blue-600" />
            <div>
              <CardTitle className="text-base">{trace.operation_name}</CardTitle>
              <CardDescription className="text-sm">{trace.service_name}</CardDescription>
            </div>
          </div>
          <div className="flex space-x-2">
            <Badge className={getStatusColor(trace.status)}>
              {trace.status.toUpperCase()}
            </Badge>
            <Badge variant="outline" className={getDurationColor(trace.duration)}>
              {trace.duration}ms
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <div className="text-sm text-gray-600">
            <strong>Trace ID:</strong> <code className="text-xs bg-gray-100 px-1 rounded">{trace.id}</code>
          </div>
          <div className="text-sm text-gray-600">
            <strong>Spans:</strong> {trace.spans.length} spans
          </div>
          <div className="text-sm text-gray-600">
            <strong>Started:</strong> {new Date(trace.start_time).toLocaleString()}
          </div>
          {trace.error && (
            <div className="text-sm text-red-600">
              <strong>Error:</strong> {trace.error}
            </div>
          )}
          <div className="flex space-x-2">
            <Button 
              size="sm" 
              variant="outline"
              onClick={() => onViewDetails(trace.id)}
            >
              <Eye className="w-4 h-4 mr-1" />
              View Timeline
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

interface ErrorCardProps {
  error: ErrorAnalysis
  onUpdateStatus: (errorId: string, status: ErrorAnalysis['resolution_status']) => void
}

const ErrorCard: React.FC<ErrorCardProps> = ({ error, onUpdateStatus }) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'open': return 'bg-red-100 text-red-800'
      case 'investigating': return 'bg-yellow-100 text-yellow-800'
      case 'resolved': return 'bg-green-100 text-green-800'
      case 'ignored': return 'bg-gray-100 text-gray-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Bug className="w-4 h-4 text-red-600" />
            <div>
              <CardTitle className="text-base">{error.error_type}</CardTitle>
              <CardDescription className="text-sm">{error.service_name}</CardDescription>
            </div>
          </div>
          <Badge className={getStatusColor(error.resolution_status)}>
            {error.resolution_status.toUpperCase()}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <div className="text-sm text-gray-800">
            {error.message}
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
            <div>
              <strong>Occurrences:</strong> {error.occurrence_count}
            </div>
            <div>
              <strong>Affected Users:</strong> {error.affected_users}
            </div>
            <div>
              <strong>First Seen:</strong> {new Date(error.first_seen).toLocaleDateString()}
            </div>
            <div>
              <strong>Last Seen:</strong> {new Date(error.last_seen).toLocaleDateString()}
            </div>
          </div>
          <div className="flex space-x-2">
            {error.resolution_status === 'open' && (
              <Button 
                size="sm" 
                variant="outline"
                onClick={() => onUpdateStatus(error.error_id, 'investigating')}
              >
                Investigate
              </Button>
            )}
            {error.resolution_status !== 'resolved' && (
              <Button 
                size="sm" 
                variant="outline"
                onClick={() => onUpdateStatus(error.error_id, 'resolved')}
              >
                <CheckCircle className="w-4 h-4 mr-1" />
                Resolve
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function ObservabilityPage(): React.ReactElement {
  const { user, tenant } = useAuth()
  const [serviceMap, setServiceMap] = useState<ServiceMap | null>(null)
  const [services, setServices] = useState<ServiceNode[]>([])
  const [traces, setTraces] = useState<Trace[]>([])
  const [errors, setErrors] = useState<ErrorAnalysis[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [selectedTimeRange, setSelectedTimeRange] = useState('1h')

  useEffect(() => {
    loadObservabilityData()
  }, [selectedTimeRange])

  const loadObservabilityData = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const [serviceMapResponse, servicesResponse, tracesResponse, errorsResponse] = await Promise.all([
        ObservabilityApi.getServiceMap(selectedTimeRange),
        ObservabilityApi.listServices(),
        ObservabilityApi.searchTraces({ time_range: selectedTimeRange, limit: 20 }),
        ObservabilityApi.getErrorAnalysis({ time_range: selectedTimeRange, limit: 20 })
      ])
      
      if (serviceMapResponse.success) {
        setServiceMap(serviceMapResponse.data)
      }
      
      if (servicesResponse.success) {
        setServices(servicesResponse.data || [])
      }
      
      if (tracesResponse.success && tracesResponse.data) {
        setTraces(tracesResponse.data || [])
      }
      
      if (errorsResponse.success && errorsResponse.data) {
        setErrors(errorsResponse.data || [])
      }
    } catch (err: any) {
      console.error('Failed to load observability data:', err)
      setError(err.message || 'Failed to load observability data')
    } finally {
      setLoading(false)
    }
  }

  const viewTraceDetails = (traceId: string) => {
    alert(`View Trace Details: ${traceId}\n\nThis would open a detailed trace timeline view showing all spans, timing, and dependencies.`)
  }

  const updateErrorStatus = async (errorId: string, status: ErrorAnalysis['resolution_status']) => {
    try {
      const response = await ObservabilityApi.updateErrorStatus(errorId, status, 'Updated from UI')
      
      if (response.success) {
        setErrors(prev => 
          prev.map(error => 
            error.error_id === errorId ? { ...error, resolution_status: status } : error
          )
        )
      }
    } catch (err: any) {
      console.error('Failed to update error status:', err)
      setError(err.message || 'Failed to update error status')
    }
  }

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <div className="flex items-center space-x-2">
            <RefreshCw className="w-6 h-6 animate-spin" />
            <span>Loading observability data...</span>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Observability & APM</h1>
            <p className="text-gray-600 mt-1">
              Monitor application performance, distributed traces, and service dependencies
            </p>
          </div>
          <div className="flex space-x-2">
            <select 
              value={selectedTimeRange}
              onChange={(e) => setSelectedTimeRange(e.target.value)}
              className="border rounded px-3 py-2 text-sm"
            >
              <option value="15m">Last 15 minutes</option>
              <option value="1h">Last hour</option>
              <option value="6h">Last 6 hours</option>
              <option value="24h">Last 24 hours</option>
              <option value="7d">Last 7 days</option>
            </select>
            <Button variant="outline" onClick={loadObservabilityData}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* APM Overview Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <Activity className="w-8 h-8 text-blue-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">Total Services</p>
                  <p className="text-2xl font-bold text-gray-900">{serviceMap?.metrics.total_services || 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <TrendingUp className="w-8 h-8 text-green-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">Requests/min</p>
                  <p className="text-2xl font-bold text-gray-900">{serviceMap?.metrics.total_requests.toLocaleString() || 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <Timer className="w-8 h-8 text-purple-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">Avg Response</p>
                  <p className="text-2xl font-bold text-gray-900">{serviceMap?.metrics.avg_response_time || 0}ms</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <AlertTriangle className="w-8 h-8 text-orange-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">Error Rate</p>
                  <p className="text-2xl font-bold text-gray-900">{((serviceMap?.metrics.overall_error_rate || 0) * 100).toFixed(2)}%</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Observability Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="service-map">Service Map ({serviceMap?.services.length || 0})</TabsTrigger>
            <TabsTrigger value="traces">Distributed Traces ({traces.length})</TabsTrigger>
            <TabsTrigger value="errors">Error Analysis ({errors.length})</TabsTrigger>
            <TabsTrigger value="metrics">Metrics</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Service Health Overview */}
              <Card>
                <CardHeader>
                  <CardTitle>Service Health Overview</CardTitle>
                  <CardDescription>Health status of all monitored services</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {services.slice(0, 5).map((service) => {
                      const getHealthIcon = (status: string) => {
                        switch (status) {
                          case 'healthy': return <CheckCircle className="w-4 h-4 text-green-600" />
                          case 'warning': return <AlertTriangle className="w-4 h-4 text-yellow-600" />
                          case 'critical': return <XCircle className="w-4 h-4 text-red-600" />
                          default: return <Clock className="w-4 h-4 text-gray-600" />
                        }
                      }

                      return (
                        <div key={service.name} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                          <div className="flex items-center space-x-3">
                            {getHealthIcon(service.health_status)}
                            <div>
                              <div className="font-medium">{service.name}</div>
                              <div className="text-sm text-gray-600 capitalize">{service.type} • {service.environment}</div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-sm font-medium">{service.metrics.avg_latency}ms</div>
                            <div className="text-xs text-gray-500">{(service.metrics.error_rate * 100).toFixed(1)}% errors</div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* Recent Errors */}
              <Card>
                <CardHeader>
                  <CardTitle>Recent Errors</CardTitle>
                  <CardDescription>Latest application errors requiring attention</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {errors.filter(e => e.resolution_status === 'open').slice(0, 5).map((error) => (
                      <div key={error.error_id} className="flex items-center justify-between p-3 bg-red-50 rounded border-l-4 border-red-400">
                        <div>
                          <div className="font-medium text-red-800">{error.error_type}</div>
                          <div className="text-sm text-red-600">{error.service_name}</div>
                          <div className="text-xs text-red-500">{error.occurrence_count} occurrences</div>
                        </div>
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => updateErrorStatus(error.error_id, 'investigating')}
                        >
                          Investigate
                        </Button>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="service-map" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Service Map & Dependencies</CardTitle>
                <CardDescription>Visualize service topology and dependencies</CardDescription>
              </CardHeader>
              <CardContent>
                <ServiceMapVisualization serviceMap={serviceMap} />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="traces" className="mt-6">
            {traces.length === 0 ? (
              <Card>
                <CardContent className="p-8 text-center">
                  <Network className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    No traces found
                  </h3>
                  <p className="text-gray-600">
                    No distributed traces found for the selected time range
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {traces.map((trace) => (
                  <TraceCard
                    key={trace.id}
                    trace={trace}
                    onViewDetails={viewTraceDetails}
                  />
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="errors" className="mt-6">
            {errors.length === 0 ? (
              <Card>
                <CardContent className="p-8 text-center">
                  <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    No errors found
                  </h3>
                  <p className="text-gray-600">
                    No application errors detected in the selected time range
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {errors.map((error) => (
                  <ErrorCard
                    key={error.error_id}
                    error={error}
                    onUpdateStatus={updateErrorStatus}
                  />
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="metrics" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Custom Metrics & KPIs</CardTitle>
                <CardDescription>Monitor business and application metrics</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-8">
                  <LineChart className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    Metrics Dashboard
                  </h3>
                  <p className="text-gray-600 mb-4">
                    Create custom dashboards and track business-critical metrics
                  </p>
                  <Button>
                    <BarChart3 className="w-4 h-4 mr-2" />
                    Create Custom Dashboard
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  )
}