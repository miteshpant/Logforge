"""
Simple OpenTelemetry Field Mapper
Maps customer field variations to standardized database column names
"""

import yaml
import os
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class SimpleOTelMapper:
    """Simple field mapper for OpenTelemetry data"""

    def __init__(self):
        self.field_mappings = self._load_field_mappings()

    def _load_field_mappings(self) -> Dict[str, list]:
        """Load field mapping configuration from YAML"""
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "config",
            "otel_field_mapping.yml"
        )

        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            # Extract only the variations for each field
            field_mappings = {}
            for key, value in config.items():
                if isinstance(value, dict) and 'variations' in value:
                    field_mappings[key] = value['variations']
            return field_mappings
        except Exception as e:
            logger.error(f"Failed to load OTel field mappings: {e}")
            return {}

    def normalize_service_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize service topology data using simple field mapping"""
        normalized = raw_data.copy()  # Start with original data

        # Go through each standardized field we want to populate
        for standard_field, variations in self.field_mappings.items():
            found_value = None
            found_variation = None

            # Search for this field in all its possible variations
            for variation in variations:
                value = self._get_field_value(raw_data, variation)
                if value is not None:
                    found_value = value
                    found_variation = variation
                    break

            # If we found a value, set it in normalized data
            if found_value is not None:
                normalized[standard_field] = found_value
            else:
                # Only log for the fields we care about
                if standard_field in ['deployment_environment', 'namespace', 'cluster']:
                    logger.info(f"No variation found for {standard_field}, checking variations: {variations}")

        return normalized

    def _get_field_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """Get field value, supporting dot notation for nested fields"""
        try:
            # Handle simple field names (no dots)
            if '.' not in field_path:
                return data.get(field_path)

            # Handle nested field paths like "resource.env"
            current = data
            for part in field_path.split('.'):
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None
            return current

        except Exception as e:
            logger.error(f"Error getting field {field_path}: {e}")
            return None


# Global instance
simple_mapper = SimpleOTelMapper()

def normalize_otel_service_simple(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Simple convenience function to normalize service data"""
    return simple_mapper.normalize_service_data(raw_data)
