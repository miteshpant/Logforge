"""
Event System API Endpoints
Health checks and management for the event-driven architecture
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
import structlog

from dependencies import event_publisher_manager, event_subscriber_manager, kafka_admin

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/events", tags=["events"])


@router.get("/health")
async def get_event_system_health() -> Dict[str, Any]:
    """Get comprehensive health status of the event system"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": str(datetime.now()),
            "components": {}
        }
        
        # Check publisher manager health
        if event_publisher_manager:
            publisher_health = await event_publisher_manager.health_check()
            health_status["components"]["publisher"] = publisher_health
        else:
            health_status["components"]["publisher"] = {"status": "not_initialized"}
            health_status["status"] = "degraded"
        
        # Check subscriber manager health
        if event_subscriber_manager:
            subscriber_health = event_subscriber_manager.get_health_status()
            health_status["components"]["subscriber"] = subscriber_health
        else:
            health_status["components"]["subscriber"] = {"status": "not_initialized"}
            health_status["status"] = "degraded"
        
        # Check Kafka admin health
        if kafka_admin:
            kafka_healthy = await kafka_admin.health_check()
            health_status["components"]["kafka"] = {
                "status": "healthy" if kafka_healthy else "unhealthy",
                "admin_connected": kafka_healthy
            }
            
            if not kafka_healthy:
                health_status["status"] = "degraded"
        else:
            health_status["components"]["kafka"] = {"status": "not_available"}
        
        # Overall status determination
        component_statuses = [
            comp.get("status", "unknown") 
            for comp in health_status["components"].values()
        ]
        
        if "unhealthy" in component_statuses:
            health_status["status"] = "unhealthy"
        elif "degraded" in component_statuses or "not_initialized" in component_statuses:
            health_status["status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error getting event system health: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")


@router.get("/metrics")
async def get_event_system_metrics() -> Dict[str, Any]:
    """Get detailed metrics from the event system"""
    try:
        metrics = {
            "timestamp": str(datetime.now()),
            "publisher_metrics": {},
            "subscriber_metrics": {},
            "kafka_metrics": {}
        }
        
        # Get publisher metrics
        if event_publisher_manager:
            metrics["publisher_metrics"] = event_publisher_manager.get_metrics()
        
        # Get subscriber metrics
        if event_subscriber_manager:
            metrics["subscriber_metrics"] = event_subscriber_manager.get_metrics()
        
        # Get Kafka admin metrics
        if kafka_admin:
            metrics["kafka_metrics"] = kafka_admin.get_metrics()
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting event system metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Metrics retrieval failed: {e}")


@router.get("/topics")
async def list_kafka_topics() -> Dict[str, Any]:
    """List all Kafka topics in the cluster"""
    try:
        if not kafka_admin:
            raise HTTPException(status_code=503, detail="Kafka admin not available")
        
        topics = await kafka_admin.list_topics()
        
        return {
            "topics": topics,
            "topic_count": len(topics),
            "timestamp": str(datetime.now())
        }
        
    except Exception as e:
        logger.error(f"Error listing Kafka topics: {e}")
        raise HTTPException(status_code=500, detail=f"Topic listing failed: {e}")


@router.get("/topics/{topic_name}")
async def describe_kafka_topic(topic_name: str) -> Dict[str, Any]:
    """Get detailed information about a specific Kafka topic"""
    try:
        if not kafka_admin:
            raise HTTPException(status_code=503, detail="Kafka admin not available")
        
        topic_info = await kafka_admin.describe_topic(topic_name)
        
        if not topic_info:
            raise HTTPException(status_code=404, detail=f"Topic '{topic_name}' not found")
        
        return topic_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error describing topic {topic_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Topic description failed: {e}")


@router.get("/cluster")
async def get_kafka_cluster_info() -> Dict[str, Any]:
    """Get Kafka cluster information"""
    try:
        if not kafka_admin:
            raise HTTPException(status_code=503, detail="Kafka admin not available")
        
        cluster_info = await kafka_admin.get_cluster_info()
        
        return cluster_info
        
    except Exception as e:
        logger.error(f"Error getting cluster info: {e}")
        raise HTTPException(status_code=500, detail=f"Cluster info retrieval failed: {e}")


@router.post("/topics/{topic_key}/create")
async def create_kafka_topic(topic_key: str, validate_only: bool = False) -> Dict[str, Any]:
    """Create a Kafka topic based on configuration"""
    try:
        if not kafka_admin:
            raise HTTPException(status_code=503, detail="Kafka admin not available")
        
        success = await kafka_admin.create_topic(topic_key, validate_only=validate_only)
        
        if success:
            action = "validated" if validate_only else "created"
            return {
                "success": True,
                "message": f"Topic '{topic_key}' {action} successfully",
                "topic_key": topic_key,
                "validate_only": validate_only
            }
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to {'validate' if validate_only else 'create'} topic '{topic_key}'"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating topic {topic_key}: {e}")
        raise HTTPException(status_code=500, detail=f"Topic creation failed: {e}")


@router.post("/setup")
async def setup_event_system() -> Dict[str, Any]:
    """Setup the complete event system (topics, etc.)"""
    try:
        if not kafka_admin:
            raise HTTPException(status_code=503, detail="Kafka admin not available")
        
        setup_results = await kafka_admin.setup_cluster(create_missing_topics=True)
        
        return {
            "success": True,
            "message": "Event system setup completed",
            "setup_results": setup_results,
            "timestamp": str(datetime.now())
        }
        
    except Exception as e:
        logger.error(f"Error setting up event system: {e}")
        raise HTTPException(status_code=500, detail=f"Event system setup failed: {e}")


@router.get("/config")
async def get_event_system_config() -> Dict[str, Any]:
    """Get event system configuration summary"""
    try:
        from events.config import events_config_manager
        
        config_summary = events_config_manager.get_config_summary()
        
        return config_summary
        
    except Exception as e:
        logger.error(f"Error getting event system config: {e}")
        raise HTTPException(status_code=500, detail=f"Config retrieval failed: {e}")


# Add necessary imports at the top
from datetime import datetime

logger.info("Event system API endpoints loaded")