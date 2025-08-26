'use client'
import { useEffect, useState } from 'react'
import { Play, Square, CheckCircle, XCircle, Clock, AlertCircle, Database, Shield, Activity, BarChart3 } from 'lucide-react'

interface TestResult {
  name: string
  status: 'running' | 'passed' | 'failed' | 'pending'
  duration?: number
  error?: string
  output?: string[]
  timestamp?: string
}

interface TestSuite {
  id: string
  name: string
  description: string
  category: string
  tests: TestResult[]
  totalTests: number
  passedTests: number
  failedTests: number
  runningTests: number
  lastRun?: string
}

const MOCK_TEST_SUITES: TestSuite[] = [
  {
    id: 'ingestion',
    name: 'M1 - Ingestion & Storage',
    description: 'Multi-format log ingestion and storage tests',
    category: 'Core',
    tests: [],
    totalTests: 12,
    passedTests: 0,
    failedTests: 0,
    runningTests: 0
  },
  {
    id: 'query-dashboard',
    name: 'M2 - Query & Dashboards',
    description: 'Advanced query engine and enterprise dashboard tests',
    category: 'Analytics',
    tests: [],
    totalTests: 18,
    passedTests: 0,
    failedTests: 0,
    runningTests: 0
  },
  {
    id: 'alert-engine',
    name: 'M3 - Alert Engine',
    description: 'Rule-based alerting and notification system tests',
    category: 'Monitoring',
    tests: [],
    totalTests: 24,
    passedTests: 0,
    failedTests: 0,
    runningTests: 0
  },
  {
    id: 'multi-tenant',
    name: 'Multi-Tenant Isolation',
    description: 'Customer isolation and security boundary tests',
    category: 'Security',
    tests: [],
    totalTests: 15,
    passedTests: 0,
    failedTests: 0,
    runningTests: 0
  },
  {
    id: 'performance',
    name: 'Performance Benchmarks',
    description: 'Throughput and latency performance validation',
    category: 'Performance',
    tests: [],
    totalTests: 8,
    passedTests: 0,
    failedTests: 0,
    runningTests: 0
  },
  {
    id: 'integration',
    name: 'End-to-End Integration',
    description: 'Complete workflow and system integration tests',
    category: 'Integration',
    tests: [],
    totalTests: 10,
    passedTests: 0,
    failedTests: 0,
    runningTests: 0
  }
]

export default function TestRunner() {
  const [testSuites, setTestSuites] = useState<TestSuite[]>(MOCK_TEST_SUITES)
  const [selectedSuite, setSelectedSuite] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [logs, setLogs] = useState<string[]>([])
  const [apiStatus, setApiStatus] = useState<'healthy' | 'unhealthy' | 'checking'>('checking')

  useEffect(() => {
    checkApiHealth()
  }, [])

  const checkApiHealth = async () => {
    try {
      const response = await fetch('http://localhost:7080/health')
      if (response.ok) {
        setApiStatus('healthy')
        addLog('✅ API connection established')
      } else {
        setApiStatus('unhealthy')
        addLog('❌ API health check failed')
      }
    } catch (error) {
      setApiStatus('unhealthy')
      addLog('❌ Cannot connect to API server')
    }
  }

  const addLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString()
    setLogs(prev => [...prev, `[${timestamp}] ${message}`])
  }

  const runTestSuite = async (suiteId: string) => {
    if (isRunning) return
    
    setIsRunning(true)
    setSelectedSuite(suiteId)
    
    const suite = testSuites.find(s => s.id === suiteId)
    if (!suite) return

    addLog(`🚀 Starting test suite: ${suite.name}`)
    
    // Reset suite stats
    const updatedSuites = testSuites.map(s => 
      s.id === suiteId 
        ? { ...s, passedTests: 0, failedTests: 0, runningTests: 0, tests: [], lastRun: new Date().toISOString() }
        : s
    )
    setTestSuites(updatedSuites)

    try {
      // Start test execution via API
      const response = await fetch(`http://localhost:7080/v1/test-runner/execute/${suiteId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      })
      
      if (response.ok) {
        const result = await response.json()
        addLog(`📡 ${result.message}`)
        
        // Poll for results
        await pollTestResults()
      } else {
        addLog(`❌ Failed to start test suite: ${response.statusText}`)
      }
    } catch (error) {
      addLog(`❌ Test suite failed: ${error}`)
    } finally {
      setIsRunning(false)
    }
  }

  const executeTestSuite = async (suiteId: string) => {
    const testDefinitions = getTestDefinitions(suiteId)
    
    for (const testDef of testDefinitions) {
      addLog(`🔄 Running: ${testDef.name}`)
      
      // Update test status to running
      updateTestStatus(suiteId, testDef.name, 'running')
      
      const startTime = Date.now()
      
      try {
        const result = await runIndividualTest(testDef)
        const duration = Date.now() - startTime
        
        if (result.success) {
          updateTestStatus(suiteId, testDef.name, 'passed', { duration, output: result.output })
          addLog(`✅ ${testDef.name} - PASSED (${duration}ms)`)
        } else {
          updateTestStatus(suiteId, testDef.name, 'failed', { duration, error: result.error, output: result.output })
          addLog(`❌ ${testDef.name} - FAILED: ${result.error}`)
        }
      } catch (error) {
        const duration = Date.now() - startTime
        updateTestStatus(suiteId, testDef.name, 'failed', { duration, error: String(error) })
        addLog(`❌ ${testDef.name} - ERROR: ${error}`)
      }
      
      // Small delay between tests
      await new Promise(resolve => setTimeout(resolve, 500))
    }
    
    const suite = testSuites.find(s => s.id === suiteId)
    if (suite) {
      addLog(`🏁 Test suite completed: ${suite.passedTests}/${suite.totalTests} passed`)
    }
  }

  const updateTestStatus = (suiteId: string, testName: string, status: TestResult['status'], details?: any) => {
    setTestSuites(prev => prev.map(suite => {
      if (suite.id !== suiteId) return suite
      
      const existingTestIndex = suite.tests.findIndex(t => t.name === testName)
      const testResult: TestResult = {
        name: testName,
        status,
        timestamp: new Date().toISOString(),
        ...details
      }
      
      let updatedTests
      if (existingTestIndex >= 0) {
        updatedTests = [...suite.tests]
        updatedTests[existingTestIndex] = testResult
      } else {
        updatedTests = [...suite.tests, testResult]
      }
      
      const passedTests = updatedTests.filter(t => t.status === 'passed').length
      const failedTests = updatedTests.filter(t => t.status === 'failed').length
      const runningTests = updatedTests.filter(t => t.status === 'running').length
      
      return {
        ...suite,
        tests: updatedTests,
        passedTests,
        failedTests,
        runningTests
      }
    }))
  }

  const runIndividualTest = async (testDef: any): Promise<{ success: boolean; output?: string[]; error?: string }> => {
    // Simulate actual API calls based on test type
    const output: string[] = []
    
    try {
      switch (testDef.type) {
        case 'health':
          const healthResponse = await fetch('http://localhost:7080/health')
          const healthData = await healthResponse.json()
          output.push(`Status: ${healthData.status}`)
          return { success: healthResponse.ok, output }
          
        case 'ingestion':
          const testLog = {
            ts: new Date().toISOString(),
            level: 'INFO',
            msg: `Test log from UI - ${Date.now()}`,
            service: 'test-runner',
            customer_id: 'test-customer'
          }
          const ingestResponse = await fetch('http://localhost:7080/v1/ingest/logs', {
            method: 'POST',
            headers: { 
              'Content-Type': 'application/json',
              'X-Customer-ID': 'test-customer'
            },
            body: JSON.stringify(testLog)
          })
          output.push(`Ingestion response: ${ingestResponse.status}`)
          return { success: ingestResponse.ok, output }
          
        case 'query':
          const queryResponse = await fetch('http://localhost:7080/v1/query/advanced', {
            method: 'POST',
            headers: { 
              'Content-Type': 'application/json',
              'X-Customer-ID': 'test-customer'
            },
            body: JSON.stringify({
              start_time: new Date(Date.now() - 3600000).toISOString(),
              end_time: new Date().toISOString(),
              filters: [{ field: 'customer_id', operator: 'eq', value: 'test-customer' }],
              limit: 10
            })
          })
          const queryData = await queryResponse.json()
          output.push(`Query returned ${queryData.results?.length || 0} results`)
          return { success: queryResponse.ok, output }
          
        case 'dashboard':
          const dashboardResponse = await fetch('http://localhost:7080/v1/dashboards/security_soc', {
            headers: { 'X-Customer-ID': 'test-customer' }
          })
          const dashboardData = await dashboardResponse.json()
          output.push(`Dashboard has ${dashboardData.widgets?.length || 0} widgets`)
          return { success: dashboardResponse.ok, output }
          
        case 'alert':
          const alertRuleResponse = await fetch('http://localhost:7080/v1/alerts/rules', {
            headers: { 'X-Customer-ID': 'test-customer' }
          })
          const alertData = await alertRuleResponse.json()
          output.push(`Found ${alertData.rules?.length || 0} alert rules`)
          return { success: alertRuleResponse.ok, output }
          
        default:
          // Simulate test execution
          await new Promise(resolve => setTimeout(resolve, Math.random() * 2000 + 500))
          const success = Math.random() > 0.1 // 90% success rate for demo
          output.push(`Simulated test execution completed`)
          if (!success) {
            return { success: false, error: 'Simulated test failure for demo purposes', output }
          }
          return { success: true, output }
      }
    } catch (error) {
      return { success: false, error: String(error), output }
    }
  }

  const getTestDefinitions = (suiteId: string) => {
    const definitions: Record<string, any[]> = {
      'ingestion': [
        { name: 'API Health Check', type: 'health' },
        { name: 'JSON Log Ingestion', type: 'ingestion' },
        { name: 'Batch Log Ingestion', type: 'batch_ingestion' },
        { name: 'Syslog Format Parsing', type: 'syslog' },
        { name: 'OTLP Format Support', type: 'otlp' },
        { name: 'CEF Format Parsing', type: 'cef' },
        { name: 'Nginx Log Parsing', type: 'nginx' },
        { name: 'Auto Format Detection', type: 'auto_format' },
        { name: 'Storage Persistence', type: 'storage' },
        { name: 'TTL Policy Application', type: 'ttl' },
        { name: 'Multi-Cloud Storage', type: 'cloud_storage' },
        { name: 'Performance Validation', type: 'performance' }
      ],
      'query-dashboard': [
        { name: 'Advanced Query Engine', type: 'query' },
        { name: 'Time Range Filtering', type: 'time_filter' },
        { name: 'Field-based Filtering', type: 'field_filter' },
        { name: 'Aggregation Functions', type: 'aggregation' },
        { name: 'Time Series Analysis', type: 'timeseries' },
        { name: 'Security SOC Dashboard', type: 'dashboard' },
        { name: 'Performance Dashboard', type: 'dashboard' },
        { name: 'Infrastructure Dashboard', type: 'dashboard' },
        { name: 'Business Metrics Dashboard', type: 'dashboard' },
        { name: 'Compliance Dashboard', type: 'dashboard' },
        { name: 'Executive Summary Dashboard', type: 'dashboard' },
        { name: 'Custom Dashboard Creation', type: 'custom_dashboard' },
        { name: 'Widget Data Generation', type: 'widget_data' },
        { name: 'Dashboard Export', type: 'export' },
        { name: 'Real-time Updates', type: 'realtime' },
        { name: 'Query Performance', type: 'query_perf' },
        { name: 'Dashboard Caching', type: 'caching' },
        { name: 'Data Visualization', type: 'visualization' }
      ],
      'alert-engine': [
        { name: 'Alert Engine Health', type: 'alert' },
        { name: 'Threshold Rule Creation', type: 'threshold_rule' },
        { name: 'Anomaly Detection Rules', type: 'anomaly_rule' },
        { name: 'Pattern Matching Rules', type: 'pattern_rule' },
        { name: 'Frequency-based Rules', type: 'frequency_rule' },
        { name: 'Absence Detection Rules', type: 'absence_rule' },
        { name: 'Sequence Pattern Rules', type: 'sequence_rule' },
        { name: 'Rule Evaluation Engine', type: 'rule_evaluation' },
        { name: 'Alert Lifecycle Management', type: 'alert_lifecycle' },
        { name: 'Alert Acknowledgement', type: 'alert_ack' },
        { name: 'Alert Resolution', type: 'alert_resolve' },
        { name: 'Email Notifications', type: 'notification_email' },
        { name: 'Slack Integration', type: 'notification_slack' },
        { name: 'Webhook Notifications', type: 'notification_webhook' },
        { name: 'PagerDuty Integration', type: 'notification_pagerduty' },
        { name: 'Rate Limiting', type: 'rate_limiting' },
        { name: 'Cooldown Periods', type: 'cooldown' },
        { name: 'Rule Testing (Dry Run)', type: 'rule_testing' },
        { name: 'Alert Statistics', type: 'alert_stats' },
        { name: 'Background Evaluation', type: 'background_eval' },
        { name: 'Multi-condition Rules', type: 'multi_condition' },
        { name: 'Time Window Processing', type: 'time_window' },
        { name: 'Alert Suppression', type: 'alert_suppression' },
        { name: 'Notification Channels', type: 'notification_channels' }
      ],
      'multi-tenant': [
        { name: 'Customer Isolation - Ingestion', type: 'tenant_ingestion' },
        { name: 'Customer Isolation - Queries', type: 'tenant_queries' },
        { name: 'Customer Isolation - Dashboards', type: 'tenant_dashboards' },
        { name: 'Customer Isolation - Alerts', type: 'tenant_alerts' },
        { name: 'X-Customer-ID Header Validation', type: 'customer_header' },
        { name: 'Data Boundary Enforcement', type: 'data_boundary' },
        { name: 'Cross-tenant Access Prevention', type: 'cross_tenant' },
        { name: 'Tenant-specific TTL Policies', type: 'tenant_ttl' },
        { name: 'Tenant Storage Isolation', type: 'tenant_storage' },
        { name: 'Tenant-specific Retention', type: 'tenant_retention' },
        { name: 'Multi-tenant Schema Validation', type: 'schema_validation' },
        { name: 'Tenant Compliance Policies', type: 'compliance_policies' },
        { name: 'Resource Quota Enforcement', type: 'resource_quota' },
        { name: 'Tenant Security Boundaries', type: 'security_boundaries' },
        { name: 'Audit Trail per Tenant', type: 'audit_trail' }
      ],
      'performance': [
        { name: 'Ingestion Throughput (EPS)', type: 'ingestion_throughput' },
        { name: 'Query Response Time', type: 'query_latency' },
        { name: 'Dashboard Load Time', type: 'dashboard_latency' },
        { name: 'Alert Processing Latency', type: 'alert_latency' },
        { name: 'Memory Usage Validation', type: 'memory_usage' },
        { name: 'CPU Usage Under Load', type: 'cpu_usage' },
        { name: 'Storage Compression Ratio', type: 'compression_ratio' },
        { name: 'Concurrent User Handling', type: 'concurrent_users' }
      ],
      'integration': [
        { name: 'End-to-End Log Flow', type: 'e2e_flow' },
        { name: 'Complete Query Workflow', type: 'query_workflow' },
        { name: 'Dashboard Data Pipeline', type: 'dashboard_pipeline' },
        { name: 'Alert Notification Flow', type: 'alert_flow' },
        { name: 'Multi-tenant E2E', type: 'multitenant_e2e' },
        { name: 'Storage Lifecycle', type: 'storage_lifecycle' },
        { name: 'System Recovery', type: 'system_recovery' },
        { name: 'API Endpoint Validation', type: 'api_validation' },
        { name: 'Cross-service Integration', type: 'cross_service' },
        { name: 'Regression Test Suite', type: 'regression' }
      ]
    }
    
    return definitions[suiteId] || []
  }

  const getStatusIcon = (status: TestResult['status']) => {
    switch (status) {
      case 'passed': return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'failed': return <XCircle className="h-4 w-4 text-red-500" />
      case 'running': return <Clock className="h-4 w-4 text-blue-500 animate-spin" />
      default: return <AlertCircle className="h-4 w-4 text-gray-400" />
    }
  }

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'Core': return <Database className="h-5 w-5 text-blue-500" />
      case 'Analytics': return <BarChart3 className="h-5 w-5 text-green-500" />
      case 'Monitoring': return <AlertCircle className="h-5 w-5 text-orange-500" />
      case 'Security': return <Shield className="h-5 w-5 text-red-500" />
      case 'Performance': return <Activity className="h-5 w-5 text-purple-500" />
      case 'Integration': return <Activity className="h-5 w-5 text-indigo-500" />
      default: return <Activity className="h-5 w-5 text-gray-500" />
    }
  }

  const runAllTests = async () => {
    if (isRunning) return
    
    addLog('🚀 Starting comprehensive test suite execution')
    
    for (const suite of testSuites) {
      await runTestSuite(suite.id)
      await new Promise(resolve => setTimeout(resolve, 1000)) // Brief pause between suites
    }
    
    addLog('🏁 All test suites completed')
  }

  const pollTestResults = async () => {
    const pollInterval = setInterval(async () => {
      try {
        // Get test status
        const statusResponse = await fetch('http://localhost:7080/v1/test-runner/status')
        if (statusResponse.ok) {
          const status = await statusResponse.json()
          
          if (!status.running) {
            // Tests completed, get final results
            await fetchTestResults()
            clearInterval(pollInterval)
            setIsRunning(false)
            return
          }
        }

        // Get logs
        const logsResponse = await fetch('http://localhost:7080/v1/test-runner/logs')
        if (logsResponse.ok) {
          const logsData = await logsResponse.json()
          setLogs(logsData.logs)
        }

        // Get suite results if available
        await fetchTestResults()
        
      } catch (error) {
        addLog(`❌ Error polling results: ${error}`)
      }
    }, 2000) // Poll every 2 seconds

    // Cleanup after 10 minutes
    setTimeout(() => {
      clearInterval(pollInterval)
      setIsRunning(false)
    }, 600000)
  }

  const fetchTestResults = async () => {
    if (!selectedSuite) return

    try {
      const response = await fetch(`http://localhost:7080/v1/test-runner/suites/${selectedSuite}/results`)
      if (response.ok) {
        const suiteResult = await response.json()
        
        setTestSuites(prev => prev.map(suite => 
          suite.id === selectedSuite
            ? {
                ...suite,
                totalTests: suiteResult.total_tests,
                passedTests: suiteResult.passed_tests,
                failedTests: suiteResult.failed_tests,
                runningTests: suiteResult.running_tests,
                tests: suiteResult.tests.map((test: any) => ({
                  name: test.name,
                  status: test.status,
                  duration: test.duration,
                  error: test.error,
                  output: test.output,
                  timestamp: test.timestamp
                }))
              }
            : suite
        ))
      }
    } catch (error) {
      // Ignore fetch errors during polling
    }
  }

  const clearLogs = async () => {
    try {
      await fetch('http://localhost:7080/v1/test-runner/logs', { method: 'DELETE' })
      setLogs([])
    } catch (error) {
      setLogs([])
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">Logforge Test Runner</h1>
          <p className="text-lg text-gray-600">
            Comprehensive testing interface for all Logforge functionality
          </p>
          
          {/* API Status */}
          <div className="mt-4 flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <div className={`w-3 h-3 rounded-full ${
                apiStatus === 'healthy' ? 'bg-green-500' : 
                apiStatus === 'unhealthy' ? 'bg-red-500' : 'bg-yellow-500 animate-pulse'
              }`}></div>
              <span className="text-sm font-medium">
                API Status: {apiStatus === 'healthy' ? 'Connected' : apiStatus === 'unhealthy' ? 'Disconnected' : 'Checking...'}
              </span>
            </div>
            
            <button
              onClick={runAllTests}
              disabled={isRunning || apiStatus !== 'healthy'}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-bold py-2 px-4 rounded flex items-center space-x-2"
            >
              {isRunning ? <Clock className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              <span>{isRunning ? 'Running Tests...' : 'Run All Tests'}</span>
            </button>
            
            <button
              onClick={clearLogs}
              className="bg-gray-500 hover:bg-gray-600 text-white font-bold py-2 px-4 rounded flex items-center space-x-2"
            >
              <Square className="h-4 w-4" />
              <span>Clear Logs</span>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Test Suites Panel */}
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-gray-900">Test Suites</h2>
            
            {testSuites.map((suite) => (
              <div key={suite.id} className="bg-white rounded-lg shadow-md p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    {getCategoryIcon(suite.category)}
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">{suite.name}</h3>
                      <p className="text-sm text-gray-600">{suite.description}</p>
                    </div>
                  </div>
                  
                  <button
                    onClick={() => runTestSuite(suite.id)}
                    disabled={isRunning}
                    className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded flex items-center space-x-2"
                  >
                    {suite.runningTests > 0 ? <Clock className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                    <span>Run</span>
                  </button>
                </div>
                
                {/* Test Statistics */}
                <div className="grid grid-cols-4 gap-4 mb-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-gray-900">{suite.totalTests}</div>
                    <div className="text-sm text-gray-600">Total</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">{suite.passedTests}</div>
                    <div className="text-sm text-gray-600">Passed</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-red-600">{suite.failedTests}</div>
                    <div className="text-sm text-gray-600">Failed</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">{suite.runningTests}</div>
                    <div className="text-sm text-gray-600">Running</div>
                  </div>
                </div>
                
                {/* Progress Bar */}
                <div className="w-full bg-gray-200 rounded-full h-2 mb-4">
                  <div 
                    className="bg-green-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${suite.totalTests > 0 ? (suite.passedTests / suite.totalTests) * 100 : 0}%` }}
                  ></div>
                </div>
                
                {/* Individual Test Results */}
                {suite.tests.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="font-medium text-gray-900">Test Results:</h4>
                    <div className="max-h-40 overflow-y-auto space-y-1">
                      {suite.tests.map((test, index) => (
                        <div key={index} className="flex items-center justify-between text-sm">
                          <div className="flex items-center space-x-2">
                            {getStatusIcon(test.status)}
                            <span className="truncate">{test.name}</span>
                          </div>
                          {test.duration && (
                            <span className="text-gray-500">{test.duration}ms</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {suite.lastRun && (
                  <div className="mt-4 text-sm text-gray-500">
                    Last run: {new Date(suite.lastRun).toLocaleString()}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Logs Panel */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold text-gray-900">Test Execution Logs</h2>
              <div className="text-sm text-gray-500">
                {logs.length} entries
              </div>
            </div>
            
            <div className="bg-black text-green-400 font-mono text-sm p-4 rounded-lg h-96 overflow-y-auto">
              {logs.length === 0 ? (
                <div className="text-gray-500">No logs yet. Run a test suite to see output...</div>
              ) : (
                logs.map((log, index) => (
                  <div key={index} className="mb-1 whitespace-pre-wrap">
                    {log}
                  </div>
                ))
              )}
            </div>
            
            {/* Selected Test Details */}
            {selectedSuite && (
              <div className="mt-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  Current Suite: {testSuites.find(s => s.id === selectedSuite)?.name}
                </h3>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="font-medium">Status:</span> {isRunning ? 'Running' : 'Idle'}
                  </div>
                  <div>
                    <span className="font-medium">Progress:</span> 
                    {(() => {
                      const suite = testSuites.find(s => s.id === selectedSuite)
                      if (!suite) return 'N/A'
                      return `${suite.passedTests + suite.failedTests}/${suite.totalTests}`
                    })()}
                  </div>
                  <div>
                    <span className="font-medium">Success Rate:</span>
                    {(() => {
                      const suite = testSuites.find(s => s.id === selectedSuite)
                      if (!suite || suite.passedTests + suite.failedTests === 0) return 'N/A'
                      return `${Math.round((suite.passedTests / (suite.passedTests + suite.failedTests)) * 100)}%`
                    })()}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}