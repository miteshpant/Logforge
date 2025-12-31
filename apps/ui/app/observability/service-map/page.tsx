'use client'

import { useEffect, useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import ServiceMapVisualization from '@/components/observability/ServiceMapVisualization'
import ServiceMapControls from '@/components/observability/ServiceMapControls'
import ServiceMapDetails from '@/components/observability/ServiceMapDetails'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'

export interface ServiceNode {
  id: string
  name: string
  type: 'service' | 'database' | 'external' | 'cache'
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

export default function ServiceMapPage() {
  const { getApiTimeRange } = useTimeRange()
  const [serviceMapData, setServiceMapData] = useState<ServiceMapData | null>(null)
  const [selectedNode, setSelectedNode] = useState<ServiceNode | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<string>('all')
  const [filterHealth, setFilterHealth] = useState<string>('all')
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(30000) // 30 seconds default

  const loadServiceMap = async () => {
    try {
      setIsLoading(true)
      const { start_time, end_time } = getApiTimeRange()

      const response = await apiClient.get<ServiceMapData>('/v1/observability/service-map', {
        start_time,
        end_time
      })

      const data = response?.data || response

      if (data) {
        setServiceMapData(data as ServiceMapData)
      }
    } catch (error) {
      console.error('Failed to load service map:', error)
      // Set mock data for development
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
    } finally {
      setIsLoading(false)
    }
  }

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
  const filteredData = serviceMapData ? {
    ...serviceMapData,
    nodes: serviceMapData.nodes.filter(node => {
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
    })
  } : null

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-white">Service Map</h1>
            <p className="text-slate-400 mt-1">
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
        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
          <h3 className="text-sm font-semibold text-white mb-3">Legend</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-emerald-500"></div>
              <span className="text-slate-300">Healthy</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-yellow-500"></div>
              <span className="text-slate-300">Degraded</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-red-500"></div>
              <span className="text-slate-300">Down</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-blue-500"></div>
              <span className="text-slate-300">Service</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-purple-500"></div>
              <span className="text-slate-300">Database</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-orange-500"></div>
              <span className="text-slate-300">Cache</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-slate-500"></div>
              <span className="text-slate-300">External</span>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
