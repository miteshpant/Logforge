'use client'

import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import {
  Puzzle,
  Search,
  CheckCircle,
  XCircle,
  Settings,
  ExternalLink,
  Plus,
  RefreshCw,
  AlertTriangle,
  Zap,
  MessageSquare,
  Mail,
  GitBranch,
  Database,
  Cloud,
  Shield,
  BarChart,
  Bell,
  X,
  ChevronRight
} from 'lucide-react'

interface Integration {
  id: string
  name: string
  description: string
  category: 'alerting' | 'ticketing' | 'communication' | 'cloud' | 'security' | 'data'
  icon: string
  status: 'connected' | 'disconnected' | 'error' | 'available'
  config?: Record<string, any>
  lastSync?: string
  features: string[]
  docsUrl: string
}

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  alerting: <Bell className="w-5 h-5" />,
  ticketing: <GitBranch className="w-5 h-5" />,
  communication: <MessageSquare className="w-5 h-5" />,
  cloud: <Cloud className="w-5 h-5" />,
  security: <Shield className="w-5 h-5" />,
  data: <Database className="w-5 h-5" />
}

const CATEGORY_COLORS: Record<string, string> = {
  alerting: 'bg-red-500/20 text-red-400 border-red-500/30',
  ticketing: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  communication: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  cloud: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  security: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  data: 'bg-green-500/20 text-green-400 border-green-500/30'
}

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterCategory, setFilterCategory] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [selectedIntegration, setSelectedIntegration] = useState<Integration | null>(null)
  const [showConfigModal, setShowConfigModal] = useState(false)

  useEffect(() => {
    loadIntegrations()
  }, [])

  const loadIntegrations = async () => {
    try {
      setIsLoading(true)
      const response = await apiClient.get<{ integrations: Integration[] }>('/v1/enterprise/integrations')
      if (response?.data?.integrations) {
        setIntegrations(response.data.integrations)
      } else {
        setIntegrations([])
      }
    } catch (error) {
      console.error('Failed to load integrations:', error)
      setIntegrations([])
    } finally {
      setIsLoading(false)
    }
  }

  const testConnection = async (integrationId: string) => {
    try {
      await apiClient.post(`/v1/enterprise/integrations/${integrationId}/test`)
      // Simulate success
      setIntegrations(integrations.map(i =>
        i.id === integrationId ? { ...i, status: 'connected' as const, lastSync: new Date().toISOString() } : i
      ))
    } catch (error) {
      console.error('Failed to test connection:', error)
    }
  }

  const disconnectIntegration = async (integrationId: string) => {
    if (!confirm('Are you sure you want to disconnect this integration?')) return

    try {
      await apiClient.delete(`/v1/enterprise/integrations/${integrationId}`)
      setIntegrations(integrations.map(i =>
        i.id === integrationId ? { ...i, status: 'available' as const, config: undefined } : i
      ))
    } catch (error) {
      console.error('Failed to disconnect:', error)
      setIntegrations(integrations.map(i =>
        i.id === integrationId ? { ...i, status: 'available' as const, config: undefined } : i
      ))
    }
  }

  const filteredIntegrations = integrations.filter(integration => {
    if (searchQuery && !integration.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !integration.description.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false
    }
    if (filterCategory !== 'all' && integration.category !== filterCategory) return false
    if (filterStatus === 'connected' && integration.status !== 'connected') return false
    if (filterStatus === 'available' && integration.status !== 'available' && integration.status !== 'disconnected') return false
    if (filterStatus === 'error' && integration.status !== 'error') return false
    return true
  })

  const stats = {
    total: integrations.length,
    connected: integrations.filter(i => i.status === 'connected').length,
    available: integrations.filter(i => i.status === 'available' || i.status === 'disconnected').length,
    errors: integrations.filter(i => i.status === 'error').length
  }

  const formatTimeAgo = (timestamp: string | undefined) => {
    if (!timestamp) return 'Never'
    const diff = Date.now() - new Date(timestamp).getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    if (hours > 0) return `${hours}h ago`
    if (minutes > 0) return `${minutes}m ago`
    return 'Just now'
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'connected': return <CheckCircle className="w-5 h-5 text-green-400" />
      case 'error': return <AlertTriangle className="w-5 h-5 text-red-400" />
      case 'available': return <Plus className="w-5 h-5 text-gray-400" />
      default: return <XCircle className="w-5 h-5 text-gray-400" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected': return 'border-green-500/50 bg-green-500/5'
      case 'error': return 'border-red-500/50 bg-red-500/5'
      default: return 'border-gray-700 hover:border-gray-600'
    }
  }

  // Get integration logo/icon placeholder
  const getIntegrationIcon = (integration: Integration) => {
    const iconMap: Record<string, React.ReactNode> = {
      slack: <MessageSquare className="w-8 h-8" />,
      pagerduty: <Bell className="w-8 h-8" />,
      jira: <GitBranch className="w-8 h-8" />,
      github: <GitBranch className="w-8 h-8" />,
      aws: <Cloud className="w-8 h-8" />,
      gcp: <Cloud className="w-8 h-8" />,
      azure: <Cloud className="w-8 h-8" />,
      teams: <MessageSquare className="w-8 h-8" />,
      opsgenie: <Bell className="w-8 h-8" />,
      datadog: <BarChart className="w-8 h-8" />,
      splunk: <Database className="w-8 h-8" />,
      crowdstrike: <Shield className="w-8 h-8" />,
      okta: <Shield className="w-8 h-8" />,
      servicenow: <GitBranch className="w-8 h-8" />,
      webhook: <Zap className="w-8 h-8" />
    }
    return iconMap[integration.id] || <Puzzle className="w-8 h-8" />
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Integrations</h1>
            <p className="text-gray-400 mt-1">Connect Logforge with your favorite tools</p>
          </div>
          <button
            onClick={loadIntegrations}
            className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-500/20 rounded-lg">
                <Puzzle className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <p className="text-gray-400 text-sm">Total Integrations</p>
                <p className="text-2xl font-bold text-white">{stats.total}</p>
              </div>
            </div>
          </div>
          <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-500/20 rounded-lg">
                <CheckCircle className="w-5 h-5 text-green-400" />
              </div>
              <div>
                <p className="text-gray-400 text-sm">Connected</p>
                <p className="text-2xl font-bold text-white">{stats.connected}</p>
              </div>
            </div>
          </div>
          <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gray-500/20 rounded-lg">
                <Plus className="w-5 h-5 text-gray-400" />
              </div>
              <div>
                <p className="text-gray-400 text-sm">Available</p>
                <p className="text-2xl font-bold text-white">{stats.available}</p>
              </div>
            </div>
          </div>
          <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-500/20 rounded-lg">
                <AlertTriangle className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <p className="text-gray-400 text-sm">Errors</p>
                <p className="text-2xl font-bold text-white">{stats.errors}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-4 items-center">
          <div className="relative flex-1 min-w-[200px] max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search integrations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Categories</option>
            <option value="alerting">Alerting</option>
            <option value="ticketing">Ticketing</option>
            <option value="communication">Communication</option>
            <option value="cloud">Cloud</option>
            <option value="security">Security</option>
            <option value="data">Data</option>
          </select>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Status</option>
            <option value="connected">Connected</option>
            <option value="available">Available</option>
            <option value="error">Errors</option>
          </select>
        </div>

        {/* Integration Grid */}
        {isLoading ? (
          <div className="flex items-center justify-center h-48">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        ) : filteredIntegrations.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 bg-gray-800/50 border border-gray-700 rounded-lg">
            <Puzzle className="w-12 h-12 text-gray-500 mb-4" />
            <h3 className="text-lg font-medium text-white mb-2">
              {integrations.length === 0 ? 'No integrations configured' : 'No matching integrations'}
            </h3>
            <p className="text-gray-400 text-sm text-center max-w-md">
              {integrations.length === 0
                ? 'Connect your favorite tools to Logforge to start receiving alerts and syncing data.'
                : 'Try adjusting your search or filter criteria.'}
            </p>
            {integrations.length === 0 && (
              <button
                onClick={loadIntegrations}
                className="mt-4 flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredIntegrations.map((integration) => (
              <div
                key={integration.id}
                className={`bg-gray-800/50 border rounded-lg p-4 cursor-pointer transition-all hover:bg-gray-800/70 ${getStatusColor(integration.status)}`}
                onClick={() => {
                  setSelectedIntegration(integration)
                  setShowConfigModal(true)
                }}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${CATEGORY_COLORS[integration.category]}`}>
                      {getIntegrationIcon(integration)}
                    </div>
                    <div>
                      <h3 className="text-white font-medium">{integration.name}</h3>
                      <span className={`px-2 py-0.5 rounded text-xs ${CATEGORY_COLORS[integration.category]}`}>
                        {integration.category}
                      </span>
                    </div>
                  </div>
                  {getStatusIcon(integration.status)}
                </div>
                <p className="text-gray-400 text-sm mt-3">{integration.description}</p>
                <div className="flex flex-wrap gap-1 mt-3">
                  {integration.features.slice(0, 3).map((feature, idx) => (
                    <span key={idx} className="px-2 py-0.5 bg-gray-700 rounded text-xs text-gray-300">
                      {feature}
                    </span>
                  ))}
                  {integration.features.length > 3 && (
                    <span className="px-2 py-0.5 bg-gray-700 rounded text-xs text-gray-400">
                      +{integration.features.length - 3}
                    </span>
                  )}
                </div>
                {integration.status === 'connected' && integration.lastSync && (
                  <p className="text-gray-500 text-xs mt-3">
                    Last synced: {formatTimeAgo(integration.lastSync)}
                  </p>
                )}
                {integration.status === 'error' && (
                  <p className="text-red-400 text-xs mt-3 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    Connection error - click to fix
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Configuration Modal */}
        {showConfigModal && selectedIntegration && (
          <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
            <div className="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between p-4 border-b border-gray-700">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${CATEGORY_COLORS[selectedIntegration.category]}`}>
                    {getIntegrationIcon(selectedIntegration)}
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">{selectedIntegration.name}</h3>
                    <span className={`px-2 py-0.5 rounded text-xs ${CATEGORY_COLORS[selectedIntegration.category]}`}>
                      {selectedIntegration.category}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setShowConfigModal(false)}
                  className="text-gray-400 hover:text-white"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="p-4 space-y-4">
                <p className="text-gray-300">{selectedIntegration.description}</p>

                {/* Status */}
                <div className={`flex items-center gap-2 p-3 rounded-lg ${
                  selectedIntegration.status === 'connected' ? 'bg-green-500/10 border border-green-500/30' :
                  selectedIntegration.status === 'error' ? 'bg-red-500/10 border border-red-500/30' :
                  'bg-gray-700/50 border border-gray-600'
                }`}>
                  {getStatusIcon(selectedIntegration.status)}
                  <span className={`font-medium ${
                    selectedIntegration.status === 'connected' ? 'text-green-400' :
                    selectedIntegration.status === 'error' ? 'text-red-400' :
                    'text-gray-300'
                  }`}>
                    {selectedIntegration.status === 'connected' ? 'Connected' :
                     selectedIntegration.status === 'error' ? 'Connection Error' :
                     'Not Connected'}
                  </span>
                  {selectedIntegration.lastSync && (
                    <span className="text-gray-500 text-sm ml-auto">
                      Last sync: {formatTimeAgo(selectedIntegration.lastSync)}
                    </span>
                  )}
                </div>

                {/* Features */}
                <div>
                  <h4 className="text-white font-medium mb-2">Features</h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedIntegration.features.map((feature, idx) => (
                      <span key={idx} className="px-3 py-1 bg-gray-700 rounded-full text-sm text-gray-300">
                        {feature}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Configuration Form */}
                {selectedIntegration.status === 'available' ? (
                  <div className="border border-gray-600 rounded-lg p-4">
                    <h4 className="text-white font-medium mb-3">Connect {selectedIntegration.name}</h4>
                    {selectedIntegration.id === 'slack' && (
                      <div className="space-y-3">
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">Webhook URL</label>
                          <input
                            type="text"
                            placeholder="https://hooks.slack.com/services/..."
                            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 text-sm"
                          />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">Default Channel</label>
                          <input
                            type="text"
                            placeholder="#alerts"
                            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 text-sm"
                          />
                        </div>
                      </div>
                    )}
                    {selectedIntegration.id === 'pagerduty' && (
                      <div className="space-y-3">
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">API Key</label>
                          <input
                            type="password"
                            placeholder="Enter your PagerDuty API key"
                            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 text-sm"
                          />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">Service ID</label>
                          <input
                            type="text"
                            placeholder="PXXXXXX"
                            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 text-sm"
                          />
                        </div>
                      </div>
                    )}
                    {!['slack', 'pagerduty'].includes(selectedIntegration.id) && (
                      <div className="space-y-3">
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">API Key / Token</label>
                          <input
                            type="password"
                            placeholder="Enter your API key"
                            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 text-sm"
                          />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">Endpoint URL (optional)</label>
                          <input
                            type="text"
                            placeholder="https://api.example.com"
                            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 text-sm"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                ) : selectedIntegration.status === 'connected' && selectedIntegration.config && (
                  <div className="border border-gray-600 rounded-lg p-4">
                    <h4 className="text-white font-medium mb-3">Configuration</h4>
                    <div className="space-y-2">
                      {Object.entries(selectedIntegration.config).map(([key, value]) => (
                        <div key={key} className="flex justify-between">
                          <span className="text-gray-400 capitalize">{key.replace(/_/g, ' ')}</span>
                          <span className="text-white">
                            {Array.isArray(value) ? value.join(', ') : String(value)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Documentation Link */}
                <a
                  href={selectedIntegration.docsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-blue-400 hover:text-blue-300 text-sm"
                >
                  <ExternalLink className="w-4 h-4" />
                  View Documentation
                </a>
              </div>

              <div className="flex justify-end gap-3 p-4 border-t border-gray-700">
                <button
                  onClick={() => setShowConfigModal(false)}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
                >
                  Close
                </button>
                {selectedIntegration.status === 'connected' && (
                  <>
                    <button
                      onClick={() => testConnection(selectedIntegration.id)}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
                    >
                      Test Connection
                    </button>
                    <button
                      onClick={() => {
                        disconnectIntegration(selectedIntegration.id)
                        setShowConfigModal(false)
                      }}
                      className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
                    >
                      Disconnect
                    </button>
                  </>
                )}
                {selectedIntegration.status === 'available' && (
                  <button className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors">
                    Connect
                  </button>
                )}
                {selectedIntegration.status === 'error' && (
                  <button
                    onClick={() => testConnection(selectedIntegration.id)}
                    className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg transition-colors"
                  >
                    Retry Connection
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
