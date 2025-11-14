# Adding New Components to Logforge

This guide explains how to properly add new routers, services, and DAOs to the Logforge system with correct database access and middleware configuration.

## Table of Contents
1. [Overview](#overview)
2. [Database Layer Configuration](#database-layer-configuration)
3. [Creating a DAO](#creating-a-dao)
4. [Creating a Service](#creating-a-service)
5. [Creating a Router](#creating-a-router)
6. [Middleware Configuration](#middleware-configuration)
7. [Registration in main.py](#registration-in-mainpy)
8. [Testing](#testing)
9. [Example: Complete Implementation](#example-complete-implementation)

## Overview

The Logforge system follows a layered architecture:
- **Router Layer**: FastAPI endpoints handling HTTP requests
- **Service Layer**: Business logic and coordination
- **DAO Layer**: Data access objects for database operations
- **Database Layer**: Centralized ClickHouse abstraction with security

## Database Layer Configuration

### Step 1: Add Service Authentication

Edit `/apps/api/database_layer.py` and add your service to the `AUTHORIZED_SERVICES` dictionary:

```python
AUTHORIZED_SERVICES = {
    # ... existing services ...
    'YourServiceDAO': os.getenv('YOUR_SERVICE_KEY', 'your-service-key-dev'),
}
```

### Step 2: Configure Table Access

Add table permissions to `TABLE_ACCESS_CONTROL`:

```python
TABLE_ACCESS_CONTROL = {
    # ... existing services ...
    'YourServiceDAO': ['your_table_mt', 'shared_table_mt'],  # List tables your service can access
}
```

### Step 3: Configure Operation Permissions

If your service needs special operations, add it to the appropriate lists:

```python
# For DELETE operations
DELETE_ALLOWED_SERVICES = ['SecurityDAO', 'YourServiceDAO']

# For UPDATE operations  
UPDATE_ALLOWED_SERVICES = ['UserService', 'YourServiceDAO']

# For admin operations (DROP, TRUNCATE, CREATE TABLE)
ADMIN_SERVICES = ['TestService']  # Generally not needed for new services
```

## Creating a DAO

### Step 1: Create the DAO File

Create `/apps/api/dao/your_service_dao.py`:

```python
"""
Your Service Data Access Object
Handles database operations for your service
"""

import structlog
from typing import Dict, Any, Optional, List
from database_layer import DatabaseLayer
from constants.your_constants import VALID_CONFIG_TYPES

logger = structlog.get_logger(__name__)


class YourServiceDAO:
    """Data Access Object for your service"""
    
    def __init__(self):
        self.db = DatabaseLayer("YourServiceDAO", "your-service-key-dev")
    
    async def get_all_records(self) -> List[Dict[str, Any]]:
        """Get all records from your table"""
        query = """
        SELECT id, name, config, created_at, updated_at
        FROM your_table_mt 
        ORDER BY created_at DESC
        """
        
        result = await self.db.fetch(query)
        return result if result else []
    
    async def get_record_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Get specific record by ID"""
        query = """
        SELECT id, name, config, created_at, updated_at
        FROM your_table_mt 
        WHERE id = %(record_id)s
        LIMIT 1
        """
        
        result = await self.db.fetch(query, {
            "record_id": record_id
        })
        
        return result[0] if result else None
    
    async def create_record(
        self, 
        record_id: str,
        name: str, 
        config: str, 
        created_by: str
    ) -> bool:
        """Create new record"""
        try:
            import uuid
            if not record_id:
                record_id = str(uuid.uuid4())
            
            query = """
            INSERT INTO your_table_mt (
                id, name, config, created_by
            ) VALUES (
                %(id)s, %(name)s, %(config)s, %(created_by)s
            )
            """
            
            await self.db.execute(query, {
                "id": record_id,
                "name": name,
                "config": config,
                "created_by": created_by
            })
            
            logger.info(f"Created record: {record_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create record: {e}")
            return False
    
    async def update_record(
        self, 
        record_id: str, 
        config: str
    ) -> bool:
        """Update existing record"""
        try:
            query = """
            ALTER TABLE your_table_mt UPDATE 
                config = %(config)s,
                updated_at = now64(3)
            WHERE id = %(record_id)s
            """
            
            await self.db.execute(query, {
                "record_id": record_id,
                "config": config
            })
            
            logger.info(f"Updated record: {record_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update record: {e}")
            return False
    
    async def delete_record(self, record_id: str) -> bool:
        """Delete record"""
        try:
            query = """
            ALTER TABLE your_table_mt DELETE 
            WHERE id = %(record_id)s
            """
            
            await self.db.execute(query, {
                "record_id": record_id
            })
            
            logger.info(f"Deleted record: {record_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete record: {e}")
            return False
```

## Creating a Service

### Step 1: Create the Service File

Create `/apps/api/services/your_service.py`:

```python
"""
Your Service
Business logic for your service functionality
"""

import json
import structlog
from typing import Dict, Any, Optional, List
from dao.your_service_dao import YourServiceDAO
from events.management.cache.redis_manager import get_redis_manager

logger = structlog.get_logger(__name__)


class YourService:
    """Service for managing your business logic"""
    
    def __init__(self):
        self.dao = YourServiceDAO()
        self.redis = None  # Will be initialized async
    
    async def _ensure_redis_connection(self):
        """Ensure Redis connection is established"""
        if self.redis is None:
            self.redis = await get_redis_manager()
    
    async def get_all_records(self) -> List[Dict[str, Any]]:
        """Get all records with business logic applied"""
        try:
            records = await self.dao.get_all_records()
            
            # Apply business logic here
            processed_records = []
            for record in records:
                # Parse JSON config if needed
                if record.get('config'):
                    try:
                        record['parsed_config'] = json.loads(record['config'])
                    except json.JSONDecodeError:
                        record['parsed_config'] = {}
                
                processed_records.append(record)
            
            return processed_records
            
        except Exception as e:
            logger.error(f"Failed to get records: {e}")
            return []
    
    async def create_record(
        self, 
        name: str, 
        config: Dict[str, Any], 
        created_by: str
    ) -> Optional[str]:
        """Create new record with validation"""
        try:
            # Validate input
            if not name or not config:
                raise ValueError("Name and config are required")
            
            # Apply business rules
            processed_config = self._validate_and_process_config(config)
            
            # Store in database
            record_id = None  # Will be generated by DAO
            config_json = json.dumps(processed_config)
            
            success = await self.dao.create_record(
                record_id, name, config_json, created_by
            )
            
            if success:
                # Cache in Redis if needed
                await self._cache_record(record_id, processed_config)
                
            return record_id if success else None
            
        except Exception as e:
            logger.error(f"Failed to create record: {e}")
            raise
    
    def _validate_and_process_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and process configuration"""
        # Apply validation rules
        if not isinstance(config.get("enabled"), bool):
            raise ValueError("'enabled' must be a boolean")
        
        # Apply defaults
        processed = {
            "enabled": config.get("enabled", True),
            "settings": config.get("settings", {}),
            # Add more processing as needed
        }
        
        return processed
    
    async def _cache_record(self, record_id: str, config: Dict[str, Any]):
        """Cache record in Redis"""
        try:
            await self._ensure_redis_connection()
            cache_key = f"your_service:record:{record_id}"
            config_json = json.dumps(config)
            await self.redis.set(cache_key, config_json, ex=3600)  # 1 hour TTL
        except Exception as e:
            logger.warning(f"Failed to cache record: {e}")


# Global service instance
_your_service = None

def get_your_service() -> YourService:
    """Get singleton service instance"""
    global _your_service
    if _your_service is None:
        _your_service = YourService()
    return _your_service
```

## Creating a Router

### Step 1: Create the Router File

Create `/apps/api/routers/your_service_api.py`:

```python
"""
Your Service API
Manage your service configurations via REST API
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import structlog

from services.your_service import get_your_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/your-service", tags=["your-service"])


# Pydantic Models
class YourServiceConfig(BaseModel):
    """Configuration for your service"""
    enabled: bool = Field(default=True, description="Enable/disable service")
    settings: Dict[str, Any] = Field(default={}, description="Service settings")
    description: str = Field(default="", description="Configuration description")


class YourServiceResponse(BaseModel):
    """Response for your service operations"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class AllRecordsResponse(BaseModel):
    """Response for getting all records"""
    records: List[Dict[str, Any]]
    total_count: int


def get_current_user_id():
    """Mock function for getting current user ID - replace with actual auth"""
    return "system"


@router.get("/", response_model=AllRecordsResponse)
async def get_all_records():
    """Get all service records"""
    try:
        service = get_your_service()
        records = await service.get_all_records()
        
        return AllRecordsResponse(
            records=records,
            total_count=len(records)
        )
        
    except Exception as e:
        logger.error(f"Failed to get records: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get records: {str(e)}")


@router.get("/{record_id}", response_model=Dict[str, Any])
async def get_record(
    record_id: str,
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get specific record by ID"""
    try:
        service = get_your_service()
        record = await service.get_record_by_id(record_id)
        
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        
        return {
            "customer_id": customer_id,
            "record": record
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get record {record_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get record: {str(e)}")


@router.post("/", response_model=YourServiceResponse)
async def create_record(
    config: YourServiceConfig,
    name: str,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: str = Depends(get_current_user_id)
):
    """Create new service record"""
    try:
        service = get_your_service()
        
        record_id = await service.create_record(
            name=name,
            config=config.dict(),
            created_by=current_user
        )
        
        if record_id:
            return YourServiceResponse(
                success=True,
                message="Record created successfully",
                data={"record_id": record_id, "config": config.dict()}
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to create record")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create record for {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create record: {str(e)}")


@router.delete("/{record_id}", response_model=YourServiceResponse)
async def delete_record(
    record_id: str,
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Delete service record"""
    try:
        service = get_your_service()
        
        success = await service.delete_record(record_id)
        
        if success:
            return YourServiceResponse(
                success=True,
                message="Record deleted successfully"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to delete record")
            
    except Exception as e:
        logger.error(f"Failed to delete record {record_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete record: {str(e)}")
```

## Middleware Configuration

### Step 1: Add Permission Mapping

Edit `/apps/api/authn_authz_middleware.py` and add your endpoints to the `get_endpoint_permission` function:

```python
def get_endpoint_permission(path: str, method: str) -> Optional[str]:
    """Map endpoint paths to required permissions"""
    
    # ... existing mappings ...
    
    elif path.startswith("/v1/your-service"):
        if method in ["POST", "PUT", "DELETE"]:
            return "your_service:write:tenant"  # Write operations require write access
        return "your_service:read:tenant"  # Read operations require read access
    
    # ... rest of function ...
```

### Step 2: Update Role Permissions (Optional)

If you need to create new permission types, edit the `ROLE_PERMISSIONS` in the same file:

```python
ROLE_PERMISSIONS = {
    "TENANT_ADMIN": [
        "observability:*:tenant",
        "your_service:*:tenant",  # Full access for tenant admins
        # ... other permissions ...
    ],
    "DEVOPS_ENGINEER": [
        "observability:*:tenant",
        "your_service:*:tenant",  # Full access for devops
        # ... other permissions ...
    ],
    "DEVELOPER": [
        "observability:read:tenant",
        "your_service:read:tenant",  # Read-only for developers
        # ... other permissions ...
    ],
}
```

## Registration in main.py

### Step 1: Import the Router

Edit `/apps/api/main.py` and add your router import:

```python
# Import API routers for additional functionality
from routers.security_api import router as security_router
from routers.observability_api import router as observability_router
from routers.your_service_api import router as your_service_router  # Add this line
```

### Step 2: Include the Router

Add your router to the app:

```python
# Include additional API routers
app.include_router(security_router)
app.include_router(observability_router)
app.include_router(your_service_router)  # Add this line
```

## Testing

### Step 1: Create Constants File (Optional)

Create `/apps/api/constants/your_constants.py`:

```python
"""
Your Service Constants
"""

# Valid configuration types
VALID_CONFIG_TYPES = [
    "your_service_config_1",
    "your_service_config_2"
]

# Default configurations
DEFAULT_CONFIG = {
    "enabled": True,
    "settings": {
        "timeout": 30,
        "retries": 3
    }
}
```

### Step 2: Test the Endpoints

Test your new endpoints:

```bash
# Get all records
curl -X GET "http://localhost:8080/v1/your-service/" \
     -H "X-Customer-ID: test-customer" \
     -H "Authorization: Bearer your-token"

# Create a record
curl -X POST "http://localhost:8080/v1/your-service/" \
     -H "Content-Type: application/json" \
     -H "X-Customer-ID: test-customer" \
     -H "Authorization: Bearer your-token" \
     -d '{
       "enabled": true,
       "settings": {"key": "value"},
       "description": "Test configuration"
     }' \
     -G -d "name=test-config"

# Get specific record
curl -X GET "http://localhost:8080/v1/your-service/record-id" \
     -H "X-Customer-ID: test-customer" \
     -H "Authorization: Bearer your-token"
```

## Example: Complete Implementation

Here's how the streaming configuration was implemented following this pattern:

### Files Created:
1. `/apps/api/constants/streaming_config.py` - Constants and defaults
2. `/apps/api/dao/streaming_config_dao.py` - Database access layer
3. `/apps/api/services/streaming_config_service.py` - Business logic
4. `/apps/api/routers/streaming_config_api.py` - REST API endpoints

### Database Layer Changes:
```python
# Added to database_layer.py
AUTHORIZED_SERVICES = {
    'StreamingConfigDAO': os.getenv('STREAMING_CONFIG_SERVICE_KEY', 'streaming-config-service-key'),
}

TABLE_ACCESS_CONTROL = {
    'StreamingConfigDAO': ['tenant_configs_mt'],
}

UPDATE_ALLOWED_SERVICES = [..., 'StreamingConfigDAO']
```

### Middleware Changes:
```python
# Added to authn_authz_middleware.py
elif path.startswith("/v1/streaming/config"):
    if method in ["POST", "PUT", "DELETE"]:
        return "observability:write:tenant"
    return "observability:read:tenant"
```

### Main App Registration:
```python
# Added to main.py
from routers.streaming_config_api import router as streaming_config_router
app.include_router(streaming_config_router)
```

## Best Practices

1. **Security First**: Always configure proper database permissions before implementing functionality
2. **Error Handling**: Use proper exception handling and logging in all layers
3. **Validation**: Validate input data in both Pydantic models and service layer
4. **Caching**: Use Redis for frequently accessed data
5. **Documentation**: Document your API endpoints with clear descriptions
6. **Testing**: Test all endpoints with various scenarios including edge cases
7. **Monitoring**: Add appropriate logging for debugging and monitoring
8. **Constants**: Use constants files for configuration values and avoid hardcoding

## Troubleshooting

### Common Issues:

1. **"Invalid credentials for service"**: Service not added to `AUTHORIZED_SERVICES`
2. **"Not authorized to access table"**: Table not added to `TABLE_ACCESS_CONTROL`
3. **"Not authorized for UPDATE operations"**: Service not added to `UPDATE_ALLOWED_SERVICES`
4. **"Insufficient permissions"**: Endpoint not mapped in middleware
5. **404 errors**: Router not imported/included in main.py
6. **Import errors**: Missing dependencies or circular imports

### Debug Steps:

1. Check database layer configuration
2. Verify middleware permission mapping
3. Ensure router is registered in main.py
4. Test with admin role first
5. Check application logs for specific errors
6. Verify database table exists and has correct schema

Following this guide ensures your new components integrate properly with Logforge's security, middleware, and database systems.