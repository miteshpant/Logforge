"""
Schema Registry API

Allows customers to pre-register their log schemas for instant normalization.
Pre-registration eliminates runtime computation - logs are normalized in ~10μs.

This is the "index-time extraction" approach used by Elasticsearch and Splunk
for high-performance log processing.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
import structlog

from middleware.auth_middleware import get_current_customer_id
from services.high_performance_normalizer import (
    get_high_performance_normalizer,
    HighPerformanceNormalizer
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/schemas", tags=["schema-registry"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class FieldMapping(BaseModel):
    """Single field mapping definition"""
    customer_field: str = Field(..., description="Field name in customer's logs")
    standard_field: str = Field(..., description="Standard Sigma/MITRE field name")
    description: Optional[str] = Field(None, description="Optional description")


class SchemaRegistrationRequest(BaseModel):
    """Request to register a new log schema"""
    schema_name: str = Field(..., description="Human-readable schema name (e.g., 'nginx-access-logs')")
    description: Optional[str] = Field(None, description="Schema description")
    log_source: str = Field(..., description="Log source type (e.g., 'nginx', 'apache', 'syslog')")
    field_mappings: List[FieldMapping] = Field(..., description="List of field mappings")
    sample_log: Optional[Dict[str, Any]] = Field(None, description="Optional sample log for validation")

    class Config:
        json_schema_extra = {
            "example": {
                "schema_name": "nginx-access-logs",
                "description": "Nginx access log format with custom fields",
                "log_source": "nginx",
                "field_mappings": [
                    {"customer_field": "remote_addr", "standard_field": "source_ip"},
                    {"customer_field": "request_uri", "standard_field": "url_path"},
                    {"customer_field": "status", "standard_field": "status_code"},
                    {"customer_field": "request_method", "standard_field": "http_method"},
                    {"customer_field": "http_user_agent", "standard_field": "user_agent"}
                ],
                "sample_log": {
                    "remote_addr": "192.168.1.100",
                    "request_uri": "/api/users",
                    "status": 200,
                    "request_method": "GET"
                }
            }
        }


class SchemaRegistrationResponse(BaseModel):
    """Response after schema registration"""
    schema_id: str
    schema_name: str
    fields_registered: int
    message: str


class SchemaInfo(BaseModel):
    """Information about a registered schema"""
    schema_id: str
    schema_name: str
    log_source: str
    fields_count: int
    hit_count: int
    created_at: float


class NormalizerStatsResponse(BaseModel):
    """Normalizer performance statistics"""
    total_logs_processed: int
    bloom_filter_rejections: int
    bloom_filter_rejection_rate: float
    known_field_variations: int
    total_schemas: int
    cache_hits: int
    cache_misses: int
    hit_rate: float


class StandardFieldsResponse(BaseModel):
    """List of standard field names supported"""
    standard_fields: List[str]
    field_variations: Dict[str, List[str]]


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/register", response_model=SchemaRegistrationResponse)
async def register_schema(
    request: SchemaRegistrationRequest,
    customer_id: str = Depends(get_current_customer_id)
):
    """
    Register a log schema for instant normalization.

    Pre-registering your log schema eliminates runtime computation.
    Logs matching this schema will be normalized in ~10μs instead of ~1ms.

    **Benefits:**
    - 100x faster normalization for known schemas
    - Guaranteed field mapping consistency
    - No regex evaluation at runtime
    - Better Sigma rule matching accuracy

    **When to use:**
    - High-volume log sources (>10k logs/sec)
    - Critical security logs requiring fast processing
    - Custom log formats with non-standard field names
    """
    try:
        normalizer = get_high_performance_normalizer()

        # Convert field mappings to dict format
        field_mapping_dict = {
            mapping.customer_field: mapping.standard_field
            for mapping in request.field_mappings
        }

        # Validate sample log if provided
        if request.sample_log:
            # Check that all mapped fields exist in sample
            missing_fields = set(field_mapping_dict.keys()) - set(request.sample_log.keys())
            if missing_fields:
                logger.warning(
                    f"Sample log missing some mapped fields",
                    missing=list(missing_fields),
                    customer_id=customer_id
                )

        # Register schema
        schema_id = normalizer.register_customer_schema(
            customer_id=customer_id,
            schema_name=request.schema_name,
            field_mappings=field_mapping_dict
        )

        logger.info(
            f"Schema registered successfully",
            customer_id=customer_id,
            schema_name=request.schema_name,
            schema_id=schema_id,
            fields_count=len(field_mapping_dict)
        )

        return SchemaRegistrationResponse(
            schema_id=schema_id,
            schema_name=request.schema_name,
            fields_registered=len(field_mapping_dict),
            message=f"Schema '{request.schema_name}' registered successfully. Logs with these fields will be normalized instantly."
        )

    except Exception as e:
        logger.error(f"Failed to register schema: {e}", customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to register schema: {str(e)}")


@router.get("/list", response_model=List[SchemaInfo])
async def list_schemas(
    customer_id: str = Depends(get_current_customer_id)
):
    """
    List all registered schemas for the customer.

    Returns schema metadata including hit counts to help identify
    which schemas are being used most frequently.
    """
    try:
        normalizer = get_high_performance_normalizer()

        # Filter schemas for this customer
        customer_prefix = f"{customer_id}:"
        schemas = []

        for schema_key, schema in normalizer.schema_registry.schemas.items():
            if schema_key.startswith(customer_prefix):
                # Parse schema key: customer_id:source_type:fingerprint
                parts = schema_key.split(":")
                source_type = parts[1] if len(parts) > 1 else "unknown"

                schemas.append(SchemaInfo(
                    schema_id=schema.schema_id,
                    schema_name=source_type,
                    log_source=source_type,
                    fields_count=len(schema.field_mapping),
                    hit_count=schema.hit_count,
                    created_at=schema.created_at
                ))

        # Sort by hit count (most used first)
        schemas.sort(key=lambda s: s.hit_count, reverse=True)

        return schemas

    except Exception as e:
        logger.error(f"Failed to list schemas: {e}", customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to list schemas: {str(e)}")


@router.delete("/{schema_id}")
async def delete_schema(
    schema_id: str,
    customer_id: str = Depends(get_current_customer_id)
):
    """
    Delete a registered schema.

    After deletion, logs with this structure will use runtime normalization
    (slower, but still functional).
    """
    try:
        normalizer = get_high_performance_normalizer()

        # Verify schema belongs to customer
        if not schema_id.startswith(f"{customer_id}:"):
            raise HTTPException(status_code=403, detail="Schema does not belong to this customer")

        # Delete schema
        if schema_id in normalizer.schema_registry.schemas:
            del normalizer.schema_registry.schemas[schema_id]
            normalizer.schema_registry.customer_schema_counts[customer_id] -= 1

            logger.info(f"Schema deleted", schema_id=schema_id, customer_id=customer_id)

            return {"message": f"Schema '{schema_id}' deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Schema not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete schema: {e}", customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to delete schema: {str(e)}")


@router.get("/stats", response_model=NormalizerStatsResponse)
async def get_normalizer_stats(
    customer_id: str = Depends(get_current_customer_id)
):
    """
    Get normalizer performance statistics.

    Use this to monitor:
    - Cache hit rate (should be >95% for good performance)
    - Bloom filter rejection rate (logs skipped because no known fields)
    - Total schemas registered
    """
    try:
        normalizer = get_high_performance_normalizer()
        stats = normalizer.get_stats()

        return NormalizerStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Failed to get stats: {e}", customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/standard-fields", response_model=StandardFieldsResponse)
async def get_standard_fields():
    """
    Get list of standard field names supported for normalization.

    These are the Sigma/MITRE standard field names that your customer
    fields can be mapped to. Using these standard names enables
    Sigma rule matching across different log formats.
    """
    try:
        normalizer = get_high_performance_normalizer()

        # Group by standard field
        field_variations: Dict[str, List[str]] = {}
        for customer_field, standard_field in normalizer.reverse_mapping.items():
            if standard_field not in field_variations:
                field_variations[standard_field] = []
            field_variations[standard_field].append(customer_field)

        return StandardFieldsResponse(
            standard_fields=list(field_variations.keys()),
            field_variations=field_variations
        )

    except Exception as e:
        logger.error(f"Failed to get standard fields: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get standard fields: {str(e)}")


@router.post("/test-normalization")
async def test_normalization(
    log_entry: Dict[str, Any],
    customer_id: str = Depends(get_current_customer_id)
):
    """
    Test normalization of a sample log.

    Use this to verify your field mappings work correctly before
    registering a schema. Shows which fields were normalized and
    to what standard names.
    """
    try:
        normalizer = get_high_performance_normalizer()

        # Normalize the log
        normalized = normalizer.normalize(log_entry, customer_id, "test")

        # Find which fields were mapped
        mapped_fields = {}
        for original_field in log_entry.keys():
            if original_field.lower() in normalizer.reverse_mapping:
                standard = normalizer.reverse_mapping[original_field.lower()]
                mapped_fields[original_field] = standard

        return {
            "original_log": log_entry,
            "normalized_log": normalized,
            "fields_mapped": mapped_fields,
            "fields_count": len(mapped_fields),
            "recommendation": "Register this schema for 100x faster normalization" if mapped_fields else "No mappable fields found"
        }

    except Exception as e:
        logger.error(f"Failed to test normalization: {e}", customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to test normalization: {str(e)}")
