"""
OpenTelemetry Field Mapper
Maps customer variations to standardized field names using otel_field_mapping.yml
Includes Redis caching for customer-specific field mappings
"""

import yaml
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class OTelFieldMapper:
    """Maps OpenTelemetry field variations to standardized database column names"""
    
    def __init__(self):
        self.field_mappings = self._load_field_mappings()
        self.value_mappings = self._load_value_mappings()
        # TODO: Implement async Redis caching later
        self.redis_client = None
        
    def _get_redis_manager(self):
        """Get Redis manager for caching field mappings"""
        try:
            from events.management.cache.redis_manager import get_redis_manager
            return get_redis_manager
        except Exception as e:
            logger.warning(f"Redis manager not available for field mapping cache: {e}")
            return None
        
    def _load_field_mappings(self) -> Dict[str, List[str]]:
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
            
            # Extract field variations (excluding value mappings and special sections)
            field_mappings = {}
            for key, value in config.items():
                if isinstance(value, dict) and 'variations' in value:
                    field_mappings[key] = value['variations']
                    
            return field_mappings
        except Exception as e:
            logger.error(f"Failed to load OTel field mappings: {e}")
            return {}
    
    def _load_value_mappings(self) -> Dict[str, Dict[str, List[str]]]:
        """Load value transformation mappings"""
        config_path = os.path.join(
            os.path.dirname(__file__), 
            "..", 
            "config", 
            "otel_field_mapping.yml"
        )
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Extract value mappings
            value_mappings = {}
            mapping_sections = [
                'service_type_mappings',
                'health_status_mappings', 
                'span_kind_mappings',
                'span_status_mappings'
            ]
            
            for section in mapping_sections:
                if section in config:
                    value_mappings[section.replace('_mappings', '')] = config[section]
                    
            return value_mappings
        except Exception as e:
            logger.error(f"Failed to load OTel value mappings: {e}")
            return {}

    def normalize_trace_span(self, raw_span: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a trace span using field mappings"""
        normalized = {}
        
        # Apply field mappings
        normalized.update(self._apply_field_mappings(raw_span))
        
        # Apply nested extractions
        normalized.update(self._extract_nested_fields(raw_span))
        
        # Apply value transformations
        normalized = self._apply_value_transformations(normalized)
        
        # Apply default values for required fields
        normalized = self._apply_trace_defaults(normalized)
        
        return normalized
    
    def normalize_service_topology(self, raw_service: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize service topology data using field mappings"""
        normalized = {}
        
        # Apply field mappings
        normalized.update(self._apply_field_mappings(raw_service))
        
        # Apply nested extractions
        normalized.update(self._extract_nested_fields(raw_service))
        
        # Apply value transformations
        normalized = self._apply_value_transformations(normalized)
        
        # Apply default values for required fields
        normalized = self._apply_service_defaults(normalized)
        
        return normalized
    
    def normalize_metric(self, raw_metric: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a metric using field mappings"""
        normalized = {}
        
        # Apply field mappings
        normalized.update(self._apply_field_mappings(raw_metric))
        
        # Apply nested extractions  
        normalized.update(self._extract_nested_fields(raw_metric))
        
        # Apply default values for required fields
        normalized = self._apply_metric_defaults(normalized)
        
        return normalized
    
    def _apply_field_mappings(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply field name mappings to raw data with Redis caching and dot notation support"""
        normalized = {}
        
        # Get customer ID for caching (if available)
        customer_id = raw_data.get('customer_id')
        
        # Direct field mapping with Redis caching
        for standard_field, variations in self.field_mappings.items():
            value_found = None
            actual_key_used = None
            
            # Check Redis cache first for customer-specific mappings
            if customer_id and self.redis_client:
                cached_key = self._get_cached_field_mapping(customer_id, standard_field)
                if cached_key:
                    if cached_key in raw_data and raw_data[cached_key] is not None:
                        normalized[standard_field] = raw_data[cached_key]
                        logger.debug(f"Used cached mapping {standard_field}: {cached_key} -> {raw_data[cached_key]}")
                        continue
                    elif '.' in cached_key:
                        cached_value = self._get_nested_value(raw_data, cached_key)
                        if cached_value is not None:
                            normalized[standard_field] = cached_value
                            logger.debug(f"Used cached nested mapping {standard_field}: {cached_key} -> {cached_value}")
                            continue
            
            for variation in variations:
                # Check for exact key match first (performance optimization)
                if variation in raw_data and raw_data[variation] is not None:
                    value_found = raw_data[variation]
                    actual_key_used = variation
                    logger.debug(f"Found exact match {standard_field}: {variation} -> {value_found}")
                    break
                    
                # Check for dot notation path (e.g., resource.env, installation.env)
                elif '.' in variation:
                    value = self._get_nested_value(raw_data, variation)
                    if value is not None:
                        value_found = value
                        actual_key_used = variation
                        logger.debug(f"Found nested match {standard_field}: {variation} -> {value_found}")
                        break
            
            # If value found, use it and cache the mapping
            if value_found is not None and standard_field not in normalized:
                normalized[standard_field] = value_found
                
                # Cache this successful mapping in Redis for future use
                if customer_id and actual_key_used and self.redis_client:
                    self._cache_field_mapping(customer_id, standard_field, actual_key_used)
                    logger.debug(f"Cached new mapping {standard_field}: {actual_key_used}")
                    
                # First match wins, move to next standard field
                continue
        
        # Copy unmapped fields as-is (preserve extra data)
        for key, value in raw_data.items():
            if key not in normalized and not self._is_mapped_variation(key):
                normalized[key] = value
                
        return normalized
        
    def _cache_field_mapping(self, customer_id: str, standard_field: str, actual_key: str):
        """Cache successful field mapping in Redis using format: SERVICE_TOPOLOGY_<field>_<customer_id>"""
        if not self.redis_client:
            return
            
        try:
            # Redis key format: SERVICE_TOPOLOGY_<standard_field>_<customer_id>
            cache_key = f"SERVICE_TOPOLOGY_{standard_field.upper()}_{customer_id}"
            
            # Store the actual key that worked for this customer
            self.redis_client.setex(cache_key, 86400, actual_key)  # Cache for 24 hours
            
            logger.debug(f"Cached field mapping: {cache_key} -> {actual_key}")
        except Exception as e:
            logger.warning(f"Failed to cache field mapping: {e}")
            
    def _get_cached_field_mapping(self, customer_id: str, standard_field: str) -> Optional[str]:
        """Get cached field mapping from Redis"""
        if not self.redis_client or not customer_id:
            return None
            
        try:
            cache_key = f"SERVICE_TOPOLOGY_{standard_field.upper()}_{customer_id}"
            cached_key = self.redis_client.get(cache_key)
            
            if cached_key:
                return cached_key.decode('utf-8') if isinstance(cached_key, bytes) else cached_key
                
        except Exception as e:
            logger.warning(f"Failed to get cached field mapping: {e}")
            
        return None
    
    def _is_mapped_variation(self, field_name: str) -> bool:
        """Check if a field name is already mapped to a standard field"""
        for variations in self.field_mappings.values():
            if field_name in variations:
                return True
        return False
    
    def _extract_nested_fields(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract fields from nested objects based on nested_extractions config"""
        config_path = os.path.join(
            os.path.dirname(__file__), 
            "..", 
            "config", 
            "otel_field_mapping.yml"
        )
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            nested_extractions = config.get('nested_extractions', {})
            extracted = {}
            
            for target_field, source_paths in nested_extractions.items():
                for path in source_paths:
                    value = self._get_nested_value(raw_data, path)
                    if value is not None:
                        # Remove the "_from_" suffix to get the actual field name
                        actual_field = target_field.replace('_from_resource', '').replace('_from_attributes', '')
                        extracted[actual_field] = value
                        break
                        
            return extracted
        except Exception as e:
            logger.error(f"Failed to extract nested fields: {e}")
            return {}
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get value from nested object using dot notation"""
        try:
            value = data
            for key in path.split('.'):
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None
            return value
        except Exception:
            return None
    
    def _apply_value_transformations(self, normalized: Dict[str, Any]) -> Dict[str, Any]:
        """Apply value transformations using mapping rules"""
        transformed = normalized.copy()
        
        # Transform service_type
        if 'service_type' in transformed:
            transformed['service_type'] = self._transform_enum_value(
                transformed['service_type'], 'service_type'
            )
        
        # Transform health_status
        if 'health_status' in transformed:
            transformed['health_status'] = self._transform_enum_value(
                transformed['health_status'], 'health_status'
            )
        
        # Transform span_kind
        if 'kind' in transformed:
            transformed['kind'] = self._transform_enum_value(
                transformed['kind'], 'span_kind'
            )
        
        # Transform span_status
        if 'status' in transformed:
            transformed['status'] = self._transform_enum_value(
                transformed['status'], 'span_status'
            )
            
        return transformed
    
    def _transform_enum_value(self, raw_value: str, mapping_type: str) -> str:
        """Transform enum values using mapping rules"""
        if not raw_value or mapping_type not in self.value_mappings:
            return raw_value
        
        raw_value_lower = str(raw_value).lower()
        mappings = self.value_mappings[mapping_type]
        
        # Find matching standard value
        for standard_value, variations in mappings.items():
            if raw_value_lower in [v.lower() for v in variations]:
                return standard_value
                
        # Return original if no mapping found
        return raw_value
    
    def _apply_trace_defaults(self, normalized: Dict[str, Any]) -> Dict[str, Any]:
        """Apply default values for required trace fields"""
        defaults = normalized.copy()
        
        # Generate IDs if missing
        if not defaults.get('trace_id'):
            defaults['trace_id'] = f"trace_{datetime.now().timestamp()}"
        if not defaults.get('span_id'):
            defaults['span_id'] = f"span_{datetime.now().timestamp()}"
            
        # Default timestamps
        if not defaults.get('start_time'):
            defaults['start_time'] = datetime.now()
        if not defaults.get('end_time'):
            defaults['end_time'] = datetime.now()
            
        # Calculate duration if missing
        if not defaults.get('duration_ms') and defaults.get('start_time') and defaults.get('end_time'):
            try:
                start = defaults['start_time']
                end = defaults['end_time']
                if isinstance(start, str):
                    start = datetime.fromisoformat(start.replace('Z', '+00:00'))
                if isinstance(end, str):
                    end = datetime.fromisoformat(end.replace('Z', '+00:00'))
                duration = (end - start).total_seconds() * 1000
                defaults['duration_ms'] = max(0, duration)
            except Exception:
                defaults['duration_ms'] = 0
        
        # Default values
        if not defaults.get('kind'):
            defaults['kind'] = 'internal'
        if not defaults.get('status'):
            defaults['status'] = 'unset'
            
        return defaults
    
    def _apply_service_defaults(self, normalized: Dict[str, Any]) -> Dict[str, Any]:
        """Apply default values for required service topology fields"""
        defaults = normalized.copy()
        
        # Generate service instance ID if missing
        if not defaults.get('service_instance_id') and defaults.get('service_name'):
            defaults['service_instance_id'] = f"{defaults['service_name']}-instance-{datetime.now().timestamp()}"
        
        # Default service type
        if not defaults.get('service_type'):
            defaults['service_type'] = 'application'
            
        # Default environment
        if not defaults.get('deployment_environment'):
            defaults['deployment_environment'] = 'unknown'
            
        # Default health status
        if not defaults.get('health_status'):
            defaults['health_status'] = 'unknown'
            
        # Default metrics
        if not defaults.get('request_count'):
            defaults['request_count'] = 0
        if not defaults.get('error_count'):
            defaults['error_count'] = 0
        if not defaults.get('avg_response_time_ms'):
            defaults['avg_response_time_ms'] = 0.0
            
        return defaults
    
    def _apply_metric_defaults(self, normalized: Dict[str, Any]) -> Dict[str, Any]:
        """Apply default values for required metric fields"""
        defaults = normalized.copy()
        
        # Default timestamp
        if not defaults.get('timestamp'):
            defaults['timestamp'] = datetime.now()
            
        # Default metric type
        if not defaults.get('metric_type'):
            defaults['metric_type'] = 'gauge'
            
        # Ensure value is numeric
        if 'value' in defaults:
            try:
                defaults['value'] = float(defaults['value'])
            except (ValueError, TypeError):
                defaults['value'] = 0.0
        else:
            defaults['value'] = 0.0
            
        return defaults


# Global instance for easy import
otel_field_mapper = OTelFieldMapper()

def normalize_otel_span(raw_span: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to normalize a trace span"""
    return otel_field_mapper.normalize_trace_span(raw_span)

def normalize_otel_service(raw_service: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to normalize service topology data"""
    return otel_field_mapper.normalize_service_topology(raw_service)

def normalize_otel_metric(raw_metric: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to normalize a metric"""
    return otel_field_mapper.normalize_metric(raw_metric)