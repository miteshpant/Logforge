"""
Simple Event Types
Basic event definitions for log ingestion tracking
"""

import json
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
import structlog

from ..constants.events_constants import EVENT_LOGS_BATCH_INGESTED

logger = structlog.get_logger(__name__)

@dataclass
class LogIngestionEvent:
    """Event published when logs are ingested"""
    
    # Event metadata
    event_id: str
    event_type: str = EVENT_LOGS_BATCH_INGESTED
    timestamp: datetime = None
    
    # Tenant information
    tenant_id: str = ""
    customer_id: str = ""
    
    # Ingestion details
    endpoint: str = ""
    log_count: int = 0
    data_size_bytes: int = 0
    data_size_gb: float = 0.0
    processing_time_ms: float = 0.0
    format_type: str = "json"
    
    # Optional tracking
    user_id: str = ""
    ingested_at: str = ""
    
    def __post_init__(self):
        if not self.event_id:
            self.event_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc)
        if not self.ingested_at:
            self.ingested_at = self.timestamp.isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert datetime to ISO string
        if isinstance(data["timestamp"], datetime):
            data["timestamp"] = data["timestamp"].isoformat()
        return data
    
    def to_json(self) -> str:
        """Convert event to JSON string"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogIngestionEvent":
        """Create event from dictionary"""
        # Convert ISO string back to datetime if needed
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> "LogIngestionEvent":
        """Create event from JSON string"""
        return cls.from_dict(json.loads(json_str))