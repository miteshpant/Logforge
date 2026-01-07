'use client'

import { useEffect, useState, useMemo } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import ServiceMapVisualization from '@/components/observability/ServiceMapVisualization'
import ServiceMapControls from '@/components/observability/ServiceMapControls'
import ServiceMapDetails from '@/components/observability/ServiceMapDetails'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'

// API response types
interface ApiService {
  id: string
  customer_id: string
  service_name: string
  service_version: string
  service_instance_id: string
  deployment_environment: string
  namespace: string
  cluster: string
  host: string
  container_id: string
  service_type: string
  dependencies: string[]
  endpoints: string[]
  health_status: string
  last_seen: string
  request_count: number
  error_count: number
  avg_response_time_ms: number
  metadata: Record<string, unknown>
  resource_attributes: string
  created_at: string
  updated_at: string
}

interface ApiServiceMapResponse {
  services: ApiService[]
}

export interface ServiceNode {
  id: string
  name: string
  type: 'api' | 'application' | 'database' | 'cache' | 'queue' | 'external' | 'service'
  health: 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
  metrics: {
    request_count: number
    error_rate: number
    avg_latency_ms: number
    p95_latency_ms: number
  }
  metadata?: {
    version?: string
    environment?: string
    namespace?: string
    instanceCount?: number
  }
}

export interface ServiceEdge {
  source: string
  target: string
  metrics: {
    request_count: number
    error_count: number
    avg_latency_ms: number
  }
}

export interface ServiceMapData {
  nodes: ServiceNode[]
  edges: ServiceEdge[]
  timestamp: string
}

// Map service_type DB enum to internal node type
function mapServiceType(serviceType: string): ServiceNode['type'] {
  const st = serviceType?.toLowerCase() || ''
  // Match DB enum values: api, database, cache, queue, external, application
  if (st === 'api') return 'api'
  if (st === 'database' || st.includes('postgres') || st.includes('mysql') || st.includes('db')) return 'database'
  if (st === 'cache' || st.includes('redis') || st.includes('memcached')) return 'cache'
  if (st === 'queue' || st.includes('kafka') || st.includes('rabbitmq') || st.includes('sqs')) return 'queue'
  if (st === 'external') return 'external'
  if (st === 'application' || st === 'service') return 'application'
  return 'application' // Default
}

// Map health_status DB enum to internal health
function mapHealthStatus(healthStatus: string): ServiceNode['health'] {
  const hs = healthStatus?.toLowerCase() || ''
  // Match DB enum values: healthy, degraded, unhealthy, unknown
  if (hs === 'healthy') return 'healthy'
  if (hs === 'degraded') return 'degraded'
  if (hs === 'unhealthy' || hs === 'down') return 'unhealthy'
  if (hs === 'unknown') return 'unknown'
  return 'unknown' // Default
}

// Aggregate services by unique service_name
interface AggregatedService {
  service_name: string
  instances: ApiService[]
  total_request_count: number
  total_error_count: number
  avg_response_time_ms: number
  dominant_type: string
  dominant_health: string
  environments: string[]
}

function aggregateServicesByName(services: ApiService[]): AggregatedService[] {
  const serviceMap = new Map<string, ApiService[]>()

  // Group by service_name
  services.forEach(service => {
    const name = service.service_name
    if (!serviceMap.has(name)) {
      serviceMap.set(name, [])
    }
    serviceMap.get(name)!.push(service)
  })

  // Aggregate metrics for each unique service
  const aggregated: AggregatedService[] = []

  serviceMap.forEach((instances, serviceName) => {
    const totalRequests = instances.reduce((sum, s) => sum + (s.request_count || 0), 0)
    const totalErrors = instances.reduce((sum, s) => sum + (s.error_count || 0), 0)
    const avgLatency = instances.length > 0
      ? instances.reduce((sum, s) => sum + (s.avg_response_time_ms || 0), 0) / instances.length
      : 0

    // Get unique environments
    const environments = Array.from(new Set(instances.map(s => s.deployment_environment).filter(Boolean))) as string[]

    // Determine dominant type (most common)
    const typeCounts = instances.reduce((acc, s) => {
      const t = s.service_type || 'application'
      acc[t] = (acc[t] || 0) + 1
      return acc
    }, {} as Record<string, number>)
    const dominantType = Object.entries(typeCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'application'

    // Determine dominant health (worst health wins: unhealthy > degraded > unknown > healthy)
    const healthPriority: Record<string, number> = { unhealthy: 4, degraded: 3, unknown: 2, healthy: 1 }
    const dominantHealth = instances.reduce((worst, s) => {
      const h = s.health_status?.toLowerCase() || 'unknown'
      return (healthPriority[h] || 0) > (healthPriority[worst] || 0) ? h : worst
    }, 'healthy')

    aggregated.push({
      service_name: serviceName,
      instances,
      total_request_count: totalRequests,
      total_error_count: totalErrors,
      avg_response_time_ms: avgLatency,
      dominant_type: dominantType,
      dominant_health: dominantHealth,
      environments
    })
  })

  return aggregated
}

// Transform aggregated service to internal node format
function transformAggregatedService(agg: AggregatedService): ServiceNode {
  const errorRate = agg.total_request_count > 0
    ? (agg.total_error_count / agg.total_request_count) * 100
    : 0

  // Use first instance's ID for the aggregated node
  const primaryInstance = agg.instances[0]

  return {
    id: primaryInstance.id,
    name: agg.service_name,
    type: mapServiceType(agg.dominant_type),
    health: mapHealthStatus(agg.dominant_health),
    metrics: {
      request_count: agg.total_request_count,
      error_rate: errorRate,
      avg_latency_ms: agg.avg_response_time_ms,
      p95_latency_ms: agg.avg_response_time_ms * 2 // Estimate P95
    },
    metadata: {
      version: primaryInstance.service_version || undefined,
      environment: agg.environments.join(', ') || undefined,
      namespace: primaryInstance.namespace || undefined,
      instanceCount: agg.instances.length
    }
  }
}

// Transform API service to internal node format (for single instance)
function transformApiService(service: ApiService): ServiceNode {
  const errorRate = service.request_count > 0
    ? (service.error_count / service.request_count) * 100
    : 0

  return {
    id: service.id,
    name: service.service_name,
    type: mapServiceType(service.service_type),
    health: mapHealthStatus(service.health_status),
    metrics: {
      request_count: service.request_count || 0,
      error_rate: errorRate,
      avg_latency_ms: service.avg_response_time_ms || 0,
      p95_latency_ms: (service.avg_response_time_ms || 0) * 2 // Estimate P95
    },
    metadata: {
      version: service.service_version || undefined,
      environment: service.deployment_environment || undefined,
      namespace: service.namespace || undefined,
      instanceCount: 1
    }
  }
}

// Build edges from service dependencies
function buildEdges(services: ApiService[]): ServiceEdge[] {
  const edges: ServiceEdge[] = []
  const serviceMap = new Map(services.map(s => [s.service_name, s]))

  services.forEach(service => {
    if (service.dependencies && Array.isArray(service.dependencies)) {
      service.dependencies.forEach(depName => {
        const depService = serviceMap.get(depName)
        if (depService) {
          edges.push({
            source: service.id,
            target: depService.id,
            metrics: {
              request_count: service.request_count || 0,
              error_count: service.error_count || 0,
              avg_latency_ms: service.avg_response_time_ms || 0
            }
          })
        }
      })
    }
  })

  return edges
}

export default function ServiceMapPage() {
  const { getApiTimeRange } = useTimeRange()
  const [serviceMapData, setServiceMapData] = useState<ServiceMapData | null>(null)
  const [rawServices, setRawServices] = useState<ApiService[]>([])
  const [selectedNode, setSelectedNode] = useState<ServiceNode | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [filterType, setFilterType] = useState<string>('all')
  const [filterHealth, setFilterHealth] = useState<string>('all')
  const [selectedService, setSelectedService] = useState<string>('all')
  const [filterEnvironment, setFilterEnvironment] = useState<string>('all')
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(30000) // 30 seconds default

  // Extract unique environments from raw services
  const uniqueEnvironments = useMemo((): string[] => {
    const envs = new Set<string>()
    rawServices.forEach((s: ApiService) => {
      if (s.deployment_environment) {
        envs.add(s.deployment_environment)
      }
    })
    return Array.from(envs).sort()
  }, [rawServices])

  // Aggregate services by unique name with instance counts for dropdown
  const serviceOptions = useMemo(() => {
    const serviceMap = new Map<string, number>()
    rawServices.forEach((s: ApiService) => {
      const name = s.service_name
      serviceMap.set(name, (serviceMap.get(name) || 0) + 1)
    })
    return Array.from(serviceMap.entries())
      .map(([name, count]: [string, number]) => ({ name, instanceCount: count }))
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [rawServices])

  const loadServiceMap = async () => {
    try {
      setIsLoading(true)
      const { start_time, end_time } = getApiTimeRange()

      // Calculate time range in hours
      const timeRangeMs = new Date(end_time).getTime() - new Date(start_time).getTime()
      const timeRangeHours = Math.ceil(timeRangeMs / (1000 * 60 * 60))

      const response = await apiClient.get<ApiServiceMapResponse>('/v1/observability/service-map', {
        time_range_hours: timeRangeHours
      })

      const data = response?.data || response

      // Handle API response with 'services' array
      if (data && (data as ApiServiceMapResponse).services && Array.isArray((data as ApiServiceMapResponse).services)) {
        const services = (data as ApiServiceMapResponse).services
        setRawServices(services)

        // Aggregate services by unique name for visualization
        const aggregatedServices = aggregateServicesByName(services)
        const nodes = aggregatedServices.map(transformAggregatedService)
        const edges = buildEdges(services)

        setServiceMapData({
          nodes,
          edges,
          timestamp: new Date().toISOString()
        })
      }
      // Also handle legacy format with 'nodes' array
      else if (data && (data as unknown as ServiceMapData).nodes) {
        const legacyData = data as unknown as ServiceMapData
        setServiceMapData(legacyData)
        // Convert nodes to service options for the dropdown
        setRawServices(legacyData.nodes.map(n => ({
          id: n.id,
          customer_id: '',
          service_name: n.name,
          service_version: n.metadata?.version || '',
          service_instance_id: '',
          deployment_environment: n.metadata?.environment || '',
          namespace: n.metadata?.namespace || '',
          cluster: '',
          host: '',
          container_id: '',
          service_type: n.type,
          dependencies: [],
          endpoints: [],
          health_status: n.health,
          last_seen: '',
          request_count: n.metrics.request_count,
          error_count: Math.round(n.metrics.request_count * n.metrics.error_rate / 100),
          avg_response_time_ms: n.metrics.avg_latency_ms,
          metadata: {},
          resource_attributes: '',
          created_at: '',
          updated_at: ''
        })))
      }
      else {
        // If no data, show empty state
        setServiceMapData({ nodes: [], edges: [], timestamp: new Date().toISOString() })
        setRawServices([])
      }
    } catch (error) {
      console.error('Failed to load service map:', error)
      // Show empty state on error
      setServiceMapData({ nodes: [], edges: [], timestamp: new Date().toISOString() })
      setRawServices([])
    } finally {
      setIsLoading(false)
    }
  }

  // Keep old mock data generator for reference but commented out
  /*
  const generateMockData = () => {
    setServiceMapData({
        nodes: [
          {
            id: 'frontend',
            name: 'Frontend Service',
            type: 'service',
            health: 'healthy',
            metrics: {
              request_count: 15420,
              error_rate: 0.12,
              avg_latency_ms: 45,
              p95_latency_ms: 120
            }
          },
          {
            id: 'api-gateway',
            name: 'API Gateway',
            type: 'service',
            health: 'healthy',
            metrics: {
              request_count: 28934,
              error_rate: 0.05,
              avg_latency_ms: 28,
              p95_latency_ms: 85
            }
          },
          {
            id: 'auth-service',
            name: 'Auth Service',
            type: 'service',
            health: 'healthy',
            metrics: {
              request_count: 5623,
              error_rate: 0.03,
              avg_latency_ms: 15,
              p95_latency_ms: 42
            }
          },
          {
            id: 'user-service',
            name: 'User Service',
            type: 'service',
            health: 'degraded',
            metrics: {
              request_count: 12456,
              error_rate: 2.45,
              avg_latency_ms: 156,
              p95_latency_ms: 450
            }
          },
          {
            id: 'order-service',
            name: 'Order Service',
            type: 'service',
            health: 'healthy',
            metrics: {
              request_count: 8234,
              error_rate: 0.08,
              avg_latency_ms: 67,
              p95_latency_ms: 180
            }
          },
          {
            id: 'payment-service',
            name: 'Payment Service',
            type: 'service',
            health: 'healthy',
            metrics: {
              request_count: 3421,
              error_rate: 0.02,
              avg_latency_ms: 89,
              p95_latency_ms: 230
            }
          },
          {
            id: 'postgres',
            name: 'PostgreSQL',
            type: 'database',
            health: 'healthy',
            metrics: {
              request_count: 45678,
              error_rate: 0.01,
              avg_latency_ms: 8,
              p95_latency_ms: 25
            }
          },
          {
            id: 'redis',
            name: 'Redis Cache',
            type: 'cache',
            health: 'healthy',
            metrics: {
              request_count: 123456,
              error_rate: 0.0,
              avg_latency_ms: 2,
              p95_latency_ms: 5
            }
          },
          {
            id: 'stripe-api',
            name: 'Stripe API',
            type: 'external',
            health: 'healthy',
            metrics: {
              request_count: 3400,
              error_rate: 0.15,
              avg_latency_ms: 245,
              p95_latency_ms: 680
            }
          }
        ],
        edges: [
          { source: 'frontend', target: 'api-gateway', metrics: { request_count: 15420, error_count: 18, avg_latency_ms: 45 } },
          { source: 'api-gateway', target: 'auth-service', metrics: { request_count: 5623, error_count: 2, avg_latency_ms: 15 } },
          { source: 'api-gateway', target: 'user-service', metrics: { request_count: 12456, error_count: 305, avg_latency_ms: 156 } },
          { source: 'api-gateway', target: 'order-service', metrics: { request_count: 8234, error_count: 7, avg_latency_ms: 67 } },
          { source: 'order-service', target: 'payment-service', metrics: { request_count: 3421, error_count: 1, avg_latency_ms: 89 } },
          { source: 'payment-service', target: 'stripe-api', metrics: { request_count: 3400, error_count: 5, avg_latency_ms: 245 } },
          { source: 'auth-service', target: 'postgres', metrics: { request_count: 5600, error_count: 0, avg_latency_ms: 8 } },
          { source: 'user-service', target: 'postgres', metrics: { request_count: 12400, error_count: 1, avg_latency_ms: 8 } },
          { source: 'order-service', target: 'postgres', metrics: { request_count: 8200, error_count: 0, avg_latency_ms: 8 } },
          { source: 'auth-service', target: 'redis', metrics: { request_count: 5620, error_count: 0, avg_latency_ms: 2 } },
          { source: 'user-service', target: 'redis', metrics: { request_count: 12450, error_count: 0, avg_latency_ms: 2 } }
        ],
        timestamp: new Date().toISOString()
      })
    }
  }
  */

  // Initial load
  useEffect(() => {
    loadServiceMap()
  }, [])

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(() => {
      loadServiceMap()
    }, refreshInterval)

    return () => clearInterval(interval)
  }, [autoRefresh, refreshInterval])

  // Filter nodes based on selected filters
  const filteredData = useMemo((): ServiceMapData | null => {
    if (!serviceMapData || !serviceMapData.nodes) return null

    // First, filter rawServices by environment if selected
    let applicableServiceNames: Set<string> | null = null
    if (filterEnvironment !== 'all') {
      applicableServiceNames = new Set(
        rawServices
          .filter((s: ApiService) => s.deployment_environment === filterEnvironment)
          .map((s: ApiService) => s.service_name)
      )
    }

    const filteredNodes = serviceMapData.nodes.filter((node: ServiceNode) => {
      // Environment filter (check if service has any instance in selected environment)
      if (applicableServiceNames && !applicableServiceNames.has(node.name)) {
        return false
      }

      // Service filter (specific service selected from dropdown by name)
      if (selectedService !== 'all' && node.name !== selectedService) {
        return false
      }

      // Type filter
      if (filterType !== 'all' && node.type !== filterType) {
        return false
      }

      // Health filter
      if (filterHealth !== 'all' && node.health !== filterHealth) {
        return false
      }

      return true
    })

    // Filter edges to only include those between visible nodes
    const visibleNodeIds = new Set(filteredNodes.map((n: ServiceNode) => n.id))
    const filteredEdges = (serviceMapData.edges || []).filter(
      (edge: ServiceEdge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
    )

    return {
      ...serviceMapData,
      nodes: filteredNodes,
      edges: filteredEdges
    }
  }, [serviceMapData, rawServices, filterEnvironment, selectedService, filterType, filterHealth])

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">Service Map</h1>
            <p className="text-slate-600 mt-1">
              Interactive visualization of your service dependencies and health
            </p>
          </div>

          <button
            onClick={loadServiceMap}
            disabled={isLoading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>

        {/* Controls */}
        <ServiceMapControls
          filterType={filterType}
          onFilterTypeChange={setFilterType}
          filterHealth={filterHealth}
          onFilterHealthChange={setFilterHealth}
          filterEnvironment={filterEnvironment}
          onFilterEnvironmentChange={setFilterEnvironment}
          autoRefresh={autoRefresh}
          onAutoRefreshChange={setAutoRefresh}
          refreshInterval={refreshInterval}
          onRefreshIntervalChange={setRefreshInterval}
          services={serviceOptions}
          selectedService={selectedService}
          onSelectedServiceChange={setSelectedService}
          environments={uniqueEnvironments}
        />

        {/* Service Map Visualization and Details */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Map Visualization */}
          <div className="lg:col-span-2">
            <ServiceMapVisualization
              data={filteredData}
              isLoading={isLoading}
              selectedNode={selectedNode}
              onNodeSelect={setSelectedNode}
            />
          </div>

          {/* Node Details Panel */}
          <div className="lg:col-span-1">
            <ServiceMapDetails
              node={selectedNode}
              onClose={() => setSelectedNode(null)}
            />
          </div>
        </div>

        {/* Legend */}
        <div className="bg-white rounded-lg p-4 border border-slate-200 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900 mb-3">Legend</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 text-sm">
            {/* Health Status */}
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-emerald-500"></div>
              <span className="text-slate-700">Healthy</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-yellow-500"></div>
              <span className="text-slate-700">Degraded</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-red-500"></div>
              <span className="text-slate-700">Unhealthy</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-slate-400"></div>
              <span className="text-slate-700">Unknown</span>
            </div>
            {/* Service Types */}
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-cyan-500"></div>
              <span className="text-slate-700">API</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-blue-500"></div>
              <span className="text-slate-700">Application</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-purple-500"></div>
              <span className="text-slate-700">Database</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-orange-500"></div>
              <span className="text-slate-700">Cache</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-pink-500"></div>
              <span className="text-slate-700">Queue</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-slate-500"></div>
              <span className="text-slate-700">External</span>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
