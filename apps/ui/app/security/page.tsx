'use client'

import React, { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { SecurityApi, SecurityEvent, SigmaRule, ThreatIntelIndicator, SecurityDashboard, ThreatHuntingCampaign } from '@/lib/api/security'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { 
  Shield, 
  AlertTriangle, 
  Search, 
  Eye, 
  Play, 
  Pause, 
  RefreshCw,
  Filter,
  Download,
  Bell,
  Target,
  TrendingUp,
  Activity,
  Clock,
  User,
  ExternalLink,
  ChevronRight
} from 'lucide-react'
import Link from 'next/link'

interface SecurityPageProps {}

interface SecurityEventCardProps {
  event: SecurityEvent
  onStatusUpdate: (eventId: string, status: SecurityEvent['status']) => void
}

const SecurityEventCard: React.FC<SecurityEventCardProps> = ({ event, onStatusUpdate }) => {
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
      case 'investigating': return 'bg-yellow-100 text-yellow-800'
      case 'resolved': return 'bg-green-100 text-green-800'
      case 'false_positive': return 'bg-gray-100 text-gray-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <Shield className="w-5 h-5 text-red-600" />
            <div>
              <CardTitle className="text-lg">{event.rule_name}</CardTitle>
              <CardDescription className="text-sm">{event.description}</CardDescription>
            </div>
          </div>
          <Badge className={getSeverityColor(event.severity)}>
            {event.severity.toUpperCase()}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Badge className={getStatusColor(event.status)}>
              {event.status.replace('_', ' ').toUpperCase()}
            </Badge>
            <span className="text-sm text-gray-500">
              {new Date(event.timestamp).toLocaleString()}
            </span>
          </div>
          
          {event.mitre_technique && (
            <div className="flex items-center space-x-2">
              <Target className="w-4 h-4 text-gray-500" />
              <span className="text-sm font-medium">MITRE {event.mitre_technique}</span>
            </div>
          )}
          
          {event.source_ip && (
            <div className="text-sm text-gray-600">
              Source: {event.source_ip}
              {event.target_ip && ` → ${event.target_ip}`}
            </div>
          )}
          
          <div className="flex space-x-2">
            <Button 
              size="sm" 
              variant="outline"
              onClick={() => onStatusUpdate(event.id, 'investigating')}
              disabled={event.status === 'investigating'}
            >
              <Eye className="w-4 h-4 mr-1" />
              Investigate
            </Button>
            <Button 
              size="sm" 
              variant="outline"
              onClick={() => onStatusUpdate(event.id, 'resolved')}
              disabled={event.status === 'resolved'}
            >
              Resolve
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function SecurityAnalyticsPage(): React.ReactElement {
  const { user, tenant } = useAuth()
  const [dashboard, setDashboard] = useState<SecurityDashboard | null>(null)
  const [securityEvents, setSecurityEvents] = useState<SecurityEvent[]>([])
  const [sigmaRules, setSigmaRules] = useState<SigmaRule[]>([])
  const [threatIntel, setThreatIntel] = useState<ThreatIntelIndicator[]>([])
  const [threatHunts, setThreatHunts] = useState<ThreatHuntingCampaign[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [refreshing, setRefreshing] = useState<Set<string>>(new Set())

  useEffect(() => {
    loadSecurityData()
  }, [])

  const loadSecurityData = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const [dashboardResponse, eventsResponse, rulesResponse, threatIntelResponse] = await Promise.all([
        SecurityApi.getSecurityDashboard('24h'),
        SecurityApi.listSecurityEvents({ limit: 20 }),
        SecurityApi.listSigmaRules({ limit: 50 }),
        SecurityApi.getThreatIntelligence({ limit: 20 })
      ])
      
      if (dashboardResponse.success) {
        setDashboard(dashboardResponse.data)
      }
      
      if (eventsResponse.success && eventsResponse.data) {
        setSecurityEvents(eventsResponse.data || [])
      }
      
      if (rulesResponse.success && rulesResponse.data) {
        setSigmaRules(rulesResponse.data || [])
      }
      
      if (threatIntelResponse.success && threatIntelResponse.data) {
        setThreatIntel(threatIntelResponse.data || [])
      }
    } catch (err: any) {
      console.error('Failed to load security data:', err)
      setError(err.message || 'Failed to load security data')
    } finally {
      setLoading(false)
    }
  }

  const updateEventStatus = async (eventId: string, status: SecurityEvent['status']) => {
    try {
      setRefreshing(prev => new Set(prev).add(eventId))
      
      const response = await SecurityApi.updateEventStatus(eventId, status)
      
      if (response.success) {
        // Update local state
        setSecurityEvents(prev => 
          prev.map(event => 
            event.id === eventId ? { ...event, status } : event
          )
        )
        
        // Refresh dashboard to update counts
        const dashboardResponse = await SecurityApi.getSecurityDashboard('24h')
        if (dashboardResponse.success) {
          setDashboard(dashboardResponse.data)
        }
      }
    } catch (err: any) {
      console.error('Failed to update event status:', err)
      setError(err.message || 'Failed to update event status')
    } finally {
      setRefreshing(prev => {
        const newSet = new Set(prev)
        newSet.delete(eventId)
        return newSet
      })
    }
  }

  const toggleSigmaRule = async (ruleId: string, enabled: boolean) => {
    try {
      const response = await SecurityApi.toggleSigmaRule(ruleId, enabled)
      
      if (response.success) {
        setSigmaRules(prev => 
          prev.map(rule => 
            rule.id === ruleId ? { ...rule, status: enabled ? 'enabled' : 'disabled' } : rule
          )
        )
      }
    } catch (err: any) {
      console.error('Failed to toggle rule:', err)
      setError(err.message || 'Failed to toggle rule')
    }
  }

  const testSigmaRule = async (ruleId: string) => {
    try {
      setLoading(true)
      const response = await SecurityApi.testSigmaRule(ruleId, { time_range: '1h' })
      
      if (response.success && response.data) {
        alert(`Rule Test Results:\n\nMatches: ${response.data.matches}\nExecution Time: ${response.data.performance.execution_time}ms\n\nRecommendations: ${response.data.recommendations.join(', ')}`)
      }
    } catch (err: any) {
      console.error('Failed to test rule:', err)
      setError(err.message || 'Failed to test rule')
    } finally {
      setLoading(false)
    }
  }

  const createThreatHunt = async () => {
    try {
      const response = await SecurityApi.createThreatHunt({
        name: `Threat Hunt - ${new Date().toLocaleString()}`,
        hypothesis: 'Proactive threat hunting across security events',
        query: 'severity:(high OR critical)',
        time_range: '24h',
        created_by: user?.id || 'unknown'
      })
      
      if (response.success) {
        // Refresh threat hunts
        const huntsResponse = await SecurityApi.listThreatHunts({ limit: 10 })
        if (huntsResponse.success && huntsResponse.data) {
          setThreatHunts(huntsResponse.data)
        }
      }
    } catch (err: any) {
      console.error('Failed to create threat hunt:', err)
      setError(err.message || 'Failed to create threat hunt')
    }
  }

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <div className="flex items-center space-x-2">
            <RefreshCw className="w-6 h-6 animate-spin" />
            <span>Loading security analytics...</span>
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
            <h1 className="text-2xl font-bold text-gray-900">Security Operations Center</h1>
            <p className="text-gray-600 mt-1">
              Detect, investigate, and respond to security threats using advanced SIEM capabilities
            </p>
          </div>
          <div className="flex space-x-2">
            <Button variant="outline" onClick={loadSecurityData}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
            <Button onClick={createThreatHunt}>
              <Search className="w-4 h-4 mr-2" />
              Start Threat Hunt
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

        {/* Security Overview Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <Bell className="w-8 h-8 text-red-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">Security Events</p>
                  <p className="text-2xl font-bold text-gray-900">{dashboard?.events_last_24h || 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <AlertTriangle className="w-8 h-8 text-orange-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">Critical Events</p>
                  <p className="text-2xl font-bold text-gray-900">{dashboard?.events_by_severity?.critical || 0}</p>
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
                  <p className="text-2xl font-bold text-gray-900">{sigmaRules.filter(r => r.status === 'enabled').length}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <TrendingUp className="w-8 h-8 text-blue-600" />
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-600">Security Score</p>
                  <p className="text-2xl font-bold text-gray-900">{dashboard?.security_posture_score || 0}%</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Security Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="events">Security Events ({securityEvents.length})</TabsTrigger>
            <TabsTrigger value="rules">Detection Rules ({sigmaRules.length})</TabsTrigger>
            <TabsTrigger value="threat-intel">Threat Intelligence ({threatIntel.length})</TabsTrigger>
            <TabsTrigger value="hunting">Threat Hunting</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Events by Severity */}
              <Card>
                <CardHeader>
                  <CardTitle>Events by Severity</CardTitle>
                  <CardDescription>Security event distribution over the last 24 hours</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {Object.entries(dashboard?.events_by_severity || {}).map(([severity, count]) => {
                      const getSeverityColor = (sev: string) => {
                        switch (sev) {
                          case 'critical': return 'bg-red-500'
                          case 'high': return 'bg-orange-500'
                          case 'medium': return 'bg-yellow-500'
                          case 'low': return 'bg-blue-500'
                          default: return 'bg-gray-500'
                        }
                      }
                      
                      const total = Object.values(dashboard?.events_by_severity || {}).reduce((a, b) => a + b, 0)
                      const percentage = total > 0 ? (count / total) * 100 : 0
                      
                      return (
                        <div key={severity} className="flex items-center space-x-3">
                          <div className="w-12 text-sm font-medium capitalize">{severity}</div>
                          <div className="flex-1 bg-gray-200 rounded-full h-2">
                            <div 
                              className={`h-2 rounded-full ${getSeverityColor(severity)}`}
                              style={{ width: `${percentage}%` }}
                            />
                          </div>
                          <div className="w-8 text-sm font-bold">{count}</div>
                        </div>
                      )
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* MITRE ATT&CK Techniques */}
              <Card>
                <CardHeader>
                  <CardTitle>MITRE ATT&CK Techniques</CardTitle>
                  <CardDescription>Most detected attack techniques</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {dashboard?.mitre_techniques?.slice(0, 5).map((technique) => (
                      <div key={technique.technique} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                        <div>
                          <div className="font-medium">{technique.technique}</div>
                          <div className="text-sm text-gray-600">{technique.description}</div>
                        </div>
                        <Badge variant="secondary">{technique.count}</Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="events" className="mt-6">
            {securityEvents.length === 0 ? (
              <Card>
                <CardContent className="p-8 text-center">
                  <Shield className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    No security events found
                  </h3>
                  <p className="text-gray-600">
                    Your security monitoring is active but no events have been detected in the last 24 hours
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {securityEvents.map((event) => (
                  <SecurityEventCard
                    key={event.id}
                    event={event}
                    onStatusUpdate={updateEventStatus}
                  />
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="rules" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Sigma Detection Rules</CardTitle>
                <CardDescription>Manage and monitor your security detection rules</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {sigmaRules.map((rule) => (
                    <div key={rule.id} className="flex items-center justify-between p-4 border rounded-lg">
                      <div className="flex-1">
                        <div className="flex items-center space-x-2">
                          <h4 className="font-medium">{rule.title}</h4>
                          <Badge 
                            className={rule.status === 'enabled' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}
                          >
                            {rule.status}
                          </Badge>
                          <Badge variant="outline">{rule.severity}</Badge>
                        </div>
                        <p className="text-sm text-gray-600 mt-1">{rule.description}</p>
                        {rule.mitre_technique && (
                          <p className="text-xs text-gray-500 mt-1">MITRE {rule.mitre_technique}</p>
                        )}
                      </div>
                      <div className="flex space-x-2">
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => testSigmaRule(rule.id)}
                        >
                          <Play className="w-4 h-4 mr-1" />
                          Test
                        </Button>
                        <Button 
                          size="sm" 
                          variant={rule.status === 'enabled' ? "secondary" : "default"}
                          onClick={() => toggleSigmaRule(rule.id, rule.status !== 'enabled')}
                        >
                          {rule.status === 'enabled' ? (
                            <><Pause className="w-4 h-4 mr-1" /> Disable</>
                          ) : (
                            <><Play className="w-4 h-4 mr-1" /> Enable</>
                          )}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="threat-intel" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Threat Intelligence Feed</CardTitle>
                <CardDescription>Known threat indicators and intelligence sources</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {threatIntel.map((indicator) => (
                    <div key={indicator.id} className="flex items-center justify-between p-4 border rounded-lg">
                      <div className="flex-1">
                        <div className="flex items-center space-x-2">
                          <code className="font-mono text-sm bg-gray-100 px-2 py-1 rounded">
                            {indicator.value}
                          </code>
                          <Badge variant="outline">{indicator.type}</Badge>
                          <Badge className={`${
                            indicator.confidence >= 90 ? 'bg-green-100 text-green-800' :
                            indicator.confidence >= 70 ? 'bg-yellow-100 text-yellow-800' :
                            'bg-red-100 text-red-800'
                          }`}>
                            {indicator.confidence}% confidence
                          </Badge>
                        </div>
                        <p className="text-sm text-gray-600 mt-1">{indicator.description}</p>
                        <div className="flex items-center space-x-4 mt-2 text-xs text-gray-500">
                          <span>Source: {indicator.source}</span>
                          <span>Threat: {indicator.threat_type}</span>
                          <span>First seen: {new Date(indicator.first_seen).toLocaleDateString()}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="hunting" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Threat Hunting Operations</CardTitle>
                <CardDescription>Proactively hunt for advanced threats and suspicious activities</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-8">
                  <Search className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    Ready to Hunt Threats
                  </h3>
                  <p className="text-gray-600 mb-4">
                    Execute threat hunting campaigns to proactively identify security threats
                  </p>
                  <Button onClick={createThreatHunt}>
                    <Search className="w-4 h-4 mr-2" />
                    Start New Hunt
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