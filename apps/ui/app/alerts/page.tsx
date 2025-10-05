'use client'

import React, { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { AlertsApi, Alert, AlertEvent, AlertTemplate } from '@/lib/api/alerts'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert as AlertComponent, AlertDescription } from '@/components/ui/alert'
import { 
  Bell, 
  AlertTriangle, 
  Play, 
  Pause, 
  RefreshCw,
  Plus,
  Eye,
  CheckCircle,
  XCircle,
  Clock,
  Settings,
  Target,
  TrendingUp,
  Activity,
  Zap,
  Shield,
  ExternalLink,
  Filter,
  Download,
  MoreVertical
} from 'lucide-react'

interface AlertRuleCardProps {
  alert: Alert
  onToggle: (alertId: string, enabled: boolean) => void
  onTest: (alertId: string) => void
  onEdit: (alert: Alert) => void
}

const AlertRuleCard: React.FC<AlertRuleCardProps> = ({ alert, onToggle, onTest, onEdit }) => {
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-200'
      case 'high': return 'bg-orange-100 text-orange-800 border-orange-200'
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-200'
      case 'low': return 'bg-blue-100 text-blue-800 border-blue-200'
      default: return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800'
      case 'paused': return 'bg-yellow-100 text-yellow-800'
      case 'disabled': return 'bg-gray-100 text-gray-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getRuleTypeIcon = (ruleType: string) => {
    switch (ruleType) {
      case 'threshold': return <Target className="w-4 h-4" />
      case 'anomaly': return <TrendingUp className="w-4 h-4" />
      case 'pattern': return <Activity className="w-4 h-4" />
      case 'frequency': return <Zap className="w-4 h-4" />
      case 'absence': return <XCircle className="w-4 h-4" />
      case 'sequence': return <Shield className="w-4 h-4" />
      default: return <Bell className="w-4 h-4" />
    }
  }

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            {getRuleTypeIcon(alert.rule_type)}
            <div>
              <CardTitle className="text-lg">{alert.name}</CardTitle>
              <CardDescription className="text-sm">{alert.description}</CardDescription>
            </div>
          </div>
          <div className="flex space-x-2">
            <Badge className={getSeverityColor(alert.severity)}>
              {alert.severity.toUpperCase()}
            </Badge>
            <Badge className={getStatusColor(alert.status)}>
              {alert.status.toUpperCase()}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div className="text-sm text-gray-600">
            <strong>Rule Type:</strong> {alert.rule_type.charAt(0).toUpperCase() + alert.rule_type.slice(1)}
          </div>
          
          <div className="text-sm text-gray-600">
            <strong>Query:</strong> <code className="bg-gray-100 px-2 py-1 rounded text-xs">{alert.query}</code>
          </div>
          
          <div className="flex items-center justify-between text-sm text-gray-500">
            <span className="flex items-center">
              <Clock className="w-4 h-4 mr-1" />
              Triggered {alert.triggered_count} times
            </span>
            <span>
              {alert.last_triggered ? `Last: ${new Date(alert.last_triggered).toLocaleDateString()}` : 'Never triggered'}
            </span>
          </div>
          
          {alert.channels && alert.channels.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {alert.channels.map((channel, index) => (
                <Badge key={index} variant="outline" className="text-xs">
                  {channel.type}
                </Badge>
              ))}
            </div>
          )}
          
          <div className="flex space-x-2">
            <Button 
              size="sm" 
              variant="outline"
              onClick={() => onTest(alert.id)}
            >
              <Play className="w-4 h-4 mr-1" />
              Test
            </Button>
            <Button 
              size="sm" 
              variant="outline"
              onClick={() => onEdit(alert)}
            >
              <Settings className="w-4 h-4 mr-1" />
              Edit
            </Button>
            <Button 
              size="sm" 
              variant={alert.status === 'active' ? "secondary" : "default"}
              onClick={() => onToggle(alert.id, alert.status !== 'active')}
            >
              {alert.status === 'active' ? (
                <><Pause className="w-4 h-4 mr-1" /> Pause</>
              ) : (
                <><Play className="w-4 h-4 mr-1" /> Activate</>
              )}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

interface AlertEventCardProps {
  event: AlertEvent
  onAcknowledge: (eventId: string) => void
  onResolve: (eventId: string) => void
}

const AlertEventCard: React.FC<AlertEventCardProps> = ({ event, onAcknowledge, onResolve }) => {
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-200'
      case 'high': return 'bg-orange-100 text-orange-800 border-orange-200'
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-200'
      case 'low': return 'bg-blue-100 text-blue-800 border-blue-200'
      default: return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'new': return 'bg-red-100 text-red-800'
      case 'acknowledged': return 'bg-yellow-100 text-yellow-800'
      case 'resolved': return 'bg-green-100 text-green-800'
      case 'suppressed': return 'bg-gray-100 text-gray-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getDuration = () => {
    const start = new Date(event.triggered_at)
    const end = event.resolved_at ? new Date(event.resolved_at) : new Date()
    const diffMs = end.getTime() - start.getTime()
    const diffMins = Math.floor(diffMs / (1000 * 60))
    const diffHours = Math.floor(diffMins / 60)
    
    if (diffHours > 0) {
      return `${diffHours}h ${diffMins % 60}m`
    }
    return `${diffMins}m`
  }

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <AlertTriangle className="w-5 h-5 text-orange-600" />
            <div>
              <CardTitle className="text-lg">{event.alert_name}</CardTitle>
              <CardDescription className="text-sm">Alert ID: {event.alert_id}</CardDescription>
            </div>
          </div>
          <div className="flex space-x-2">
            <Badge className={getSeverityColor(event.severity)}>
              {event.severity.toUpperCase()}
            </Badge>
            <Badge className={getStatusColor(event.status)}>
              {event.status.toUpperCase()}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm text-gray-500">
            <span className="flex items-center">
              <Clock className="w-4 h-4 mr-1" />
              Duration: {getDuration()}
            </span>
            <span>
              Triggered: {new Date(event.triggered_at).toLocaleString()}
            </span>
          </div>
          
          {event.acknowledged_by && (
            <div className="text-sm text-gray-600">
              <strong>Acknowledged by:</strong> {event.acknowledged_by} at {new Date(event.acknowledged_at!).toLocaleString()}
            </div>
          )}
          
          {event.notifications_sent && event.notifications_sent.length > 0 && (
            <div className="flex items-center space-x-2">
              <span className="text-sm text-gray-600">Notifications:</span>
              {event.notifications_sent.map((notification, index) => (
                <Badge 
                  key={index} 
                  variant="outline" 
                  className={`text-xs ${notification.status === 'sent' ? 'border-green-400' : 'border-red-400'}`}
                >
                  {notification.channel_type}
                </Badge>
              ))}
            </div>
          )}
          
          <div className="flex space-x-2">
            {event.status === 'triggered' && (
              <Button 
                size="sm" 
                variant="outline"
                onClick={() => onAcknowledge(event.id)}
              >
                <Eye className="w-4 h-4 mr-1" />
                Acknowledge
              </Button>
            )}
            {event.status !== 'resolved' && (
              <Button 
                size="sm" 
                variant="outline"
                onClick={() => onResolve(event.id)}
              >
                <CheckCircle className="w-4 h-4 mr-1" />
                Resolve
              </Button>
            )}
            <Button size="sm" variant="outline">
              <ExternalLink className="w-4 h-4 mr-1" />
              View Details
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function AlertsPage(): React.ReactElement {
  const { user, tenant } = useAuth()
  const [alertRules, setAlertRules] = useState<Alert[]>([])
  const [alertEvents, setAlertEvents] = useState<AlertEvent[]>([])
  const [alertTemplates, setAlertTemplates] = useState<AlertTemplate[]>([])
  const [alertStats, setAlertStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [refreshing, setRefreshing] = useState<Set<string>>(new Set())

  useEffect(() => {
    loadAlertData()
  }, [])

  const loadAlertData = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const [rulesResponse, eventsResponse, templatesResponse, statsResponse] = await Promise.all([
        AlertsApi.listAlertRules({ limit: 50 }),
        AlertsApi.listAlertEvents({ limit: 20 }),
        AlertsApi.getAlertTemplates(),
        AlertsApi.getAlertStats('24h')
      ])
      
      if (rulesResponse && rulesResponse.data) {
        setAlertRules(rulesResponse.data || [])
      }
      
      if (eventsResponse && eventsResponse.data) {
        setAlertEvents(eventsResponse.data || [])
      }
      
      if (templatesResponse && templatesResponse.data) {
        setAlertTemplates(templatesResponse.data || [])
      }
      
      if (statsResponse && statsResponse.data) {
        setAlertStats(statsResponse.data)
      }
    } catch (err: any) {
      console.error('Failed to load alert data:', err)
      setError(err.message || 'Failed to load alert data')
    } finally {
      setLoading(false)
    }
  }

  const toggleAlertRule = async (alertId: string, enabled: boolean) => {
    try {
      setRefreshing(prev => new Set(prev).add(alertId))
      
      const response = await AlertsApi.toggleAlertRule(alertId, enabled)
      
      if (response.success) {
        setAlertRules(prev => 
          prev.map(alert => 
            alert.id === alertId ? { ...alert, status: enabled ? 'active' : 'paused' } : alert
          )
        )
      }
    } catch (err: any) {
      console.error('Failed to toggle alert rule:', err)
      setError(err.message || 'Failed to toggle alert rule')
    } finally {
      setRefreshing(prev => {
        const newSet = new Set(prev)
        newSet.delete(alertId)
        return newSet
      })
    }
  }

  const testAlertRule = async (alertId: string) => {
    try {
      setLoading(true)
      const response = await AlertsApi.testAlertRule(alertId, { time_range: '1h' })
      
      if (response.success && response.data) {
        alert(`Alert Test Results:\n\nWould Trigger: ${response.data.would_trigger ? 'Yes' : 'No'}\nMatches: ${response.data.matches}\nExecution Time: ${response.data.execution_time}ms\nNext Evaluation: ${new Date(response.data.next_evaluation).toLocaleString()}`)
      }
    } catch (err: any) {
      console.error('Failed to test alert rule:', err)
      setError(err.message || 'Failed to test alert rule')
    } finally {
      setLoading(false)
    }
  }

  const acknowledgeAlert = async (eventId: string) => {
    try {
      const response = await AlertsApi.acknowledgeAlert(eventId, 'Acknowledged from UI')
      
      if (response.success) {
        setAlertEvents(prev => 
          prev.map(event => 
            event.id === eventId ? { ...event, status: 'acknowledged', acknowledged_by: user?.email, acknowledged_at: new Date().toISOString() } : event
          )
        )
      }
    } catch (err: any) {
      console.error('Failed to acknowledge alert:', err)
      setError(err.message || 'Failed to acknowledge alert')
    }
  }

  const resolveAlert = async (eventId: string) => {
    try {
      const response = await AlertsApi.resolveAlert(eventId, 'Resolved from UI')
      
      if (response.success) {
        setAlertEvents(prev => 
          prev.map(event => 
            event.id === eventId ? { ...event, status: 'resolved', resolved_at: new Date().toISOString() } : event
          )
        )
      }
    } catch (err: any) {
      console.error('Failed to resolve alert:', err)
      setError(err.message || 'Failed to resolve alert')
    }
  }

  const editAlert = (alertRule: Alert) => {
    // TODO: Implement alert editing modal
    console.log('Edit alert:', alertRule)
    alert(`Edit Alert: ${alertRule.name}\n\nThis feature will open an alert configuration modal.`)
  }

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <div className="flex items-center space-x-2">
            <RefreshCw className="w-6 h-6 animate-spin" />
            <span>Loading alert management...</span>
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
            <h1 className="text-2xl font-bold text-gray-900">Alert Management</h1>
            <p className="text-gray-600 mt-1">
              Configure intelligent alerting rules and manage incident response workflows
            </p>
          </div>
          <div className="flex space-x-2">
            <Button variant="outline" onClick={loadAlertData}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
            <Button>
              <Plus className="w-4 h-4 mr-2" />
              Create Alert Rule
            </Button>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <AlertComponent>
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </AlertComponent>
        )}

        {/* Alert Statistics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <Bell className="w-8 h-8 text-blue-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">Total Rules</p>
                  <p className="text-2xl font-bold text-gray-900">{alertStats?.total_rules || 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <Activity className="w-8 h-8 text-green-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">Active Rules</p>
                  <p className="text-2xl font-bold text-gray-900">{alertStats?.active_rules || 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <AlertTriangle className="w-8 h-8 text-orange-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">Active Alerts</p>
                  <p className="text-2xl font-bold text-gray-900">{alertStats?.total_events || 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <Clock className="w-8 h-8 text-purple-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">Avg Resolution</p>
                  <p className="text-2xl font-bold text-gray-900">{alertStats?.mean_resolution_time || 0}m</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Alert Management Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="rules">Alert Rules ({alertRules.length})</TabsTrigger>
            <TabsTrigger value="events">Active Alerts ({alertEvents.filter(e => e.status !== 'resolved').length})</TabsTrigger>
            <TabsTrigger value="templates">Templates ({alertTemplates.length})</TabsTrigger>
            <TabsTrigger value="settings">Settings</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Alert Events by Severity */}
              <Card>
                <CardHeader>
                  <CardTitle>Alerts by Severity</CardTitle>
                  <CardDescription>Alert distribution over the last 24 hours</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {Object.entries(alertStats?.events_by_severity || {}).map(([severity, count]) => {
                      const getSeverityColor = (sev: string) => {
                        switch (sev) {
                          case 'critical': return 'bg-red-500'
                          case 'high': return 'bg-orange-500'
                          case 'medium': return 'bg-yellow-500'
                          case 'low': return 'bg-blue-500'
                          default: return 'bg-gray-500'
                        }
                      }
                      
                      const total = Object.values(alertStats?.events_by_severity || {}).reduce((a: number, b: any) => a + b, 0)
                      const percentage = total > 0 ? (count as number / total) * 100 : 0
                      
                      return (
                        <div key={severity} className="flex items-center space-x-3">
                          <div className="w-12 text-sm font-medium capitalize">{severity}</div>
                          <div className="flex-1 bg-gray-200 rounded-full h-2">
                            <div 
                              className={`h-2 rounded-full ${getSeverityColor(severity)}`}
                              style={{ width: `${percentage}%` }}
                            />
                          </div>
                          <div className="w-8 text-sm font-bold">{count as number}</div>
                        </div>
                      )
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* Top Triggered Rules */}
              <Card>
                <CardHeader>
                  <CardTitle>Most Triggered Rules</CardTitle>
                  <CardDescription>Rules generating the most alerts</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {alertStats?.top_triggered_rules?.slice(0, 5).map((rule: any, index: number) => (
                      <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                        <div>
                          <div className="font-medium">{rule.rule_name}</div>
                          <div className="text-sm text-gray-600">Alert rule</div>
                        </div>
                        <Badge variant="secondary">{rule.count}</Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="rules" className="mt-6">
            {alertRules.length === 0 ? (
              <Card>
                <CardContent className="p-8 text-center">
                  <Bell className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    No alert rules configured
                  </h3>
                  <p className="text-gray-600 mb-4">
                    Get started by creating your first alert rule to monitor your systems
                  </p>
                  <Button>
                    <Plus className="w-4 h-4 mr-2" />
                    Create Alert Rule
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {alertRules.map((alert) => (
                  <AlertRuleCard
                    key={alert.id}
                    alert={alert}
                    onToggle={toggleAlertRule}
                    onTest={testAlertRule}
                    onEdit={editAlert}
                  />
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="events" className="mt-6">
            {alertEvents.filter(e => e.status !== 'resolved').length === 0 ? (
              <Card>
                <CardContent className="p-8 text-center">
                  <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    No active alerts
                  </h3>
                  <p className="text-gray-600">
                    All systems are operating normally with no active alerts
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {alertEvents.filter(e => e.status !== 'resolved').map((event) => (
                  <AlertEventCard
                    key={event.id}
                    event={event}
                    onAcknowledge={acknowledgeAlert}
                    onResolve={resolveAlert}
                  />
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="templates" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Alert Templates</CardTitle>
                <CardDescription>Pre-configured alert templates for common use cases</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {alertTemplates.map((template) => (
                    <Card key={template.id} className="hover:shadow-md transition-shadow">
                      <CardHeader className="pb-3">
                        <CardTitle className="text-base">{template.name}</CardTitle>
                        <CardDescription className="text-sm">{template.description}</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2">
                          <Badge variant="outline">{template.category}</Badge>
                          <p className="text-xs text-gray-600">{template.use_case}</p>
                          <Button size="sm" className="w-full">
                            <Plus className="w-4 h-4 mr-1" />
                            Use Template
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="settings" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Alert Settings</CardTitle>
                <CardDescription>Configure global alert settings and notification preferences</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-8">
                  <Settings className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    Alert Configuration
                  </h3>
                  <p className="text-gray-600 mb-4">
                    Configure notification channels, escalation policies, and alert preferences
                  </p>
                  <Button>
                    <Settings className="w-4 h-4 mr-2" />
                    Configure Settings
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