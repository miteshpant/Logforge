"""
Application configuration and settings
"""

import os
import logging
from typing import Dict, Any

def clickhouse_settings() -> Dict[str, Any]:
    """ClickHouse connection settings -- the single source of truth.

    Every module that opens a ClickHouse connection reads these. They used to
    be re-declared in six places with different defaults: this module said
    localhost / default / "" while the others said clickhouse / logforge /
    logforge123, and the query engine ignored CLICKHOUSE_HOST/PORT entirely
    (hard-coded clickhouse:8123). With a variable unset, different parts of
    the API connected to different servers or as different users; running the
    API outside Docker with CLICKHOUSE_HOST=localhost left queries pointed at
    a host that doesn't exist. Defaults match infra/docker/compose.yml.
    """
    return {
        "host": os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        "port": int(os.getenv("CLICKHOUSE_PORT", "8123")),
        "username": os.getenv("CLICKHOUSE_USER", "logforge"),
        "password": os.getenv("CLICKHOUSE_PASSWORD", "logforge123"),
        "database": os.getenv("CLICKHOUSE_DATABASE", "logforge"),
    }


def load_config() -> Dict[str, Any]:
    """Load application configuration from environment variables"""
    ch = clickhouse_settings()
    return {
        "clickhouse_host": ch["host"],
        "clickhouse_port": ch["port"],
        "clickhouse_user": ch["username"],
        "clickhouse_password": ch["password"],
        "clickhouse_database": ch["database"],
        "redis_host": os.getenv("REDIS_HOST", "localhost"),
        "redis_port": int(os.getenv("REDIS_PORT", "6379")),
        "redis_db": int(os.getenv("REDIS_DB", "0")),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "cors_origins": [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3001,http://localhost:3000,http://localhost:3002").split(",")],
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
