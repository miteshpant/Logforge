"""
Query Resilience Utilities

Provides timeout handling, circuit breakers, and query protection
to prevent slow queries from affecting system stability.
"""

import asyncio
import time
from typing import Any, Callable, Optional, TypeVar, Dict
from functools import wraps
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5       # Failures before opening
    success_threshold: int = 3       # Successes to close from half-open
    timeout_seconds: float = 30.0    # Time before trying half-open
    half_open_max_calls: int = 3     # Max calls in half-open state


@dataclass
class CircuitBreakerState:
    """State tracking for circuit breaker"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    half_open_calls: int = 0


class CircuitBreaker:
    """
    Circuit breaker for database queries.

    Prevents cascade failures by failing fast when a service is unhealthy.
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state.state

    @property
    def is_closed(self) -> bool:
        return self._state.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self._state.state == CircuitState.OPEN

    async def _should_allow_request(self) -> bool:
        """Check if request should be allowed through"""
        async with self._lock:
            if self._state.state == CircuitState.CLOSED:
                return True

            if self._state.state == CircuitState.OPEN:
                # Check if timeout has passed
                if self._state.last_failure_time:
                    elapsed = (datetime.utcnow() - self._state.last_failure_time).total_seconds()
                    if elapsed >= self.config.timeout_seconds:
                        # Transition to half-open
                        self._state.state = CircuitState.HALF_OPEN
                        self._state.half_open_calls = 0
                        self._state.success_count = 0
                        logger.info(
                            "Circuit breaker transitioning to half-open",
                            name=self.name
                        )
                        return True
                return False

            if self._state.state == CircuitState.HALF_OPEN:
                # Allow limited calls in half-open
                if self._state.half_open_calls < self.config.half_open_max_calls:
                    self._state.half_open_calls += 1
                    return True
                return False

            return False

    async def record_success(self):
        """Record a successful call"""
        async with self._lock:
            if self._state.state == CircuitState.HALF_OPEN:
                self._state.success_count += 1
                if self._state.success_count >= self.config.success_threshold:
                    # Close the circuit
                    self._state.state = CircuitState.CLOSED
                    self._state.failure_count = 0
                    self._state.success_count = 0
                    logger.info("Circuit breaker closed", name=self.name)

            elif self._state.state == CircuitState.CLOSED:
                # Reset failure count on success
                self._state.failure_count = 0

    async def record_failure(self):
        """Record a failed call"""
        async with self._lock:
            self._state.failure_count += 1
            self._state.last_failure_time = datetime.utcnow()

            if self._state.state == CircuitState.HALF_OPEN:
                # Immediately open on failure in half-open
                self._state.state = CircuitState.OPEN
                logger.warning("Circuit breaker re-opened", name=self.name)

            elif self._state.state == CircuitState.CLOSED:
                if self._state.failure_count >= self.config.failure_threshold:
                    self._state.state = CircuitState.OPEN
                    logger.warning(
                        "Circuit breaker opened",
                        name=self.name,
                        failures=self._state.failure_count
                    )

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection"""
        if not await self._should_allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is open"
            )

        try:
            result = await func(*args, **kwargs)
            await self.record_success()
            return result
        except Exception as e:
            await self.record_failure()
            raise

    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status"""
        return {
            "name": self.name,
            "state": self._state.state.value,
            "failure_count": self._state.failure_count,
            "success_count": self._state.success_count,
            "last_failure": self._state.last_failure_time.isoformat() if self._state.last_failure_time else None
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


class QueryTimeoutError(Exception):
    """Raised when query exceeds timeout"""
    pass


async def with_timeout(
    coro,
    timeout_seconds: float,
    operation_name: str = "query"
) -> Any:
    """
    Execute coroutine with timeout.

    Args:
        coro: Coroutine to execute
        timeout_seconds: Maximum execution time
        operation_name: Name for logging

    Returns:
        Result of coroutine

    Raises:
        QueryTimeoutError: If operation times out
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(
            "Query timeout",
            operation=operation_name,
            timeout_seconds=timeout_seconds
        )
        raise QueryTimeoutError(
            f"Operation '{operation_name}' timed out after {timeout_seconds}s"
        )


def query_with_timeout(timeout_seconds: float = 30.0):
    """
    Decorator to add timeout to async query functions.

    Usage:
        @query_with_timeout(timeout_seconds=10.0)
        async def slow_query():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await with_timeout(
                func(*args, **kwargs),
                timeout_seconds,
                operation_name=func.__name__
            )
        return wrapper
    return decorator


# Global circuit breakers for different services
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
    """Get or create a circuit breaker by name"""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
    return _circuit_breakers[name]


# Pre-configured circuit breakers for common services
def get_db_circuit_breaker() -> CircuitBreaker:
    """Circuit breaker for database operations"""
    return get_circuit_breaker("database", CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=3,
        timeout_seconds=30.0
    ))


def get_redis_circuit_breaker() -> CircuitBreaker:
    """Circuit breaker for Redis operations"""
    return get_circuit_breaker("redis", CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=15.0
    ))


def get_external_api_circuit_breaker() -> CircuitBreaker:
    """Circuit breaker for external API calls"""
    return get_circuit_breaker("external_api", CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=60.0
    ))


def get_all_circuit_breaker_status() -> Dict[str, Dict[str, Any]]:
    """Get status of all circuit breakers"""
    return {name: cb.get_status() for name, cb in _circuit_breakers.items()}
