#!/usr/bin/env python3
"""
Seed test data into the backend database.

Creates sample telemetry readings for testing the API endpoints
and dashboard development.

Usage:
    python scripts/seed_test_data.py
"""

import json
import time
import random
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import DatabaseConnection
from app.db.repository import TelemetryRepository
from app.models.schemas import TelemetryIngestRequest, SensorReading


def generate_readings(node_id: str, timestamp: int) -> dict:
    """Generate realistic sensor readings."""
    return {
        "soil_moisture": SensorReading(
            value=round(random.uniform(40, 85), 1),
            unit="%",
            valid=True,
        ),
        "soil_temperature": SensorReading(
            value=round(random.uniform(22, 38), 1),
            unit="°C",
            valid=True,
        ),
        "air_temperature": SensorReading(
            value=round(random.uniform(24, 42), 1),
            unit="°C",
            valid=True,
        ),
        "humidity": SensorReading(
            value=round(random.uniform(50, 95), 1),
            unit="%",
            valid=True,
        ),
        "rainfall_pulses": SensorReading(
            value=random.randint(0, 20),
            unit="pulses",
            valid=True,
        ),
        "flow_pulses": SensorReading(
            value=random.randint(0, 500),
            unit="pulses",
            valid=True,
        ),
    }


def main():
    db_conn = DatabaseConnection("sqlite:///data/telemetry.db")
    conn = db_conn.connect()
    repo = TelemetryRepository(conn)

    nodes = ["node-01", "node-02", "node-03"]
    now = int(time.time())
    total = 0

    print("Seeding test data...")

    for node_id in nodes:
        # Generate 24 hours of hourly readings
        for hours_ago in range(24, 0, -1):
            ts = now - (hours_ago * 3600)
            reading = TelemetryIngestRequest(
                node_id=node_id,
                timestamp=ts,
                firmware_version="1.0.0",
                battery_voltage=round(random.uniform(3.3, 4.1), 2),
                status="ok",
                readings=generate_readings(node_id, ts),
            )

            if repo.ingest_reading(reading):
                total += 1

    print(f"Seeded {total} readings across {len(nodes)} nodes")
    print(f"Total readings in DB: {repo.get_total_readings()}")
    print(f"Registered nodes: {repo.get_total_nodes()}")

    db_conn.close()


if __name__ == "__main__":
    main()
