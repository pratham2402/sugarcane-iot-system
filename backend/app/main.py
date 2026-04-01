"""
FastAPI application factory and entry point.

Sugarcane Field Monitoring — Cloud Backend
"""

import os
import sys
import logging
from contextlib import asynccontextmanager

import yaml
import uvicorn
from fastapi import FastAPI

from .db.connection import DatabaseConnection
from .db.repository import TelemetryRepository
from .api import health, telemetry, nodes, readings

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config/backend_config.yaml") -> dict:
    """Load backend configuration."""
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    # Defaults if no config file
    return {
        "server": {
            "host": "0.0.0.0",
            "port": 8000,
            "debug": True,
            "title": "Sugarcane Field Monitoring API",
            "version": "1.0.0",
        },
        "database": {
            "url": "sqlite:///data/telemetry.db",
        },
    }


def create_app(config: dict = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        config: Optional configuration dict. If None, loads from file.
    """
    if config is None:
        config = load_config()

    server_config = config.get("server", {})
    db_url = config.get("database", {}).get("url", "sqlite:///data/telemetry.db")
    db_conn = DatabaseConnection(db_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        conn = db_conn.connect()
        app.state.repository = TelemetryRepository(conn)
        logger.info("Backend started — database connected")
        yield
        # Shutdown
        db_conn.close()
        logger.info("Backend stopped — database disconnected")

    app = FastAPI(
        title=server_config.get("title", "Sugarcane Field Monitoring API"),
        version=server_config.get("version", "1.0.0"),
        description=(
            "Cloud backend for the sugarcane field monitoring system. "
            "Receives telemetry from Raspberry Pi field gateways and provides "
            "APIs for data access and analysis."
        ),
        lifespan=lifespan,
    )

    # ─── Register Routes ─────────────────────────────────────────────────────

    app.include_router(health.router)
    app.include_router(telemetry.router)
    app.include_router(nodes.router)
    app.include_router(readings.router)

    return app


# ─── CLI Entry Point ─────────────────────────────────────────────────────────

def main():
    """Run the backend server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)-8s] %(name)-25s %(message)s",
    )

    config = load_config()
    server_config = config.get("server", {})

    app = create_app(config)

    logger.info("=" * 60)
    logger.info("  Sugarcane Field Monitoring — Cloud Backend")
    logger.info(f"  Version: {server_config.get('version', '1.0.0')}")
    logger.info(f"  Port: {server_config.get('port', 8000)}")
    logger.info("=" * 60)

    uvicorn.run(
        app,
        host=server_config.get("host", "0.0.0.0"),
        port=server_config.get("port", 8000),
        log_level="info" if server_config.get("debug") else "warning",
    )


if __name__ == "__main__":
    main()
