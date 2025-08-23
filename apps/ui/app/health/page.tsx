'use client'
import { useEffect, useState } from 'react'
import { format } from 'date-fns'
import { CheckCircle, XCircle, RefreshCw } from 'lucide-react'

interface HealthData {
  status: string
  timestamp: string
  services: Record<string, string>
}

export default function HealthPage() {
  const [healthData, setHealthData] = useState<HealthData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchHealthData()
    const interval = setInterval(fetchHealthData, 10000) // Update every 10 seconds
    return () => clearInterval(interval)
  }, [])

  const fetchHealthData = async () => {
    setLoading(true)
    try {
      const response = await fetch(process.env.NEXT_PUBLIC_API_URL + '/health')
      const data = await response.json()
      setHealthData(data)
    } catch (error) {
      console.error('Failed to fetch health data:', error)
      setHealthData(null)
    } finally {
      setLoading(false)
    }
  }

  const getStatusIcon = (status: string) => {
    const isHealthy = status === 'healthy' || status.includes('healthy')
    return isHealthy ? (
      <CheckCircle className="h-6 w-6 text-green-500" />
    ) : (
      <XCircle className="h-6 w-6 text-red-500" />
    )
  }

  const getStatusColor = (status: string) => {
    const isHealthy = status === 'healthy' || status.includes('healthy')
    return isHealthy ? 'text-green-600 bg-green-50' : 'text-red-600 bg-red-50'
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="py-8">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-3xl font-bold">System Health</h2>
          <button
            onClick={fetchHealthData}
            disabled={loading}
            className="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white font-bold py-2 px-4 rounded flex items-center gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Overall Status */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-xl font-semibold mb-2">Overall System Status</h3>
              {healthData ? (
                <div className="flex items-center gap-3">
                  {getStatusIcon(healthData.status)}
                  <span className={`px-3 py-1 rounded-full text-sm font-semibold ${getStatusColor(healthData.status)}`}>
                    {healthData.status.toUpperCase()}
                  </span>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <XCircle className="h-6 w-6 text-gray-500" />
                  <span className="px-3 py-1 rounded-full text-sm font-semibold text-gray-600 bg-gray-50">
                    UNKNOWN
                  </span>
                </div>
              )}
            </div>
            <div className="text-right text-sm text-gray-500">
              <p>Last updated:</p>
              <p>{healthData ? format(new Date(healthData.timestamp), 'MMM dd, yyyy HH:mm:ss') : 'Never'}</p>
            </div>
          </div>
        </div>

        {/* Service Status */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-xl font-semibold mb-4">Service Health</h3>
          
          {healthData?.services ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Object.entries(healthData.services).map(([service, status]) => (
                <div key={service} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-medium capitalize">{service}</h4>
                    {getStatusIcon(status)}
                  </div>
                  <div className={`text-xs px-2 py-1 rounded ${getStatusColor(status)}`}>
                    {status}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-gray-500 py-8">
              <p>Unable to load service status</p>
              <p className="text-sm mt-2">Check if the API is running</p>
            </div>
          )}
        </div>

        {/* Test Actions */}
        <div className="bg-white rounded-lg shadow-md p-6 mt-6">
          <h3 className="text-xl font-semibold mb-4">Test Actions</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <button
              onClick={() => {
                fetch(process.env.NEXT_PUBLIC_API_URL + '/v1/ingest/logs', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    service: 'test-service',
                    level: 'info',
                    msg: 'Test log entry from health page',
                    trace_id: `test-${Date.now()}`,
                    attrs: { source: 'health-page' }
                  })
                })
                .then(() => alert('Test log sent successfully!'))
                .catch(() => alert('Failed to send test log'))
              }}
              className="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded"
            >
              Send Test Log
            </button>
            <button
              onClick={() => {
                fetch(process.env.NEXT_PUBLIC_API_URL + '/v1/logs?limit=1')
                .then(res => res.json())
                .then(data => alert(`Found ${data.logs?.length || 0} logs in database`))
                .catch(() => alert('Failed to query logs'))
              }}
              className="bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded"
            >
              Test Query
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}