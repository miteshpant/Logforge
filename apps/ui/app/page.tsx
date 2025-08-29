'use client'
import { useEffect, useState } from 'react'
import { Activity, Database, MessageSquare, Shield } from 'lucide-react'

interface HealthData {
  status: string
  timestamp: string
  services: Record<string, string>
}

export default function Home() {
  const [healthData, setHealthData] = useState<HealthData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchHealthData()
  }, [])

  const fetchHealthData = async () => {
    try {
      const response = await fetch(process.env.NEXT_PUBLIC_API_URL + '/health')
      const data = await response.json()
      setHealthData(data)
    } catch (error) {
      console.error('Failed to fetch health data:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    return status === 'healthy' ? 'text-green-500' : 'text-red-500'
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="py-8">
        <h2 className="text-4xl font-bold text-center mb-8">Welcome to Logforge</h2>
        <p className="text-xl text-center text-gray-600 mb-12">
          Open Observability + SIEM Platform - A credible logger
        </p>

        {/* System Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          <div className="bg-white p-6 rounded-lg shadow-md">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500">System Status</p>
                {loading ? (
                  <p className="text-2xl font-bold text-gray-400">Loading...</p>
                ) : (
                  <p className={`text-2xl font-bold ${getStatusColor(healthData?.status || 'unknown')}`}>
                    {healthData?.status || 'Unknown'}
                  </p>
                )}
              </div>
              <Activity className="h-8 w-8 text-gray-400" />
            </div>
          </div>

          <div className="bg-white p-6 rounded-lg shadow-md">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500">ClickHouse</p>
                {loading ? (
                  <p className="text-2xl font-bold text-gray-400">Loading...</p>
                ) : (
                  <p className={`text-2xl font-bold ${getStatusColor(healthData?.services?.clickhouse?.includes('healthy') ? 'healthy' : 'unhealthy')}`}>
                    {healthData?.services?.clickhouse?.includes('healthy') ? 'Healthy' : 'Unhealthy'}
                  </p>
                )}
              </div>
              <Database className="h-8 w-8 text-gray-400" />
            </div>
          </div>

          <div className="bg-white p-6 rounded-lg shadow-md">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500">Log Ingestion</p>
                <p className="text-2xl font-bold text-blue-500">Ready</p>
              </div>
              <MessageSquare className="h-8 w-8 text-gray-400" />
            </div>
          </div>

          <div className="bg-white p-6 rounded-lg shadow-md">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500">Security</p>
                <p className="text-2xl font-bold text-green-500">Active</p>
              </div>
              <Shield className="h-8 w-8 text-gray-400" />
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-2xl font-bold mb-4">Quick Actions</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button className="bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded">
              View Recent Logs
            </button>
            <button className="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded">
              Send Test Log
            </button>
            <button className="bg-purple-500 hover:bg-purple-600 text-white font-bold py-2 px-4 rounded">
              System Health
            </button>
          </div>
        </div>

        {/* Architecture Overview */}
        <div className="mt-12 bg-white rounded-lg shadow-md p-6">
          <h3 className="text-2xl font-bold mb-4">Architecture Overview</h3>
          <div className="text-gray-600 space-y-2">
            <p>• <strong>Ingestion:</strong> HTTP/OTLP endpoints for log collection</p>
            <p>• <strong>Storage:</strong> ClickHouse (hot) + S3/MinIO (cold)</p>
            <p>• <strong>Processing:</strong> Redpanda message queue + transform pipeline</p>
            <p>• <strong>Interface:</strong> React/Next.js frontend + FastAPI backend</p>
          </div>
        </div>
      </div>
    </div>
  )
}
