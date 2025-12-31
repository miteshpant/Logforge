# Logforge API Client Library

Comprehensive, type-safe API client for all Logforge backend services.

## Features

✅ **Type-Safe** - Full TypeScript support with detailed interfaces
✅ **Modular** - Organized by domain (Observability, Security, Alerts, AI)
✅ **Auto Error Handling** - Normalized response format with error handling
✅ **Timeout Support** - Configurable request timeouts
✅ **Authentication** - Built-in token and customer ID management

## Installation

The API client is already available in the project at `/lib/api/`.

## Quick Start

```typescript
import { apiClient, ObservabilityApi } from '@/lib/api'

// Use the API client directly
const response = await apiClient.get('/v1/health')

// Or use domain-specific modules
const serviceMap = await ObservabilityApi.getServiceMap('24h')
```

## Available Modules

### 1. Observability API (`ObservabilityApi`)

Service maps, APM, distributed tracing, metrics:

```typescript
import { ObservabilityApi } from '@/lib/api/observability'

// Get service map
const serviceMap = await ObservabilityApi.getServiceMap('1h')

// List all services
const services = await ObservabilityApi.listServices()

// Get APM overview
const apm = await ObservabilityApi.getApmOverview({
  start_time: '2024-01-01T00:00:00Z',
  end_time: '2024-01-02T00:00:00Z'
})

// Search traces
const traces = await ObservabilityApi.searchTraces({
  service: 'payment-service',
  min_duration: 1000,
  limit: 20
})
```

### 2. Security API (`SecurityApi`)

Security events, Sigma rules, threat hunting:

```typescript
import { SecurityApi } from '@/lib/api/security'

// Get security dashboard
const dashboard = await SecurityApi.getSecurityDashboard({ time_range: '24h' })

// List security events
const events = await SecurityApi.listSecurityEvents({
  severity: 'high',
  status: 'open',
  limit: 50
})

// Manage Sigma rules
const rules = await SecurityApi.listSigmaRules()
const newRule = await SecurityApi.createSigmaRule({
  title: 'Brute Force Detection',
  description: 'Detects brute force login attempts',
  // ... rule config
})

// Threat hunting
const campaign = await SecurityApi.createThreatHunt({
  name: 'Suspicious Login Campaign',
  hypothesis: 'Unusual login patterns from foreign IPs',
  hunt_query: '...',
  // ... campaign config
})
```

### 3. Alerts API (`AlertsApi`)

Alert rules, instances, channels:

```typescript
import { AlertsApi } from '@/lib/api/alerts'

// List alerts
const alerts = await AlertsApi.listAlerts({
  status: 'active',
  severity: 'critical'
})

// Manage alert rules
const rules = await AlertsApi.listRules()
const newRule = await AlertsApi.createRule({
  name: 'High Error Rate',
  description: 'Triggers when error rate > 5%',
  query: '...',
  condition: 'error_rate > 0.05',
  threshold: 5,
  severity: 'high',
  // ... rule config
})

// Test a rule
const testResult = await AlertsApi.testRule({
  query: '...',
  condition: 'error_rate > 0.05'
})

// Acknowledge alerts
await AlertsApi.acknowledgeAlert('alert-id-123', 'Investigating...')
```

### 4. AI API (`AiApi`)

Anomaly detection, RCA, natural language queries:

```typescript
import { AiApi } from '@/lib/api/ai'

// Detect anomalies
const anomalies = await AiApi.detectAnomalies({
  metrics: [
    { type: 'cpu_usage', service: 'api-service', weight: 1.0 },
    { type: 'memory_usage', service: 'api-service', weight: 0.9 }
  ],
  time_range: '1h',
  correlation_threshold: 0.6,
  algorithms: ['z_score']
})

// Root cause analysis
const rca = await AiApi.analyzeRootCause({
  incident_id: 'inc-123',
  start_time: '2024-01-01T10:00:00Z',
  end_time: '2024-01-01T11:00:00Z',
  affected_services: ['payment-service'],
  symptoms: ['high_latency', 'error_spike']
})

// Natural language query
const nlqResult = await AiApi.queryNaturalLanguage({
  query: 'Show me all errors from payment service in the last hour',
  context: 'logs',
  analysis_type: 'logs'
})
```

### 5. Query API (`QueryApi`)

Advanced log queries:

```typescript
import { QueryApi } from '@/lib/api/query'

// Execute advanced query
const results = await QueryApi.executeAdvancedQuery({
  start_time: '2024-01-01T00:00:00Z',
  end_time: '2024-01-02T00:00:00Z',
  filters: [
    { field: 'level', operator: 'eq', value: 'ERROR' },
    { field: 'service', operator: 'in', value: ['api', 'payment'] }
  ],
  aggregations: [
    { type: 'count', field: '*', alias: 'total_logs' },
    { type: 'unique', field: 'service', alias: 'unique_services' }
  ],
  group_by: ['level', 'service'],
  limit: 100
})

// Search logs
const searchResults = await QueryApi.searchLogs({
  query: 'payment failed',
  start_time: '2024-01-01T00:00:00Z',
  limit: 50
})
```

### 6. Usage API (`UsageApi`)

Usage statistics and billing:

```typescript
import { UsageApi } from '@/lib/api/usage'

// Get usage stats
const usageStats = await UsageApi.getUsageOverviewStats({
  start_time: '2024-01-01T00:00:00Z',
  end_time: '2024-01-02T00:00:00Z'
})

// Get billing estimate
const billing = await UsageApi.getBillingEstimate()

// Get storage info
const storage = await UsageApi.getStorageInfo()
```

## Core API Client

### Making Custom Requests

```typescript
import { apiClient } from '@/lib/api'

// GET request
const response = await apiClient.get('/v1/custom-endpoint', {
  param1: 'value1',
  param2: 'value2'
})

// POST request
const response = await apiClient.post('/v1/custom-endpoint', {
  data: 'value'
})

// PUT request
const response = await apiClient.put('/v1/custom-endpoint/123', {
  updated_field: 'new value'
})

// DELETE request
const response = await apiClient.delete('/v1/custom-endpoint/123')
```

### Authentication

```typescript
import { apiClient } from '@/lib/api'

// Set auth token
apiClient.setAuthToken('your-jwt-token')

// Set customer ID
apiClient.setCustomerId('customer-123')

// Clear auth
apiClient.clearAuthToken()
```

### Response Format

All API calls return a normalized response:

```typescript
interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
  message?: string
}

// Example usage
const response = await ObservabilityApi.getServiceMap('1h')

if (response.success) {
  console.log('Service Map:', response.data)
} else {
  console.error('Error:', response.error)
}
```

## Configuration

Set the API base URL via environment variable:

```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:7080
```

Default timeout is 30 seconds. All requests include automatic timeout handling.

## Error Handling

The API client handles errors automatically:

- **Network errors**: Returns `{ success: false, error: 'Network error' }`
- **Timeout errors**: Returns `{ success: false, error: 'Request timeout' }`
- **HTTP errors**: Returns `{ success: false, error: 'HTTP 404: Not Found' }`

Example error handling:

```typescript
const response = await ObservabilityApi.getServiceMap('1h')

if (!response.success) {
  // Handle error
  console.error(response.error)
  return
}

// Use data
const serviceMap = response.data
```

## TypeScript Support

All API functions are fully typed:

```typescript
import { ServiceMap, ServiceNode, Trace, Anomaly } from '@/lib/api'

// Types are automatically inferred
const serviceMap: ServiceMap = response.data
const services: ServiceNode[] = serviceMap.services
```

## Best Practices

1. **Always check `response.success`** before using data
2. **Use domain modules** (ObservabilityApi, SecurityApi) for better code organization
3. **Handle errors gracefully** - show user-friendly messages
4. **Use TypeScript types** for better IDE autocomplete and type safety
5. **Set auth tokens** early in your app initialization

## File Structure

```
/lib/api/
├── api.ts                  # Core API client
├── index.ts                # Centralized exports
├── observability.ts        # Observability APIs
├── security.ts             # Security APIs
├── alerts.ts               # Alerts APIs
├── ai.ts                   # AI APIs
├── query.ts                # Query APIs
├── usage.ts                # Usage APIs
└── API_README.md          # This file
```

## Contributing

When adding new API endpoints:

1. Add types to the appropriate module
2. Create API function following existing patterns
3. Export function from the module
4. Update this README with usage examples

## Support

For questions or issues, refer to the main Logforge documentation.
