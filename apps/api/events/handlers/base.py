"""
Base classes for event handlers
"""

from abc import ABC, abstractmethod
from typing import List
import structlog

from ..base import BaseEvent

logger = structlog.get_logger(__name__)


class EventHandler(ABC):
    """Abstract base class for event handlers"""

    @abstractmethod
    async def handle(self, event: BaseEvent) -> bool:
        """Handle a single event"""
        pass

    @abstractmethod
    def get_supported_event_types(self) -> List[str]:
        """Get list of event types this handler supports"""
        pass

    @abstractmethod
    def get_handler_name(self) -> str:
        """Get the name of this handler"""
        pass