"""
Base Event Framework
Core event classes and interfaces for the event-driven architecture
"""

import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class EventPriority(str, Enum):
    """Event priority levels for processing order"""
    CRITICAL = "critical"    # System-critical events (alerts, security)
    HIGH = "high"           # Important business events (usage, billing)
    MEDIUM = "medium"       # Standard operational events (logs, metrics)
    LOW = "low"             # Background analytics events


class EventStatus(str, Enum):
    """Event processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class EventMetadata:
    """Metadata for event tracking and debugging"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None
    source_service: str = "unknown"
    source_version: str = "1.0"
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    priority: EventPriority = EventPriority.MEDIUM
    status: EventStatus = EventStatus.PENDING


@dataclass
class BaseEvent:
    """Base class for all events in the system"""
    event_type: str
    customer_id: str
    data: Dict[str, Any]
    metadata: EventMetadata = field(default_factory=EventMetadata)
    
    def __post_init__(self):
        """Validate event after initialization"""
        if not self.event_type:
            raise ValueError("event_type is required")
        if not self.customer_id:
            raise ValueError("customer_id is required")
        if not isinstance(self.data, dict):
            raise ValueError("data must be a dictionary")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization"""
        return {
            "event_type": self.event_type,
            "customer_id": self.customer_id, 
            "data": self.data,
            "metadata": asdict(self.metadata)
        }
    
    def to_json(self) -> str:
        """Convert event to JSON string"""
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseEvent':
        """Create event from dictionary"""
        metadata_dict = data.get("metadata", {})
        metadata = EventMetadata(**metadata_dict)
        
        return cls(
            event_type=data["event_type"],
            customer_id=data["customer_id"],
            data=data["data"],
            metadata=metadata
        )
    
    @classmethod 
    def from_json(cls, json_str: str) -> 'BaseEvent':
        """Create event from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def get_partition_key(self) -> str:
        """Get partition key for event routing"""
        return self.customer_id
    
    def mark_processing(self):
        """Mark event as being processed"""
        self.metadata.status = EventStatus.PROCESSING
        self.metadata.processed_at = datetime.now(timezone.utc)
    
    def mark_completed(self):
        """Mark event as completed"""
        self.metadata.status = EventStatus.COMPLETED
    
    def mark_failed(self, error: str = ""):
        """Mark event as failed"""
        self.metadata.status = EventStatus.FAILED
        if error:
            self.data["error"] = error
    
    def should_retry(self) -> bool:
        """Check if event should be retried"""
        return (self.metadata.status == EventStatus.FAILED and 
                self.metadata.retry_count < self.metadata.max_retries)
    
    def increment_retry(self):
        """Increment retry count"""
        self.metadata.retry_count += 1
        self.metadata.status = EventStatus.RETRYING


class EventPublisher(ABC):
    """Abstract base class for event publishers"""
    
    @abstractmethod
    async def publish(self, event: BaseEvent) -> bool:
        """Publish an event"""
        pass
    
    @abstractmethod
    async def publish_batch(self, events: List[BaseEvent]) -> Dict[str, bool]:
        """Publish multiple events in batch"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if publisher is healthy"""
        pass
    
    @abstractmethod
    async def close(self):
        """Close publisher and cleanup resources"""
        pass


class EventSubscriber(ABC):
    """Abstract base class for event subscribers"""
    
    @abstractmethod
    async def handle_event(self, event: BaseEvent) -> bool:
        """Handle a single event"""
        pass
    
    @abstractmethod
    async def handle_batch(self, events: List[BaseEvent]) -> Dict[str, bool]:
        """Handle multiple events in batch"""
        pass
    
    @abstractmethod
    def get_subscribed_events(self) -> List[str]:
        """Get list of event types this subscriber handles"""
        pass
    
    @abstractmethod
    async def start(self):
        """Start the subscriber"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop the subscriber"""
        pass


class EventValidator:
    """Event validation utilities"""
    
    @staticmethod
    def validate_event_type(event_type: str) -> bool:
        """Validate event type format"""
        if not event_type or not isinstance(event_type, str):
            return False
        
        # Event type should be in format: category.action
        parts = event_type.split(".")
        return len(parts) >= 2 and all(part.isalnum() or part == "_" for part in parts)
    
    @staticmethod
    def validate_customer_id(customer_id: str) -> bool:
        """Validate customer ID format"""
        if not customer_id or not isinstance(customer_id, str):
            return False
        
        # Customer ID should be UUID or alphanumeric
        return len(customer_id) > 0 and len(customer_id) <= 255
    
    @staticmethod
    def validate_event_data(data: Dict[str, Any]) -> List[str]:
        """Validate event data and return list of errors"""
        errors = []
        
        if not isinstance(data, dict):
            errors.append("Event data must be a dictionary")
            return errors
        
        # Check for required fields based on event type
        # This can be extended with schema validation
        
        return errors


class EventError(Exception):
    """Base exception for event system errors"""
    pass


class EventPublishError(EventError):
    """Exception raised when event publishing fails"""
    pass


class EventSubscribeError(EventError):
    """Exception raised when event subscription fails"""
    pass


class EventValidationError(EventError):
    """Exception raised when event validation fails"""
    pass


# Event factory for creating typed events
class EventFactory:
    """Factory for creating specific event types"""
    
    _event_registry: Dict[str, type] = {}
    
    @classmethod
    def register_event_type(cls, event_type: str, event_class: type):
        """Register a custom event class"""
        cls._event_registry[event_type] = event_class
    
    @classmethod
    def create_event(cls, event_type: str, customer_id: str, 
                    data: Dict[str, Any], **kwargs) -> BaseEvent:
        """Create an event of the specified type"""
        
        # Validate inputs
        if not EventValidator.validate_event_type(event_type):
            raise EventValidationError(f"Invalid event type: {event_type}")
        
        if not EventValidator.validate_customer_id(customer_id):
            raise EventValidationError(f"Invalid customer ID: {customer_id}")
        
        validation_errors = EventValidator.validate_event_data(data)
        if validation_errors:
            raise EventValidationError(f"Event data validation failed: {validation_errors}")
        
        # Create metadata
        metadata = EventMetadata(**kwargs)
        
        # Use registered event class if available, otherwise BaseEvent
        event_class = cls._event_registry.get(event_type, BaseEvent)
        
        return event_class(
            event_type=event_type,
            customer_id=customer_id,
            data=data,
            metadata=metadata
        )


# Performance monitoring utilities
@dataclass
class EventMetrics:
    """Event processing metrics"""
    events_published: int = 0
    events_consumed: int = 0
    events_failed: int = 0
    avg_processing_time_ms: float = 0.0
    total_processing_time_ms: float = 0.0
    last_event_time: Optional[datetime] = None
    
    def record_event_published(self):
        """Record an event publication"""
        self.events_published += 1
        self.last_event_time = datetime.now(timezone.utc)
    
    def record_event_consumed(self, processing_time_ms: float):
        """Record an event consumption"""
        self.events_consumed += 1
        self.total_processing_time_ms += processing_time_ms
        self.avg_processing_time_ms = self.total_processing_time_ms / self.events_consumed
        self.last_event_time = datetime.now(timezone.utc)
    
    def record_event_failed(self):
        """Record an event failure"""
        self.events_failed += 1
    
    def get_success_rate(self) -> float:
        """Get event processing success rate"""
        total = self.events_consumed + self.events_failed
        return (self.events_consumed / total * 100) if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "events_published": self.events_published,
            "events_consumed": self.events_consumed, 
            "events_failed": self.events_failed,
            "avg_processing_time_ms": self.avg_processing_time_ms,
            "success_rate_percent": self.get_success_rate(),
            "last_event_time": self.last_event_time.isoformat() if self.last_event_time else None
        }


logger.info("Base event framework initialized")