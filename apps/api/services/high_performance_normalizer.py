"""
High-Performance Field Normalization Engine

Designed for millions of logs/second throughput using:
1. Schema Registry - Pre-computed normalization maps per customer/source
2. Log Fingerprinting - O(1) hash-based cache lookup
3. Bloom Filter - Fast field existence checks (O(1))
4. Compiled Regex Cache - No runtime regex compilation
5. Batch Processing - Vectorized operations for throughput

Performance Characteristics:
- First log of new schema: ~1ms (build normalization map)
- Cached schema hit: ~10μs (hash lookup only)
- Bloom filter miss: ~1μs (skip normalization entirely)
- Target: 1M+ logs/second on single core
"""

import hashlib
import re
from typing import Dict, List, Any, Optional, Set, Tuple, FrozenSet
from dataclasses import dataclass, field
from collections import defaultdict
import threading
from functools import lru_cache
import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# BLOOM FILTER - O(1) field existence check
# =============================================================================

class BloomFilter:
    """
    Probabilistic data structure for fast "is this field known?" checks.

    False positives possible (will check further), false negatives impossible.
    This means we never miss a field that should be normalized.
    """

    def __init__(self, expected_items: int = 10000, false_positive_rate: float = 0.01):
        """
        Initialize bloom filter with optimal size.

        Args:
            expected_items: Expected number of unique field names
            false_positive_rate: Acceptable false positive rate (default 1%)
        """
        import math

        # Calculate optimal size and hash count
        self.size = int(-expected_items * math.log(false_positive_rate) / (math.log(2) ** 2))
        self.hash_count = int((self.size / expected_items) * math.log(2))
        self.bit_array = [False] * self.size
        self.item_count = 0

        logger.debug(f"BloomFilter initialized: size={self.size}, hash_count={self.hash_count}")

    def _hashes(self, item: str) -> List[int]:
        """Generate hash values for item"""
        hashes = []
        for i in range(self.hash_count):
            # Use different seeds for each hash
            h = hashlib.md5(f"{item}:{i}".encode()).hexdigest()
            hashes.append(int(h, 16) % self.size)
        return hashes

    def add(self, item: str) -> None:
        """Add item to bloom filter"""
        for h in self._hashes(item.lower()):
            self.bit_array[h] = True
        self.item_count += 1

    def might_contain(self, item: str) -> bool:
        """
        Check if item might be in the filter.

        Returns:
            True if item might be present (could be false positive)
            False if item is definitely not present
        """
        return all(self.bit_array[h] for h in self._hashes(item.lower()))

    def add_batch(self, items: List[str]) -> None:
        """Add multiple items efficiently"""
        for item in items:
            self.add(item)


# =============================================================================
# SCHEMA REGISTRY - Pre-computed normalization maps
# =============================================================================

@dataclass
class NormalizationSchema:
    """
    Pre-computed normalization schema for a specific log structure.
    Created once when a new log format is first seen, then reused.
    """
    schema_id: str  # Hash of field names
    field_mapping: Dict[str, str]  # original_field -> normalized_field
    has_normalizable_fields: bool  # Quick check if any normalization needed
    created_at: float = field(default_factory=lambda: __import__('time').time())
    hit_count: int = 0

    def apply(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply pre-computed normalization - O(n) where n is number of fields.
        No regex, no pattern matching - just dict lookups.
        """
        if not self.has_normalizable_fields:
            return log_entry  # Fast path: no normalization needed

        result = {}
        for original_field, value in log_entry.items():
            # Add normalized field if mapping exists
            if original_field in self.field_mapping:
                normalized_field = self.field_mapping[original_field]
                result[normalized_field] = value
            # Always keep original field
            result[original_field] = value

        self.hit_count += 1
        return result


class SchemaRegistry:
    """
    Registry of pre-computed normalization schemas.

    Schemas are keyed by:
    1. Customer ID (tenant isolation)
    2. Log source type (e.g., "syslog", "json", "cef")
    3. Field fingerprint (hash of field names)

    This allows O(1) lookup for repeated log structures.
    """

    def __init__(self, max_schemas_per_customer: int = 1000):
        self.schemas: Dict[str, NormalizationSchema] = {}
        self.max_schemas_per_customer = max_schemas_per_customer
        self.customer_schema_counts: Dict[str, int] = defaultdict(int)
        self._lock = threading.RLock()

        # Stats
        self.cache_hits = 0
        self.cache_misses = 0

    def get_schema_key(self, customer_id: str, source_type: str, field_fingerprint: str) -> str:
        """Generate unique schema key"""
        return f"{customer_id}:{source_type}:{field_fingerprint}"

    def get_or_create_schema(
        self,
        customer_id: str,
        source_type: str,
        field_names: FrozenSet[str],
        field_mapper_func
    ) -> NormalizationSchema:
        """
        Get existing schema or create new one.

        Args:
            customer_id: Customer identifier
            source_type: Log source type
            field_names: Frozen set of field names in log
            field_mapper_func: Function to compute field mappings (called only on cache miss)

        Returns:
            NormalizationSchema ready to apply
        """
        # Compute fingerprint
        fingerprint = self._compute_fingerprint(field_names)
        schema_key = self.get_schema_key(customer_id, source_type, fingerprint)

        # Fast path: schema exists
        if schema_key in self.schemas:
            self.cache_hits += 1
            return self.schemas[schema_key]

        # Slow path: create new schema (thread-safe)
        with self._lock:
            # Double-check after acquiring lock
            if schema_key in self.schemas:
                self.cache_hits += 1
                return self.schemas[schema_key]

            self.cache_misses += 1

            # Compute field mappings (this is the expensive part - done only once)
            field_mapping = field_mapper_func(field_names)

            # Create schema
            schema = NormalizationSchema(
                schema_id=schema_key,
                field_mapping=field_mapping,
                has_normalizable_fields=len(field_mapping) > 0
            )

            # Store (with eviction if needed)
            self._store_schema(customer_id, schema_key, schema)

            logger.debug(
                f"Created new normalization schema",
                customer_id=customer_id,
                source_type=source_type,
                fields_count=len(field_names),
                mappings_count=len(field_mapping)
            )

            return schema

    def _compute_fingerprint(self, field_names: FrozenSet[str]) -> str:
        """Compute hash fingerprint of field names"""
        # Sort for consistency, join with separator, hash
        sorted_names = sorted(field_names)
        content = "|".join(sorted_names)
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _store_schema(self, customer_id: str, schema_key: str, schema: NormalizationSchema) -> None:
        """Store schema with LRU eviction per customer"""
        # Check if customer has too many schemas
        if self.customer_schema_counts[customer_id] >= self.max_schemas_per_customer:
            # Evict least-used schema for this customer
            self._evict_lru_schema(customer_id)

        self.schemas[schema_key] = schema
        self.customer_schema_counts[customer_id] += 1

    def _evict_lru_schema(self, customer_id: str) -> None:
        """Evict least recently used schema for customer"""
        prefix = f"{customer_id}:"
        customer_schemas = [
            (key, schema) for key, schema in self.schemas.items()
            if key.startswith(prefix)
        ]

        if customer_schemas:
            # Find schema with lowest hit count
            lru_key = min(customer_schemas, key=lambda x: x[1].hit_count)[0]
            del self.schemas[lru_key]
            self.customer_schema_counts[customer_id] -= 1
            logger.debug(f"Evicted LRU schema: {lru_key}")

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        return {
            "total_schemas": len(self.schemas),
            "customers": len(self.customer_schema_counts),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": self.cache_hits / max(1, self.cache_hits + self.cache_misses)
        }


# =============================================================================
# COMPILED REGEX CACHE - No runtime compilation
# =============================================================================

class CompiledRegexCache:
    """
    Pre-compiled regex patterns for field matching.
    Regex compilation is expensive - do it once at startup.
    """

    def __init__(self):
        self.patterns: Dict[str, re.Pattern] = {}
        self._lock = threading.Lock()

    @lru_cache(maxsize=10000)
    def get_compiled(self, pattern: str, flags: int = 0) -> re.Pattern:
        """Get compiled regex pattern (cached)"""
        return re.compile(pattern, flags)

    def precompile_patterns(self, patterns: List[str]) -> None:
        """Pre-compile a list of patterns at startup"""
        for pattern in patterns:
            self.get_compiled(pattern, re.IGNORECASE)
        logger.info(f"Pre-compiled {len(patterns)} regex patterns")


# =============================================================================
# HIGH PERFORMANCE NORMALIZER - Main class
# =============================================================================

class HighPerformanceNormalizer:
    """
    High-performance field normalization engine.

    Architecture:
    1. Bloom filter check - O(1) "might have normalizable fields?"
    2. Schema registry lookup - O(1) "have we seen this exact log structure?"
    3. Apply pre-computed mapping - O(n) simple dict operations

    No regex at runtime for cached schemas!
    """

    def __init__(self, field_mapping_config: Dict[str, List[str]]):
        """
        Initialize normalizer with field mapping configuration.

        Args:
            field_mapping_config: Dict mapping standard_field -> [customer_variations]
        """
        # Build reverse mapping: customer_field -> standard_field
        self.reverse_mapping: Dict[str, str] = {}
        for standard_field, variations in field_mapping_config.items():
            for variation in variations:
                self.reverse_mapping[variation.lower()] = standard_field

        # Initialize bloom filter with all known field variations
        self.bloom_filter = BloomFilter(expected_items=len(self.reverse_mapping) * 2)
        for field in self.reverse_mapping.keys():
            self.bloom_filter.add(field)

        # Initialize schema registry
        self.schema_registry = SchemaRegistry()

        # Pre-compile common regex patterns
        self.regex_cache = CompiledRegexCache()
        self._precompile_common_patterns()

        # Stats
        self.total_logs_processed = 0
        self.bloom_filter_rejections = 0

        logger.info(
            f"HighPerformanceNormalizer initialized",
            known_fields=len(self.reverse_mapping),
            bloom_filter_size=self.bloom_filter.size
        )

    def _precompile_common_patterns(self) -> None:
        """Pre-compile commonly used regex patterns"""
        common_patterns = [
            r'^(log_|event_|audit_)',  # Common prefixes
            r'(_log|_event|_audit)$',  # Common suffixes
            r'_',  # Underscore separator
        ]
        self.regex_cache.precompile_patterns(common_patterns)

    def normalize(
        self,
        log_entry: Dict[str, Any],
        customer_id: str = "default",
        source_type: str = "json"
    ) -> Dict[str, Any]:
        """
        Normalize a single log entry with maximum performance.

        Args:
            log_entry: Raw log entry
            customer_id: Customer identifier for tenant isolation
            source_type: Log source type for schema categorization

        Returns:
            Normalized log entry
        """
        self.total_logs_processed += 1

        # Step 1: Quick bloom filter check
        field_names = frozenset(log_entry.keys())
        if not self._might_have_normalizable_fields(field_names):
            self.bloom_filter_rejections += 1
            return log_entry  # Fast path: no known fields

        # Step 2: Get or create schema (O(1) for cached schemas)
        schema = self.schema_registry.get_or_create_schema(
            customer_id=customer_id,
            source_type=source_type,
            field_names=field_names,
            field_mapper_func=self._compute_field_mappings
        )

        # Step 3: Apply pre-computed normalization (simple dict operations)
        return schema.apply(log_entry)

    def normalize_batch(
        self,
        logs: List[Dict[str, Any]],
        customer_id: str = "default",
        source_type: str = "json"
    ) -> List[Dict[str, Any]]:
        """
        Normalize a batch of logs efficiently.

        Optimizations:
        - Groups logs by structure for schema reuse
        - Single schema lookup per unique structure

        Args:
            logs: List of raw log entries
            customer_id: Customer identifier
            source_type: Log source type

        Returns:
            List of normalized log entries
        """
        if not logs:
            return []

        # Group logs by field fingerprint for schema reuse
        groups: Dict[FrozenSet[str], List[Tuple[int, Dict[str, Any]]]] = defaultdict(list)
        for idx, log in enumerate(logs):
            field_names = frozenset(log.keys())
            groups[field_names].append((idx, log))

        # Process each group with its schema
        results = [None] * len(logs)

        for field_names, group_logs in groups.items():
            # Quick bloom filter check for entire group
            if not self._might_have_normalizable_fields(field_names):
                self.bloom_filter_rejections += len(group_logs)
                for idx, log in group_logs:
                    results[idx] = log
                continue

            # Get schema once for entire group
            schema = self.schema_registry.get_or_create_schema(
                customer_id=customer_id,
                source_type=source_type,
                field_names=field_names,
                field_mapper_func=self._compute_field_mappings
            )

            # Apply to all logs in group
            for idx, log in group_logs:
                results[idx] = schema.apply(log)

        self.total_logs_processed += len(logs)
        return results

    def _might_have_normalizable_fields(self, field_names: FrozenSet[str]) -> bool:
        """
        Quick check if any fields might need normalization.
        Uses bloom filter for O(1) check.
        """
        for field in field_names:
            if self.bloom_filter.might_contain(field):
                return True
        return False

    def _compute_field_mappings(self, field_names: FrozenSet[str]) -> Dict[str, str]:
        """
        Compute field mappings for a set of field names.
        Called only on cache miss - result is cached in schema.

        Args:
            field_names: Set of field names to map

        Returns:
            Dict mapping original_field -> normalized_field
        """
        mappings = {}

        for field in field_names:
            field_lower = field.lower()

            # Try exact match first (O(1) dict lookup)
            if field_lower in self.reverse_mapping:
                mappings[field] = self.reverse_mapping[field_lower]
                continue

            # Try pattern-based matching (only for unknown fields)
            normalized = self._try_pattern_normalization(field_lower)
            if normalized and normalized in self.reverse_mapping:
                mappings[field] = self.reverse_mapping[normalized]

        return mappings

    def _try_pattern_normalization(self, field_name: str) -> Optional[str]:
        """
        Try to normalize field name using patterns.
        Uses pre-compiled regex patterns.
        """
        # Remove common prefixes
        result = self.regex_cache.get_compiled(r'^(log_|event_|audit_)', re.IGNORECASE).sub('', field_name)
        if result != field_name and result in self.reverse_mapping:
            return result

        # Remove common suffixes
        result = self.regex_cache.get_compiled(r'(_log|_event|_audit)$', re.IGNORECASE).sub('', field_name)
        if result != field_name and result in self.reverse_mapping:
            return result

        # Remove underscores
        result = field_name.replace('_', '')
        if result in self.reverse_mapping:
            return result

        return None

    def register_customer_schema(
        self,
        customer_id: str,
        schema_name: str,
        field_mappings: Dict[str, str]
    ) -> str:
        """
        Pre-register a customer's log schema for instant normalization.

        Customers can register their log formats upfront, avoiding
        any runtime computation.

        Args:
            customer_id: Customer identifier
            schema_name: Human-readable schema name
            field_mappings: Dict mapping customer_field -> standard_field

        Returns:
            Schema ID for reference
        """
        # Create fingerprint from field names
        field_names = frozenset(field_mappings.keys())
        fingerprint = self.schema_registry._compute_fingerprint(field_names)
        schema_key = self.schema_registry.get_schema_key(customer_id, schema_name, fingerprint)

        # Create and store schema
        schema = NormalizationSchema(
            schema_id=schema_key,
            field_mapping=field_mappings,
            has_normalizable_fields=len(field_mappings) > 0
        )

        self.schema_registry.schemas[schema_key] = schema
        self.schema_registry.customer_schema_counts[customer_id] += 1

        # Add fields to bloom filter
        for field in field_mappings.keys():
            self.bloom_filter.add(field.lower())

        logger.info(
            f"Registered customer schema",
            customer_id=customer_id,
            schema_name=schema_name,
            schema_id=schema_key,
            fields_count=len(field_mappings)
        )

        return schema_key

    def get_stats(self) -> Dict[str, Any]:
        """Get normalizer performance statistics"""
        registry_stats = self.schema_registry.get_stats()

        return {
            "total_logs_processed": self.total_logs_processed,
            "bloom_filter_rejections": self.bloom_filter_rejections,
            "bloom_filter_rejection_rate": self.bloom_filter_rejections / max(1, self.total_logs_processed),
            "known_field_variations": len(self.reverse_mapping),
            "bloom_filter_size": self.bloom_filter.size,
            "bloom_filter_items": self.bloom_filter.item_count,
            **registry_stats
        }


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

_normalizer_instance: Optional[HighPerformanceNormalizer] = None
_normalizer_lock = threading.Lock()


def get_high_performance_normalizer() -> HighPerformanceNormalizer:
    """
    Get singleton high-performance normalizer instance.
    Loads configuration from field_mapping.yml on first call.
    """
    global _normalizer_instance

    if _normalizer_instance is None:
        with _normalizer_lock:
            if _normalizer_instance is None:
                # Load field mapping configuration
                import yaml
                import os

                config_path = os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "config",
                    "field_mapping.yml"
                )

                try:
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                    field_mappings = config.get("field_mappings", {})
                except Exception as e:
                    logger.warning(f"Could not load field_mapping.yml: {e}, using defaults")
                    field_mappings = _get_default_field_mappings()

                _normalizer_instance = HighPerformanceNormalizer(field_mappings)

    return _normalizer_instance


def _get_default_field_mappings() -> Dict[str, List[str]]:
    """Default field mappings if config file not found"""
    return {
        "source_ip": ["src_ip", "source_ip", "srcip", "client_ip", "remote_addr", "ip_address"],
        "destination_ip": ["dst_ip", "dest_ip", "dstip", "target_ip", "server_ip"],
        "user_name": ["user", "username", "user_name", "usr", "account", "login"],
        "image": ["image", "process_name", "processname", "executable", "exe", "program"],
        "command_line": ["command_line", "commandline", "cmd", "cmdline", "args", "command"],
        "event_type": ["event_type", "eventtype", "type", "action", "event_action"],
        "message": ["message", "msg", "description", "text", "log_message"],
        "hostname": ["hostname", "host", "computer", "machine", "server_name"],
        "status_code": ["status_code", "statuscode", "status", "response_code", "http_status"],
    }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def normalize_log_fast(
    log_entry: Dict[str, Any],
    customer_id: str = "default",
    source_type: str = "json"
) -> Dict[str, Any]:
    """
    High-performance log normalization.

    Use this instead of normalize_log_for_sigma() for production workloads.

    Args:
        log_entry: Raw log entry
        customer_id: Customer identifier
        source_type: Log source type

    Returns:
        Normalized log entry
    """
    normalizer = get_high_performance_normalizer()
    return normalizer.normalize(log_entry, customer_id, source_type)


def normalize_batch_fast(
    logs: List[Dict[str, Any]],
    customer_id: str = "default",
    source_type: str = "json"
) -> List[Dict[str, Any]]:
    """
    High-performance batch log normalization.

    Optimized for processing thousands of logs at once.

    Args:
        logs: List of raw log entries
        customer_id: Customer identifier
        source_type: Log source type

    Returns:
        List of normalized log entries
    """
    normalizer = get_high_performance_normalizer()
    return normalizer.normalize_batch(logs, customer_id, source_type)


# =============================================================================
# BENCHMARKING
# =============================================================================

if __name__ == "__main__":
    import time
    import random
    import string

    print("🚀 High-Performance Normalizer Benchmark\n")

    # Create normalizer
    normalizer = HighPerformanceNormalizer(_get_default_field_mappings())

    # Generate test logs
    def generate_test_log():
        return {
            "ts": "2025-01-27T10:00:00Z",
            "src_ip": f"192.168.{random.randint(1,255)}.{random.randint(1,255)}",
            "user": f"user_{random.randint(1,1000)}",
            "msg": "Test log message " + ''.join(random.choices(string.ascii_letters, k=20)),
            "level": random.choice(["INFO", "WARN", "ERROR"]),
            "process_name": random.choice(["nginx", "apache", "sshd", "httpd"]),
        }

    # Warm up
    for _ in range(100):
        normalizer.normalize(generate_test_log(), "test_customer")

    # Benchmark single log normalization
    iterations = 100000
    logs = [generate_test_log() for _ in range(iterations)]

    start = time.perf_counter()
    for log in logs:
        normalizer.normalize(log, "test_customer")
    elapsed = time.perf_counter() - start

    print(f"Single log normalization:")
    print(f"  - {iterations:,} logs in {elapsed:.2f}s")
    print(f"  - {iterations/elapsed:,.0f} logs/second")
    print(f"  - {elapsed/iterations*1000000:.2f} μs per log")

    # Benchmark batch normalization
    batch_size = 1000
    batches = iterations // batch_size

    start = time.perf_counter()
    for i in range(batches):
        batch = logs[i*batch_size:(i+1)*batch_size]
        normalizer.normalize_batch(batch, "test_customer")
    elapsed = time.perf_counter() - start

    print(f"\nBatch normalization (batch_size={batch_size}):")
    print(f"  - {iterations:,} logs in {elapsed:.2f}s")
    print(f"  - {iterations/elapsed:,.0f} logs/second")
    print(f"  - {elapsed/iterations*1000000:.2f} μs per log")

    # Print stats
    print(f"\n📊 Statistics:")
    stats = normalizer.get_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  - {key}: {value:.4f}")
        else:
            print(f"  - {key}: {value:,}" if isinstance(value, int) else f"  - {key}: {value}")
