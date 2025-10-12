# Saved Queries API Runbook

## Overview
This runbook documents the saved queries management API endpoints for storing, retrieving, updating, and deleting query definitions in the Logforge platform.

## API Endpoints Overview

**Base Path**: `/v1/query/saved`  
**Authentication**: Bearer token + X-Customer-ID header  
**Database Table**: `saved_queries_mt` (single table for all operations)

### Supported Operations
- **GET /v1/query/saved** - List saved queries with filtering and pagination
- **POST /v1/query/saved** - Save a new query for future reuse
- **GET /v1/query/saved/{id}** - Retrieve a specific saved query by ID
- **PUT /v1/query/saved/{id}** - Update an existing saved query
- **DELETE /v1/query/saved/{id}** - Delete (deactivate) a saved query

## Database Tables Accessed

### 1. saved_queries_mt (Primary Table)
**Purpose**: Stores all saved query definitions and metadata  
**Access Methods**: CRUD operations via QueryDAO and QueryService  
**Key Fields**:
- `id`: Unique query identifier (UUID)
- `customer_id`: Tenant isolation identifier
- `name`: User-friendly query name
- `description`: Optional query description
- `query_definition`: JSON-encoded query structure
- `query_type`: Query type (default: 'advanced')
- `created_by`: User who created the query (default: 'system')
- `tags`: JSON-encoded array of tags
- `is_public`: Boolean for query visibility
- `created_at`: Query creation timestamp
- `updated_at`: Last modification timestamp
- `status`: Query status ('active' or 'inactive')

**Query Patterns**:
```sql
-- List queries
SELECT * FROM saved_queries_mt 
WHERE customer_id = %(customer_id)s AND status = 'active'
ORDER BY updated_at DESC LIMIT %(limit)s

-- Get specific query
SELECT * FROM saved_queries_mt 
WHERE id = %(query_id)s AND customer_id = %(customer_id)s AND status = 'active'

-- Update query (ClickHouse ALTER syntax)
ALTER TABLE saved_queries_mt UPDATE {fields} 
WHERE id = %(query_id)s AND customer_id = %(customer_id)s

-- Soft delete query
ALTER TABLE saved_queries_mt UPDATE status = 'inactive', updated_at = %(updated_at)s
WHERE id = %(query_id)s AND customer_id = %(customer_id)s
```

## API Endpoint Details

### 1. GET /v1/query/saved - List Saved Queries

**Purpose**: Retrieve a paginated list of saved queries with optional filtering

#### Request Format
```http
GET /v1/query/saved?created_by=admin&query_type=advanced&limit=20 HTTP/1.1
Host: localhost:7080
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
X-Customer-ID: 505908f9-8718-4dea-b2d8-9b9e5ae0bd45
```

#### Query Parameters
- **created_by** (optional): Filter by creator username
- **query_type** (optional): Filter by query type
- **limit** (optional): Maximum queries to return (default: 50, max: 100)

#### Sample cURL
```bash
curl -X GET "http://localhost:7080/v1/query/saved?limit=10" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID"
```

#### Success Response (200 OK)
```json
{
  "saved_queries": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "customer_id": "505908f9-8718-4dea-b2d8-9b9e5ae0bd45",
      "name": "Error Logs Analysis",
      "description": "Query to find error patterns in application logs",
      "query_definition": {
        "filters": [
          {"field": "level", "operator": "eq", "value": "error"}
        ],
        "aggregations": [
          {"field": "service", "type": "count"}
        ]
      },
      "query_type": "advanced",
      "created_by": "admin",
      "tags": ["errors", "monitoring"],
      "is_public": false,
      "created_at": "2025-10-09T12:00:00Z",
      "updated_at": "2025-10-09T12:30:00Z",
      "status": "active"
    }
  ],
  "count": 1,
  "customer_id": "505908f9-8718-4dea-b2d8-9b9e5ae0bd45",
  "filters": {
    "created_by": null,
    "query_type": null,
    "limit": 10
  }
}
```

### 2. POST /v1/query/saved - Save New Query

**Purpose**: Create a new saved query for future reuse

#### Request Format
```http
POST /v1/query/saved HTTP/1.1
Host: localhost:7080
Content-Type: application/json
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
X-Customer-ID: 505908f9-8718-4dea-b2d8-9b9e5ae0bd45

{
  "name": "Security Events Query",
  "description": "Monitor security-related log events",
  "query_definition": {
    "filters": [
      {"field": "service", "operator": "eq", "value": "auth-service"},
      {"field": "level", "operator": "in", "value": ["warn", "error"]}
    ],
    "start_time": "2025-10-09T00:00:00Z",
    "end_time": "2025-10-09T23:59:59Z"
  },
  "query_type": "security",
  "created_by": "security_analyst",
  "tags": ["security", "authentication", "monitoring"],
  "is_public": true
}
```

#### Required Fields
- **name**: Query name (string)
- **query_definition**: Query structure (object)

#### Optional Fields
- **description**: Query description (default: empty string)
- **query_type**: Query type (default: 'advanced')
- **created_by**: Creator username (default: 'system')
- **tags**: Array of tags (default: empty array)
- **is_public**: Public visibility (default: false)

#### Sample cURL
```bash
curl -X POST "http://localhost:7080/v1/query/saved" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{
    "name": "Performance Analysis",
    "description": "Query for performance monitoring",
    "query_definition": {
      "filters": [{"field": "level", "operator": "eq", "value": "warn"}],
      "aggregations": [{"field": "response_time", "type": "avg"}]
    },
    "tags": ["performance", "monitoring"]
  }'
```

#### Success Response (200 OK)
```json
{
  "status": "saved",
  "query_id": "987fcdeb-51a2-43d7-b456-789012345678",
  "message": "Query saved successfully",
  "customer_id": "505908f9-8718-4dea-b2d8-9b9e5ae0bd45"
}
```

### 3. GET /v1/query/saved/{id} - Get Specific Query

**Purpose**: Retrieve a specific saved query by its ID

#### Request Format
```http
GET /v1/query/saved/123e4567-e89b-12d3-a456-426614174000 HTTP/1.1
Host: localhost:7080
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
X-Customer-ID: 505908f9-8718-4dea-b2d8-9b9e5ae0bd45
```

#### Sample cURL
```bash
curl -X GET "http://localhost:7080/v1/query/saved/123e4567-e89b-12d3-a456-426614174000" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID"
```

#### Success Response (200 OK)
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "customer_id": "505908f9-8718-4dea-b2d8-9b9e5ae0bd45",
  "name": "Error Logs Analysis",
  "description": "Query to find error patterns in application logs",
  "query_definition": {
    "filters": [
      {"field": "level", "operator": "eq", "value": "error"}
    ],
    "aggregations": [
      {"field": "service", "type": "count"}
    ]
  },
  "query_type": "advanced",
  "created_by": "admin",
  "tags": ["errors", "monitoring"],
  "is_public": false,
  "created_at": "2025-10-09T12:00:00Z",
  "updated_at": "2025-10-09T12:30:00Z",
  "status": "active"
}
```

#### Error Response (404 Not Found)
```json
{
  "detail": "Query not found"
}
```

### 4. PUT /v1/query/saved/{id} - Update Query

**Purpose**: Update an existing saved query

#### Request Format
```http
PUT /v1/query/saved/123e4567-e89b-12d3-a456-426614174000 HTTP/1.1
Host: localhost:7080
Content-Type: application/json
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
X-Customer-ID: 505908f9-8718-4dea-b2d8-9b9e5ae0bd45

{
  "name": "Updated Error Analysis",
  "description": "Enhanced error pattern analysis with additional filters",
  "query_definition": {
    "filters": [
      {"field": "level", "operator": "eq", "value": "error"},
      {"field": "service", "operator": "ne", "value": "health-check"}
    ],
    "aggregations": [
      {"field": "service", "type": "count"},
      {"field": "host", "type": "count"}
    ]
  },
  "tags": ["errors", "monitoring", "enhanced"],
  "is_public": true
}
```

#### Updateable Fields
- **name**: Query name
- **description**: Query description
- **query_definition**: Query structure
- **tags**: Array of tags
- **is_public**: Public visibility

#### Sample cURL
```bash
curl -X PUT "http://localhost:7080/v1/query/saved/123e4567-e89b-12d3-a456-426614174000" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{
    "name": "Updated Query Name",
    "description": "Updated description",
    "tags": ["updated", "monitoring"]
  }'
```

#### Success Response (200 OK)
```json
{
  "status": "updated",
  "query_id": "123e4567-e89b-12d3-a456-426614174000",
  "message": "Query updated successfully",
  "customer_id": "505908f9-8718-4dea-b2d8-9b9e5ae0bd45"
}
```

### 5. DELETE /v1/query/saved/{id} - Delete Query

**Purpose**: Delete (soft delete/deactivate) a saved query

#### Request Format
```http
DELETE /v1/query/saved/123e4567-e89b-12d3-a456-426614174000 HTTP/1.1
Host: localhost:7080
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
X-Customer-ID: 505908f9-8718-4dea-b2d8-9b9e5ae0bd45
```

#### Sample cURL
```bash
curl -X DELETE "http://localhost:7080/v1/query/saved/123e4567-e89b-12d3-a456-426614174000" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID"
```

#### Success Response (200 OK)
```json
{
  "status": "deleted",
  "query_id": "123e4567-e89b-12d3-a456-426614174000",
  "message": "Query deleted successfully",
  "customer_id": "505908f9-8718-4dea-b2d8-9b9e5ae0bd45"
}
```

## Code Flow Analysis

### Request Processing Flow
1. **Authentication**: JWT token validation + X-Customer-ID header verification
2. **Request Routing**: FastAPI router directs to appropriate query endpoint
3. **Service Layer**: QueryService handles business logic and validation
4. **Data Access**: QueryDAO performs database operations with tenant isolation
5. **Response**: Formatted JSON response with operation results

### Service Layer Implementation (QueryService)
```python
# Save query with validation
async def save_query(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
    # Validate required fields
    required_fields = ['customer_id', 'name', 'query_definition']
    # Set defaults for optional fields
    # Save via QueryDAO with proper error handling

# Get query with tenant validation
async def get_saved_query(self, query_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
    # Validate inputs
    # Retrieve via QueryDAO with tenant isolation
    # Return formatted result or None

# Update with field validation
async def update_saved_query(self, query_id: str, customer_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    # Validate updateable fields
    # Filter allowed fields only
    # Update via QueryDAO with success/failure response
```

### Database Layer Implementation (QueryDAO)
```python
# JSON field handling for complex data
def save_query(self, query_data: Dict[str, Any]) -> str:
    # Convert complex fields to JSON
    query_data['query_definition'] = json.dumps(query_data['query_definition'])
    query_data['tags'] = json.dumps(query_data.get('tags', []))
    # Execute INSERT with all fields

# ClickHouse ALTER syntax for updates
def update_saved_query(self, query_id: str, customer_id: str, update_data: Dict[str, Any]) -> bool:
    # Build dynamic UPDATE clauses
    # Use ClickHouse ALTER TABLE ... UPDATE syntax
    # Apply tenant isolation in WHERE clause

# Soft delete implementation
def delete_saved_query(self, query_id: str, customer_id: str) -> bool:
    # UPDATE status to 'inactive' instead of DELETE
    # Preserve data for audit and recovery
```

## Authentication & Security

### Required Authentication
- **JWT Bearer Token**: Must be valid and non-expired
- **X-Customer-ID Header**: Must match authenticated user's tenant ID
- **Tenant Isolation**: Automatic enforcement via customer_id filtering in all queries

### Security Features
- **Mandatory Tenant Filtering**: All database queries include customer_id filtering
- **Field Validation**: Only allowed fields can be updated in PUT operations
- **Soft Delete**: Queries are deactivated, not permanently deleted
- **JSON Validation**: Query definitions validated as proper JSON structures
- **Input Sanitization**: All user inputs sanitized before database operations

### Data Protection
- **No Mock Data**: All operations use real database with proper validation
- **Audit Trail**: Creation and modification timestamps tracked
- **Access Control**: Only query owner's tenant can access/modify queries
- **Data Integrity**: UUID primary keys prevent ID conflicts

## Performance Characteristics

### Response Time Targets
- **List Queries**: < 200ms for typical result sets (< 100 queries)
- **Get Query**: < 100ms for single query retrieval
- **Save Query**: < 150ms for new query creation
- **Update Query**: < 200ms for query modifications (ClickHouse ALTER)
- **Delete Query**: < 150ms for soft delete operations

### Optimization Features
- **Pagination**: Default and maximum limits prevent large result sets
- **Indexing**: customer_id and id fields indexed for fast lookups
- **JSON Parsing**: Efficient JSON encoding/decoding for complex fields
- **Bulk Operations**: Not implemented (single query operations only)

## Error Handling

### Validation Errors (400 Bad Request)
```json
{
  "detail": "Missing required field: name"
}

{
  "detail": "Query ID and customer ID are required"
}

{
  "detail": "No valid fields to update"
}
```

### Authentication Errors (401/403)
```json
{
  "detail": "Invalid or expired session"
}

{
  "detail": "Access denied to query resource"
}
```

### Not Found Errors (404)
```json
{
  "detail": "Query not found"
}
```

### Server Errors (500)
```json
{
  "detail": "Failed to save query: Database connection error"
}

{
  "detail": "Failed to update query: Invalid query definition format"
}
```

## Monitoring & Troubleshooting

### Key Metrics to Monitor
- **Query Management Operations**: Create, read, update, delete success rates
- **Database Performance**: saved_queries_mt table query performance
- **JSON Field Size**: Monitor query_definition and tags field sizes
- **Tenant Usage**: Number of saved queries per tenant
- **Error Rates**: Failed operations by error type

### Common Issues
1. **JSON Parsing Errors**: Invalid query_definition structures
2. **ClickHouse ALTER Performance**: Slow update operations on large tables
3. **Tenant Isolation Failures**: Incorrect customer_id filtering
4. **Field Validation**: Attempts to update non-allowed fields

### Debugging Steps
1. **Check Authentication**: Verify JWT token and X-Customer-ID header
2. **Validate JSON**: Ensure query_definition is valid JSON structure
3. **Test Database Access**: Verify ClickHouse connectivity and permissions
4. **Monitor Query Performance**: Check ClickHouse query logs for slow operations
5. **Verify Tenant Isolation**: Ensure customer_id filtering is applied correctly

## Usage Examples

### Query Library Management
```python
import requests
import json

class QueryLibrary:
    def __init__(self, api_url, auth_token, tenant_id):
        self.api_url = api_url
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {auth_token}',
            'X-Customer-ID': tenant_id
        }
    
    def create_monitoring_query(self, name, service, level):
        """Create a monitoring query for specific service and level"""
        query_data = {
            "name": name,
            "description": f"Monitor {level} logs for {service}",
            "query_definition": {
                "filters": [
                    {"field": "service", "operator": "eq", "value": service},
                    {"field": "level", "operator": "eq", "value": level}
                ],
                "aggregations": [
                    {"field": "host", "type": "count"}
                ]
            },
            "query_type": "monitoring",
            "tags": ["monitoring", service, level],
            "is_public": False
        }
        
        response = requests.post(
            f"{self.api_url}/v1/query/saved",
            headers=self.headers,
            json=query_data
        )
        return response.json()
    
    def list_queries_by_type(self, query_type):
        """List all queries of specific type"""
        params = {'query_type': query_type, 'limit': 100}
        response = requests.get(
            f"{self.api_url}/v1/query/saved",
            headers=self.headers,
            params=params
        )
        return response.json()
    
    def update_query_tags(self, query_id, new_tags):
        """Update query tags"""
        update_data = {"tags": new_tags}
        response = requests.put(
            f"{self.api_url}/v1/query/saved/{query_id}",
            headers=self.headers,
            json=update_data
        )
        return response.json()

# Usage example
library = QueryLibrary(
    'http://localhost:7080',
    'your-auth-token',
    'your-tenant-id'
)

# Create monitoring queries for different services
library.create_monitoring_query("API Errors", "api-gateway", "error")
library.create_monitoring_query("DB Warnings", "database", "warn")

# List all monitoring queries
monitoring_queries = library.list_queries_by_type("monitoring")
print(f"Found {monitoring_queries['count']} monitoring queries")
```

### Batch Query Operations
```bash
#!/bin/bash
# Batch operations script

API_URL="http://localhost:7080"
AUTH_TOKEN="your-auth-token"
TENANT_ID="your-tenant-id"

# Create multiple saved queries
create_query() {
    local name="$1"
    local service="$2"
    local level="$3"
    
    curl -s -X POST "$API_URL/v1/query/saved" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "X-Customer-ID: $TENANT_ID" \
        -d "{
            \"name\": \"$name\",
            \"description\": \"Monitor $level logs for $service\",
            \"query_definition\": {
                \"filters\": [
                    {\"field\": \"service\", \"operator\": \"eq\", \"value\": \"$service\"},
                    {\"field\": \"level\", \"operator\": \"eq\", \"value\": \"$level\"}
                ]
            },
            \"tags\": [\"$service\", \"$level\", \"monitoring\"]
        }"
}

# Create queries for different services
create_query "API Gateway Errors" "api-gateway" "error"
create_query "Auth Service Warnings" "auth-service" "warn"
create_query "Database Errors" "database" "error"

# List all created queries
echo "Created queries:"
curl -s -X GET "$API_URL/v1/query/saved?limit=50" \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -H "X-Customer-ID: $TENANT_ID" | \
    jq '.saved_queries[] | "\(.name) (\(.id))"'
```

## Integration Patterns

### Dashboard Integration
```javascript
// Frontend integration for dashboard query selection
class SavedQueryManager {
    constructor(apiUrl, authToken, tenantId) {
        this.apiUrl = apiUrl;
        this.headers = {
            'Authorization': `Bearer ${authToken}`,
            'X-Customer-ID': tenantId
        };
    }
    
    async loadQueryLibrary() {
        const response = await fetch(`${this.apiUrl}/v1/query/saved?limit=100`, {
            headers: this.headers
        });
        const data = await response.json();
        return data.saved_queries;
    }
    
    async executeQuery(queryId) {
        // Get saved query definition
        const queryResponse = await fetch(`${this.apiUrl}/v1/query/saved/${queryId}`, {
            headers: this.headers
        });
        const queryData = await queryResponse.json();
        
        // Execute the query using advanced query endpoint
        const executeResponse = await fetch(`${this.apiUrl}/v1/query/advanced`, {
            method: 'POST',
            headers: {
                ...this.headers,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(queryData.query_definition)
        });
        
        return executeResponse.json();
    }
}
```

---

**Last Updated**: October 2025  
**API Version**: v1  
**Maintainer**: Logforge Engineering Team