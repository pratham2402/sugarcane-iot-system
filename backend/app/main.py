"""
FastAPI application factory and entry point.

Sugarcane Field Monitoring — Cloud Backend
"""

import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

import yaml
import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env from backend root (one level up from app/) BEFORE importing routes
load_dotenv(Path(__file__).parent.parent / ".env")

from .db.connection import DatabaseConnection
from .db.repository import TelemetryRepository
from .api import health, telemetry, nodes, readings, yield_prediction, anomalies, valve , weather
from .auth import verify_token

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

        # Log auth mode at startup so it's obvious in logs
        if os.getenv("BACKEND_API_TOKEN", "").strip():
            print("Bearer-token auth: ENABLED (non-localhost requests need token)", flush=True)
        else:
            print("Bearer-token auth: DISABLED (BACKEND_API_TOKEN not set)", flush=True)

        print("Backend started — database connected", flush=True)

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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*", "Authorization"],
    )

    # ─── Register Routes ─────────────────────────────────────────────────────

    # Open routes (no token required)
    #   /health         — used by PWA "test connection" button before token is set
    #   /telemetry/*    — ESP32 doesn't have token support yet (future work)
    app.include_router(health.router)
    app.include_router(telemetry.router)

    # Auth-gated routes (token required when BACKEND_API_TOKEN is set,
    # except for localhost requests which are always allowed for the agent)
    app.include_router(nodes.router,            dependencies=[Depends(verify_token)])
    app.include_router(readings.router,         dependencies=[Depends(verify_token)])
    app.include_router(yield_prediction.router, dependencies=[Depends(verify_token)])
    app.include_router(anomalies.router,        dependencies=[Depends(verify_token)])
    app.include_router(valve.router,            dependencies=[Depends(verify_token)])
    app.include_router(weather.router,          dependencies=[Depends(verify_token)])

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


# Module-level `app` so `uvicorn app.main:app` keeps working
app = create_app()
