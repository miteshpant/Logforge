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
  type: 'service' | 'database' | 'external' | 'cache' | 'application'
  health: 'healthy' | 'degraded' | 'down'
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

// Transform API service to internal node format
function transformApiService(service: ApiService): ServiceNode {
  const errorRate = service.request_count > 0
    ? (service.error_count / service.request_count) * 100
    : 0

  // Map service_type to our internal types
  let nodeType: ServiceNode['type'] = 'application'
  const st = service.service_type?.toLowerCase() || ''
  if (st.includes('database') || st.includes('db') || st.includes('postgres') || st.includes('mysql')) {
    nodeType = 'database'
  } else if (st.includes('cache') || st.includes('redis') || st.includes('memcached')) {
    nodeType = 'cache'
  } else if (st.includes('external') || st.includes('api')) {
    nodeType = 'external'
  } else if (st.includes('service') || st.includes('application')) {
    nodeType = 'application'
  }

  return {
    id: service.id,
    name: service.service_name,
    type: nodeType,
    health: (service.health_status as ServiceNode['health']) || 'healthy',
    metrics: {
      request_count: service.request_count || 0,
      error_rate: errorRate,
      avg_latency_ms: service.avg_response_time_ms || 0,
      p95_latency_ms: (service.avg_response_time_ms || 0) * 2 // Estimate P95
    },
    metadata: {
      version: service.service_version || undefined,
      environment: service.deployment_environment || undefined,
      namespace: service.namespace || undefined
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
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<string>('all')
  const [filterHealth, setFilterHealth] = useState<string>('all')
  const [selectedService, setSelectedService] = useState<string>('all')
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(30000) // 30 seconds default

  // Create service options for dropdown from raw services
  const serviceOptions = useMemo(() => {
    return rawServices.map(s => ({
      id: s.id,
      name: s.service_name
    }))
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
        const nodes = services.map(transformApiService)
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

  // Filter nodes based on search and filters
  const filteredData = serviceMapData && serviceMapData.nodes ? {
    ...serviceMapData,
    nodes: serviceMapData.nodes.filter(node => {
      // Service filter (specific service selected from dropdown)
      if (selectedService !== 'all' && node.id !== selectedService) {
        return false
      }

      // Search filter
      if (searchQuery && !node.name.toLowerCase().includes(searchQuery.toLowerCase())) {
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
    }),
    edges: serviceMapData.edges || []
  } : null

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
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          filterType={filterType}
          onFilterTypeChange={setFilterType}
          filterHealth={filterHealth}
          onFilterHealthChange={setFilterHealth}
          autoRefresh={autoRefresh}
          onAutoRefreshChange={setAutoRefresh}
          refreshInterval={refreshInterval}
          onRefreshIntervalChange={setRefreshInterval}
          services={serviceOptions}
          selectedService={selectedService}
          onSelectedServiceChange={setSelectedService}
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
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
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
              <span className="text-slate-700">Down</span>
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
              <div className="w-4 h-4 rounded bg-slate-500"></div>
              <span className="text-slate-700">External</span>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
