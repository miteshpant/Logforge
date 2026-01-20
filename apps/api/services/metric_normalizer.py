"""
Metric Name Normalizer Service

Normalizes incoming metric names to standardized Logforge metric names.
Supports:
- Standard metrics (response_time, throughput, error_rate, etc.)
- Custom metrics (any name starting with "custom." passes through unchanged)

This enables customers to send metrics using common naming conventions
(latency, rps, errors) while storing them with consistent names for
dashboards, alerts, and queries.
"""

import yaml
import os
from typing import Dict, Any, Optional, Tuple, List
import structlog

logger = structlog.get_logger(__name__)


class MetricNameNormalizer:
    """Normalizes metric names to standardized Logforge names"""

    def __init__(self):
        self.mappings = self._load_mappings()
        self.reverse_mappings = self._build_reverse_mappings()
        logger.info(
            "MetricNameNormalizer initialized",
            standard_metrics=len(self.mappings),
            total_variations=len(self.reverse_mappings)
        )

    def _load_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Load metric name mappings from YAML config"""
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "config",
            "metric_name_mappings.yml"
        )

        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            # Filter to only include entries with variations
            mappings = {}
            for key, value in config.items():
                if isinstance(value, dict) and 'variations' in value:
                    mappings[key] = value

            return mappings

        except FileNotFoundError:
            logger.warning(f"Metric name mappings file not found: {config_path}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load metric name mappings: {e}")
            return {}

    def _build_reverse_mappings(self) -> Dict[str, str]:
        """Build reverse lookup: variation -> standard_name"""
        reverse = {}
        for standard_name, config in self.mappings.items():
            for variation in config.get('variations', []):
                # Normalize variation to lowercase for case-insensitive matching
                reverse[variation.lower()] = standard_name
        return reverse

    def normalize(self, metric_name: str) -> Tuple[str, bool]:
        """
        Normalize a metric name to its standard form.

        Args:
            metric_name: The incoming metric name

        Returns:
            Tuple of (normalized_name, was_normalized)
            - normalized_name: The standardized metric name
            - was_normalized: True if the name was mapped, False if passed through
        """
        if not metric_name:
            return metric_name, False

        # Custom metrics pass through unchanged
        if metric_name.startswith('custom.'):
            return metric_name, False

        # Try to find a mapping (case-insensitive)
        lookup_name = metric_name.lower().strip()

        if lookup_name in self.reverse_mappings:
            standard_name = self.reverse_mappings[lookup_name]
            was_normalized = (standard_name != metric_name)
            return standard_name, was_normalized

        # No mapping found - pass through unchanged
        # Log a warning for unknown metrics (could be a typo)
        if not self._is_known_standard_name(metric_name):
            logger.debug(
                "Unknown metric name passed through without normalization",
                metric_name=metric_name,
                hint="Consider adding to metric_name_mappings.yml or prefix with 'custom.'"
            )

        return metric_name, False

    def _is_known_standard_name(self, name: str) -> bool:
        """Check if name is already a standard metric name"""
        return name.lower() in [k.lower() for k in self.mappings.keys()]

    def normalize_metric_data(self, metric_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize metric data dict, preserving original name.

        Args:
            metric_data: Dict containing metric_name and other fields

        Returns:
            Dict with normalized metric_name and original_metric_name
        """
        result = metric_data.copy()

        # Get the original metric name from various possible fields
        original_name = (
            metric_data.get('metric_name') or
            metric_data.get('metricName') or
            metric_data.get('name') or
            ''
        )

        if original_name:
            normalized_name, was_normalized = self.normalize(original_name)

            # Set normalized name
            result['metric_name'] = normalized_name

            # Preserve original name for debugging/reference
            if was_normalized:
                result['original_metric_name'] = original_name
                logger.debug(
                    "Metric name normalized",
                    original=original_name,
                    normalized=normalized_name
                )
            else:
                result['original_metric_name'] = original_name

        return result

    def get_standard_metrics(self) -> List[Dict[str, Any]]:
        """
        Get list of all standard metrics with their metadata.
        Useful for UI dropdowns and documentation.
        """
        return [
            {
                'name': name,
                'description': config.get('description', ''),
                'unit': config.get('unit', ''),
                'category': config.get('category', 'other'),
                'variations': config.get('variations', [])
            }
            for name, config in self.mappings.items()
        ]

    def get_metric_info(self, metric_name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a standard metric"""
        # First normalize the name
        normalized, _ = self.normalize(metric_name)

        if normalized in self.mappings:
            config = self.mappings[normalized]
            return {
                'name': normalized,
                'description': config.get('description', ''),
                'unit': config.get('unit', ''),
                'category': config.get('category', 'other')
            }

        return None


# Global singleton instance
_normalizer_instance: Optional[MetricNameNormalizer] = None


def get_metric_normalizer() -> MetricNameNormalizer:
    """Get the global MetricNameNormalizer instance"""
    global _normalizer_instance
    if _normalizer_instance is None:
        _normalizer_instance = MetricNameNormalizer()
    return _normalizer_instance


def normalize_metric_name(metric_name: str) -> str:
    """Convenience function to normalize a metric name"""
    normalizer = get_metric_normalizer()
    normalized, _ = normalizer.normalize(metric_name)
    return normalized


def normalize_metric_data(metric_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to normalize metric data dict"""
    normalizer = get_metric_normalizer()
    return normalizer.normalize_metric_data(metric_data)
