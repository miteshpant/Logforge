"""
Application configuration and settings
"""

import os
import logging
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    """Load application configuration from environment variables"""
    return {
        "clickhouse_host": os.getenv("CLICKHOUSE_HOST", "localhost"),
        "clickhouse_port": int(os.getenv("CLICKHOUSE_PORT", "8123")),
        "clickhouse_user": os.getenv("CLICKHOUSE_USER", "default"),
        "clickhouse_password": os.getenv("CLICKHOUSE_PASSWORD", ""),
        "clickhouse_database": os.getenv("CLICKHOUSE_DATABASE", "logforge"),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "cors_origins": os.getenv("CORS_ORIGINS", "http://localhost:3001,http://localhost:3000,http://localhost:3002").split(","),
        "max_workers": int(os.getenv("MAX_WORKERS", "4")),
        "environment": os.getenv("ENVIRONMENT", "development")
    }

def setup_logging(config: Dict[str, Any]):
    """Configure structured logging"""
    log_level = getattr(logging, config.get("log_level", "INFO").upper())

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Set specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
