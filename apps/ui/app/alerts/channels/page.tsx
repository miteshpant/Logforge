'use client'

import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import {
  Bell,
  Plus,
  Mail,
  MessageSquare,
  Webhook,
  Phone,
  Edit,
  Trash2,
  TestTube,
  CheckCircle,
  XCircle,
  Settings,
  X,
  AlertTriangle
} from 'lucide-react'

interface NotificationChannel {
  id: string
  name: string
  type: 'email' | 'slack' | 'pagerduty' | 'webhook' | 'teams' | 'opsgenie'
  enabled: boolean
  config: Record<string, any>
  created_at: string
  last_used_at?: string
  success_rate: number
}

const CHANNEL_ICONS: Record<string, React.ReactNode> = {
  email: <Mail className="w-5 h-5" />,
  slack: <MessageSquare className="w-5 h-5" />,
  pagerduty: <Phone className="w-5 h-5" />,
  webhook: <Webhook className="w-5 h-5" />,
  teams: <MessageSquare className="w-5 h-5" />,
  opsgenie: <Bell className="w-5 h-5" />
}

const CHANNEL_COLORS: Record<string, string> = {
  email: 'bg-blue-500/20 text-blue-400',
  slack: 'bg-purple-500/20 text-purple-400',
  pagerduty: 'bg-green-500/20 text-green-400',
  webhook: 'bg-orange-500/20 text-orange-400',
  teams: 'bg-indigo-500/20 text-indigo-400',
  opsgenie: 'bg-cyan-500/20 text-cyan-400'
}


export default function NotificationChannelsPage() {
  const [channels, setChannels] = useState<NotificationChannel[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedChannel, setSelectedChannel] = useState<NotificationChannel | null>(null)
  const [testingChannel, setTestingChannel] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [newChannelType, setNewChannelType] = useState('slack')
  const [newChannelName, setNewChannelName] = useState('')
  const [newChannelWebhook, setNewChannelWebhook] = useState('')
  const [newChannelTarget, setNewChannelTarget] = useState('')
  const [isCreating, setIsCreating] = useState(false)

  useEffect(() => {
    loadChannels()
  }, [])

  const loadChannels = async () => {
    try {
      setIsLoading(true)
      const response = await apiClient.get<{ channels: NotificationChannel[] }>('/v1/alerts/notifications/channels')
      if (response?.data?.channels) {
        setChannels(response.data.channels)
      } else if (Array.isArray(response?.data)) {
        setChannels(response.data)
      } else {
        setChannels([])
      }
    } catch (error) {
      console.error('Failed to load channels:', error)
      setChannels([])
    } finally {
      setIsLoading(false)
    }
  }

  const toggleChannel = async (channelId: string) => {
    const channel = channels.find(c => c.id === channelId)
    if (!channel) return

    try {
      await apiClient.put(`/v1/alerts/notifications/channels/${channelId}`, { enabled: !channel.enabled })
    } catch (error) {
      console.error('Failed to toggle channel:', error)
    }
    setChannels(channels.map(c =>
      c.id === channelId ? { ...c, enabled: !c.enabled } : c
    ))
  }

  const deleteChannel = async (channelId: string) => {
    if (!confirm('Are you sure you want to delete this notification channel?')) return

    try {
      await apiClient.delete(`/v1/alerts/notifications/channels/${channelId}`)
    } catch (error) {
      console.error('Failed to delete channel:', error)
    }
    setChannels(channels.filter(c => c.id !== channelId))
  }

  const createChannel = async () => {
    if (!newChannelName.trim()) return
    try {
      setIsCreating(true)
      const config: Record<string, any> = {}
      if (newChannelType === 'slack') {
        config.webhook_url = newChannelWebhook
        config.channel = newChannelTarget
      } else if (newChannelType === 'email') {
        config.recipients = newChannelTarget.split(',').map((e: string) => e.trim()).filter(Boolean)
      } else if (newChannelType === 'webhook') {
        config.url = newChannelWebhook
      } else if (newChannelType === 'pagerduty') {
        config.integration_key = newChannelWebhook
      } else if (newChannelType === 'teams') {
        config.webhook_url = newChannelWebhook
      }
      await apiClient.post('/v1/alerts/notifications/channels', {
        name: newChannelName,
        channel_type: newChannelType,
        config
      })
      setShowCreateModal(false)
      setNewChannelName('')
      setNewChannelWebhook('')
      setNewChannelTarget('')
      setNewChannelType('slack')
      await loadChannels()
    } catch (error) {
      console.error('Failed to create channel:', error)
    } finally {
      setIsCreating(false)
    }
  }

  const testChannel = async (channelId: string) => {
    setTestingChannel(channelId)
    setTestResult(null)

    try {
      const response = await apiClient.post(`/v1/alerts/notifications/channels/${channelId}/test`)
      setTestResult({ success: true, message: 'Test notification sent successfully!' })
    } catch (error) {
      console.error('Failed to test channel:', error)
      setTestResult({ success: false, message: 'Failed to send test notification. Check channel configuration.' })
    }

    setTimeout(() => {
      setTestingChannel(null)
      setTestResult(null)
    }, 3000)
  }

  const formatTimeAgo = (timestamp: string | undefined) => {
    if (!timestamp) return 'Never'
    const diff = Date.now() - new Date(timestamp).getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    const days = Math.floor(diff / 86400000)
    if (days > 0) return `${days}d ago`
    if (hours > 0) return `${hours}h ago`
    if (minutes > 0) return `${minutes}m ago`
    return 'Just now'
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Notification Channels</h1>
            <p className="text-slate-400 mt-1">Configure where alerts are sent</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Channel
          </button>
        </div>

        {/* Channel Types Overview */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
          {Object.entries(CHANNEL_ICONS).map(([type, icon]) => {
            const count = channels.filter(c => c.type === type).length
            const enabled = channels.filter(c => c.type === type && c.enabled).length
            return (
              <div key={type} className="bg-slate-800/50 border border-white/5 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${CHANNEL_COLORS[type]}`}>
                    {icon}
                  </div>
                  <div>
                    <p className="text-white font-medium capitalize">{type}</p>
                    <p className="text-slate-400 text-sm">{enabled}/{count} active</p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        {/* Channels List */}
        <div className="bg-slate-800/50 border border-white/5 rounded-lg overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
          ) : channels.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-slate-400">
              <Bell className="w-12 h-12 mb-4 opacity-50" />
              <p>No notification channels configured</p>
              <button
                onClick={() => setShowCreateModal(true)}
                className="mt-4 text-blue-400 hover:text-blue-300"
              >
                Add your first channel
              </button>
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-slate-900/50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase">Channel</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase">Type</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase">Last Used</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase">Success Rate</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-slate-400 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {channels.map((channel) => (
                  <tr key={channel.id} className="hover:bg-slate-700/30 transition-colors">
                    <td className="px-4 py-4">
                      <button
                        onClick={() => toggleChannel(channel.id)}
                        className={`relative w-10 h-6 rounded-full transition-colors ${
                          channel.enabled ? 'bg-green-500' : 'bg-slate-600'
                        }`}
                      >
                        <span className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                          channel.enabled ? 'left-5' : 'left-1'
                        }`} />
                      </button>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${CHANNEL_COLORS[channel.type]}`}>
                          {CHANNEL_ICONS[channel.type]}
                        </div>
                        <div>
                          <p className="text-white font-medium">{channel.name}</p>
                          <p className="text-slate-400 text-sm">
                            {channel.type === 'slack' && channel.config.channel}
                            {channel.type === 'email' && `${channel.config.recipients?.length || 0} recipients`}
                            {channel.type === 'webhook' && 'Custom endpoint'}
                            {channel.type === 'pagerduty' && 'PagerDuty Service'}
                            {channel.type === 'teams' && 'Teams Webhook'}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${CHANNEL_COLORS[channel.type]}`}>
                        {channel.type.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-slate-400">
                      {formatTimeAgo(channel.last_used_at)}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-slate-700 rounded-full max-w-[100px]">
                          <div
                            className={`h-full rounded-full ${
                              channel.success_rate >= 99 ? 'bg-green-500' :
                              channel.success_rate >= 95 ? 'bg-yellow-500' : 'bg-red-500'
                            }`}
                            style={{ width: `${channel.success_rate}%` }}
                          />
                        </div>
                        <span className={`text-sm ${
                          channel.success_rate >= 99 ? 'text-green-400' :
                          channel.success_rate >= 95 ? 'text-yellow-400' : 'text-red-400'
                        }`}>
                          {channel.success_rate}%
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center justify-end gap-1">
                        {testingChannel === channel.id ? (
                          <div className="flex items-center gap-2">
                            {testResult ? (
                              testResult.success ? (
                                <CheckCircle className="w-5 h-5 text-green-400" />
                              ) : (
                                <XCircle className="w-5 h-5 text-red-400" />
                              )
                            ) : (
                              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-500"></div>
                            )}
                          </div>
                        ) : (
                          <button
                            onClick={() => testChannel(channel.id)}
                            className="p-2 text-slate-400 hover:text-blue-400 hover:bg-slate-700 rounded transition-colors"
                            title="Test channel"
                          >
                            <TestTube className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => setSelectedChannel(channel)}
                          className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors"
                          title="Edit channel"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => deleteChannel(channel.id)}
                          className="p-2 text-slate-400 hover:text-red-400 hover:bg-slate-700 rounded transition-colors"
                          title="Delete channel"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Create Channel Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
            <div className="bg-slate-800 border border-white/5 rounded-lg w-full max-w-lg mx-4">
              <div className="flex items-center justify-between p-4 border-b border-white/5">
                <h3 className="text-lg font-semibold text-white">Add Notification Channel</h3>
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="text-slate-400 hover:text-white"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="p-4 space-y-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Channel Type</label>
                  <div className="grid grid-cols-3 gap-2">
                    {Object.entries(CHANNEL_ICONS).map(([type, icon]) => (
                      <button
                        key={type}
                        onClick={() => setNewChannelType(type)}
                        className={`flex items-center gap-2 p-3 rounded-lg border transition-colors ${
                          newChannelType === type ? 'border-blue-500 ring-1 ring-blue-500' : 'border-white/10 hover:border-blue-500'
                        } ${CHANNEL_COLORS[type]}`}
                      >
                        {icon}
                        <span className="capitalize text-sm">{type}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-slate-400 mb-1">Channel Name</label>
                  <input
                    type="text"
                    placeholder="e.g., Ops Team Slack"
                    value={newChannelName}
                    onChange={(e) => setNewChannelName(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-700 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                  />
                </div>

                <div className="bg-slate-700/50 border border-white/10 rounded-lg p-4">
                  <h4 className="text-white text-sm font-medium mb-3 capitalize">{newChannelType} Configuration</h4>
                  <div className="space-y-3">
                    {(newChannelType === 'slack' || newChannelType === 'webhook' || newChannelType === 'teams' || newChannelType === 'pagerduty') && (
                      <div>
                        <label className="block text-sm text-slate-400 mb-1">
                          {newChannelType === 'pagerduty' ? 'Integration Key' : 'Webhook URL'}
                        </label>
                        <input
                          type="text"
                          placeholder={newChannelType === 'pagerduty' ? 'PagerDuty integration key...' : 'https://hooks.example.com/...'}
                          value={newChannelWebhook}
                          onChange={(e) => setNewChannelWebhook(e.target.value)}
                          className="w-full px-3 py-2 bg-slate-800 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 text-sm"
                        />
                      </div>
                    )}
                    <div>
                      <label className="block text-sm text-slate-400 mb-1">
                        {newChannelType === 'slack' ? 'Channel' : newChannelType === 'email' ? 'Recipients (comma-separated)' : 'Target'}
                      </label>
                      <input
                        type="text"
                        placeholder={newChannelType === 'slack' ? '#alerts' : newChannelType === 'email' ? 'team@company.com, ops@company.com' : 'Target identifier'}
                        value={newChannelTarget}
                        onChange={(e) => setNewChannelTarget(e.target.value)}
                        className="w-full px-3 py-2 bg-slate-800 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 text-sm"
                      />
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                  <AlertTriangle className="w-5 h-5 text-blue-400" />
                  <p className="text-blue-300 text-sm">
                    A test notification will be sent after creation
                  </p>
                </div>
              </div>
              <div className="flex justify-end gap-3 p-4 border-t border-white/5">
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={createChannel}
                  disabled={isCreating || !newChannelName.trim()}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg transition-colors"
                >
                  {isCreating ? 'Creating...' : 'Create Channel'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
