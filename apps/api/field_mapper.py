"""
Field Mapping Engine for Sigma Rule Evaluation
Normalizes diverse customer log formats to standard MITRE/Sigma field names
"""

import yaml
import re
import os
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class FieldMappingResult:
    """Result of field mapping operation"""
    mapped_fields: Dict[str, Any]
    mapping_stats: Dict[str, int]
    unmapped_fields: Set[str]


class FieldMapper:
    """
    Normalizes customer log fields to standard Sigma rule field names
    Uses configurable YAML mapping for flexibility across log formats
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize field mapper with configuration

        Args:
            config_path: Path to field mapping YAML configuration
        """
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config", "field_mapping.yml")

        self.config_path = config_path
        self.config = self._load_config()
        self.field_mappings = self.config.get("field_mappings", {})
        self.value_mappings = self.config.get("value_mappings", {})
        self.product_mappings = self.config.get("product_mappings", {})
        self.normalization_config = self.config.get("normalization_config", {})

        # Create reverse mapping: customer_field -> standard_field
        self.reverse_mapping = self._build_reverse_mapping()

        logger.info(f"Field mapper initialized with {len(self.field_mappings)} standard fields")

    def _load_config(self) -> Dict[str, Any]:
        """Load field mapping configuration from YAML"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.debug(f"Loaded field mapping config from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load field mapping config: {e}")
            return {}

    def _build_reverse_mapping(self) -> Dict[str, str]:
        """
        Build reverse mapping from customer fields to standard fields

        Returns:
            Dict mapping customer_field -> standard_field
        """
        reverse_map = {}

        for standard_field, customer_fields in self.field_mappings.items():
            for customer_field in customer_fields:
                # Handle case sensitivity
                if self.normalization_config.get("case_insensitive", True):
                    customer_field_key = customer_field.lower()
                else:
                    customer_field_key = customer_field

                reverse_map[customer_field_key] = standard_field

        logger.debug(f"Built reverse mapping with {len(reverse_map)} customer field variations")
        return reverse_map

    def normalize_log_entry(self, log_entry: Dict[str, Any], product_hint: Optional[str] = None) -> FieldMappingResult:
        """
        Normalize a single log entry to standard field names

        Args:
            log_entry: Original log entry with customer field names
            product_hint: Optional hint about log source (windows, linux, apache, etc.)

        Returns:
            FieldMappingResult with normalized fields and mapping statistics
        """
        mapped_fields = {}
        mapping_stats = {
            "exact_matches": 0,
            "case_insensitive_matches": 0,
            "pattern_matches": 0,
            "value_transformations": 0,
            "unmapped_fields": 0
        }
        unmapped_fields = set()

        # Process each field in the original log entry
        for original_field, original_value in log_entry.items():
            mapped_field, match_type = self._map_single_field(original_field, product_hint)
            if mapped_field:
                # Apply value transformation if needed
                mapped_value = self._transform_field_value(mapped_field, original_value)
                mapped_fields[mapped_field] = mapped_value

                # Update stats
                mapping_stats[f"{match_type}_matches"] += 1
                if mapped_value != original_value:
                    mapping_stats["value_transformations"] += 1

                # Also keep original field for compatibility
                mapped_fields[original_field] = original_value

            else:
                # Keep unmapped fields as-is
                mapped_fields[original_field] = original_value
                unmapped_fields.add(original_field)
                mapping_stats["unmapped_fields"] += 1

        # Apply pattern-based event_type detection
        self._detect_event_types(mapped_fields, mapping_stats)

        return FieldMappingResult(
            mapped_fields=mapped_fields,
            mapping_stats=mapping_stats,
            unmapped_fields=unmapped_fields
        )

    def _map_single_field(self, field_name: str, product_hint: Optional[str] = None) -> Tuple[Optional[str], str]:
        """
        Map a single field name to standard field

        Args:
            field_name: Original field name
            product_hint: Optional product hint for specialized mapping

        Returns:
            Tuple of (mapped_field_name, match_type)
        """
        # Try product-specific mapping first
        if product_hint and product_hint in self.product_mappings:
            product_fields = self.product_mappings[product_hint]
            for standard_field, variations in product_fields.items():
                if field_name in variations:
                    return standard_field, "exact"

        # Try exact match in reverse mapping
        case_insensitive = self.normalization_config.get("case_insensitive", True)
        lookup_field = field_name.lower() if case_insensitive else field_name

        if lookup_field in self.reverse_mapping:
            return self.reverse_mapping[lookup_field], "exact"

        # Try case-insensitive match if not already done
        if not case_insensitive:
            lookup_field = field_name.lower()
            if lookup_field in self.reverse_mapping:
                return self.reverse_mapping[lookup_field], "case_insensitive"

        # Try pattern matching for common variations
        mapped_field = self._try_pattern_matching(field_name)
        if mapped_field:
            return mapped_field, "pattern"

        return None, "none"

    def _try_pattern_matching(self, field_name: str) -> Optional[str]:
        """
        Try pattern-based field name matching

        Args:
            field_name: Original field name

        Returns:
            Mapped field name if found
        """
        field_lower = field_name.lower()

        # Common patterns to try
        patterns = [
            # Remove common prefixes/suffixes
            (r'^(log_|event_|audit_)', ''),
            (r'(_log|_event|_audit)$', ''),

            # Handle underscore variations
            (r'_', ''),  # username -> user name -> user

            # Handle common abbreviations
            (r'src', 'source'),
            (r'dst', 'destination'),
            (r'dest', 'destination'),
            (r'msg', 'message'),
            (r'cmd', 'command'),
            (r'proc', 'process'),
            (r'usr', 'user'),
        ]

        for pattern, replacement in patterns:
            modified_field = re.sub(pattern, replacement, field_lower)
            if modified_field != field_lower and modified_field in self.reverse_mapping:
                return self.reverse_mapping[modified_field]

        return None

    def _transform_field_value(self, field_name: str, value: Any) -> Any:
        """
        Transform field value using value mappings

        Args:
            field_name: Standard field name
            value: Original field value

        Returns:
            Transformed value
        """
        value_str = str(value)
        value_lower = value_str.lower()

        # Apply status mappings with numeric conversion
        if field_name in ["status", "result", "outcome"]:
            status_mappings = self.value_mappings.get("status_mappings", {})
            for target_status, source_values in status_mappings.items():
                if value_lower in [v.lower() for v in source_values]:
                    # Convert status to integer for LogEntry model compatibility
                    if target_status == "success":
                        return 200  # HTTP 200 OK for success
                    elif target_status == "failed":
                        return 400  # HTTP 400 Bad Request for failure
                    else:
                        return target_status

        # Handle yes/no success values specifically
        if field_name in ["status", "result", "outcome"] and value_lower in ["yes", "true", "1", "success", "ok"]:
            return 200  # HTTP 200 OK for success
        elif field_name in ["status", "result", "outcome"] and value_lower in ["no", "false", "0", "fail", "failed", "error"]:
            return 400  # HTTP 400 Bad Request for failure

        # Special handling for status_code field
        if field_name == "status_code":
            # If it's already a valid HTTP status code, keep it
            if isinstance(value, (int, str)) and str(value).isdigit():
                code = int(value)
                if 100 <= code <= 599:  # Valid HTTP status range
                    return code

            # Transform status 0 to appropriate HTTP status for auth failures
            if value == 0 or value == "0":
                return 401  # Unauthorized - common for auth failures

            # Transform log levels to status codes for authentication context
            if value_lower in ["error", "err", "failed", "failure"]:
                return 401  # Unauthorized
            elif value_lower in ["warn", "warning"]:
                return 403  # Forbidden
            elif value_lower in ["critical", "fatal"]:
                return 401  # Unauthorized

        return value

    def _detect_event_types(self, mapped_fields: Dict[str, Any], stats: Dict[str, int]) -> None:
        """
        Detect event_type based on message content patterns

        Args:
            mapped_fields: Fields being mapped (modified in-place)
            stats: Mapping statistics (modified in-place)
        """
        # Only add event_type if not already present
        if "event_type" in mapped_fields:
            return
        # ...including one the caller sent in attrs: a guess must not shadow it.
        attrs = mapped_fields.get("attrs")
        if isinstance(attrs, dict) and attrs.get("event_type"):
            return

        # Check message field for event type patterns
        message_fields = ["message", "msg", "description", "text"]
        message_content = None

        for msg_field in message_fields:
            if msg_field in mapped_fields:
                message_content = str(mapped_fields[msg_field]).lower()
                break

        if not message_content:
            return

        # Apply event type patterns
        event_patterns = self.value_mappings.get("event_type_patterns", {})
        for event_type, patterns in event_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_content):
                    mapped_fields["event_type"] = event_type
                    stats["pattern_matches"] += 1
                    logger.debug(f"Detected event_type '{event_type}' from message pattern: {pattern}")
                    return

    def get_mapping_summary(self) -> Dict[str, Any]:
        """
        Get summary of available field mappings

        Returns:
            Summary statistics and information
        """
        return {
            "total_standard_fields": len(self.field_mappings),
            "total_customer_variations": len(self.reverse_mapping),
            "supported_products": list(self.product_mappings.keys()),
            "value_mapping_types": list(self.value_mappings.keys()),
            "configuration": self.normalization_config
        }

    def add_custom_mapping(self, standard_field: str, customer_fields: List[str]) -> None:
        """
        Add custom field mapping at runtime

        Args:
            standard_field: Standard field name
            customer_fields: List of customer field variations
        """
        if standard_field not in self.field_mappings:
            self.field_mappings[standard_field] = []

        self.field_mappings[standard_field].extend(customer_fields)

        # Update reverse mapping
        case_insensitive = self.normalization_config.get("case_insensitive", True)
        for customer_field in customer_fields:
            key = customer_field.lower() if case_insensitive else customer_field
            self.reverse_mapping[key] = standard_field

        logger.info(f"Added custom mapping: {standard_field} -> {customer_fields}")


# Global field mapper instance
field_mapper = FieldMapper()


def normalize_log_for_sigma(log_entry: Dict[str, Any], product_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to normalize a log entry for Sigma rule evaluation

    Args:
        log_entry: Original log entry
        product_hint: Optional product hint

    Returns:
        Normalized log entry with standard field names
    """
    result = field_mapper.normalize_log_entry(log_entry, product_hint)
    return result.mapped_fields


def get_field_mapping_stats() -> Dict[str, Any]:
    """
    Get field mapping statistics and configuration

    Returns:
        Mapping summary and stats
    """
    return field_mapper.get_mapping_summary()


if __name__ == "__main__":
    # Test the field mapper
    test_log = {
        "ts": "2025-10-29T04:10:00Z",
        "level": "ERROR",
        "msg": "Failed login attempt for user admin",
        "user_id": "admin",
        "src_ip": "192.168.1.100",
        "service": "sshd"
    }

    print("🧪 Testing Field Mapper...")
    print(f"Original log: {test_log}")

    result = field_mapper.normalize_log_entry(test_log)
    print(f"Mapped fields: {result.mapped_fields}")
    print(f"Mapping stats: {result.mapping_stats}")
    print(f"Unmapped fields: {result.unmapped_fields}")
