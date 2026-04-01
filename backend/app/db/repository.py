"""
Telemetry data repository.

Provides data access methods for telemetry storage and retrieval.
This repository pattern isolates all SQL from the API layer,
making it straightforward to swap database implementations.
"""

import sqlite3
import logging
from typing import Optional, List, Dict

from ..models.schemas import TelemetryIngestRequest

logger = logging.getLogger(__name__)


class TelemetryRepository:
    """
    Data access layer for telemetry readings and node management.

    All database operations go through this class. To swap from SQLite
    to PostgreSQL, create a new repository implementation with the
    same public interface.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ─── Telemetry Ingestion ─────────────────────────────────────────────────

    def ingest_reading(self, reading: TelemetryIngestRequest) -> bool:
        """
        Ingest a single telemetry reading.

        Returns True if inserted, False if duplicate.
        """
        readings = reading.readings

        def get_val(key):
            r = readings.get(key)
            return r.value if r else None

        def get_valid(key):
            r = readings.get(key)
            return 1 if (r and r.valid) else (0 if r else None)

        try:
            cursor = self.conn.execute(
                """INSERT OR IGNORE INTO telemetry_readings
                   (node_id, timestamp, firmware_version, battery_voltage, status,
                    soil_moisture, soil_moisture_valid,
                    soil_temperature, soil_temperature_valid,
                    air_temperature, air_temperature_valid,
                    humidity, humidity_valid,
                    rainfall_pulses, rainfall_pulses_valid,
                    flow_pulses, flow_pulses_valid)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    reading.node_id, reading.timestamp,
                    reading.firmware_version, reading.battery_voltage,
                    reading.status,
                    get_val("soil_moisture"), get_valid("soil_moisture"),
                    get_val("soil_temperature"), get_valid("soil_temperature"),
                    get_val("air_temperature"), get_valid("air_temperature"),
                    get_val("humidity"), get_valid("humidity"),
                    get_val("rainfall_pulses"), get_valid("rainfall_pulses"),
                    get_val("flow_pulses"), get_valid("flow_pulses"),
                )
            )
            self.conn.commit()

            if cursor.rowcount > 0:
                # Update node registry
                self._update_node(reading)
                return True

            return False  # Duplicate

        except sqlite3.Error as e:
            logger.error(f"Ingest error: {e}")
            raise

    def ingest_batch(self, readings: List[TelemetryIngestRequest]) -> tuple:
        """
        Ingest a batch of readings.

        Returns (ingested_count, duplicate_count).
        """
        ingested = 0
        duplicates = 0

        for reading in readings:
            if self.ingest_reading(reading):
                ingested += 1
            else:
                duplicates += 1

        return ingested, duplicates

    # ─── Queries ─────────────────────────────────────────────────────────────

    def get_total_readings(self) -> int:
        """Get total count of telemetry readings."""
        row = self.conn.execute(
            "SELECT COUNT(*) FROM telemetry_readings"
        ).fetchone()
        return row[0] if row else 0

    def get_total_nodes(self) -> int:
        """Get total count of registered nodes."""
        row = self.conn.execute(
            "SELECT COUNT(*) FROM node_registry"
        ).fetchone()
        return row[0] if row else 0

    def get_nodes(self) -> List[Dict]:
        """Get all registered nodes."""
        rows = self.conn.execute(
            """SELECT node_id, firmware_version, first_seen_at, last_seen_at,
                      total_readings, last_status, last_battery_voltage
               FROM node_registry ORDER BY node_id"""
        ).fetchall()

        return [dict(row) for row in rows]

    def get_node(self, node_id: str) -> Optional[Dict]:
        """Get a specific node by ID."""
        row = self.conn.execute(
            """SELECT node_id, firmware_version, first_seen_at, last_seen_at,
                      total_readings, last_status, last_battery_voltage
               FROM node_registry WHERE node_id = ?""",
            (node_id,)
        ).fetchone()

        return dict(row) if row else None

    def get_latest_readings(self) -> List[Dict]:
        """Get the most recent reading for each node."""
        rows = self.conn.execute(
            """SELECT t.node_id, t.timestamp, t.firmware_version,
                      t.battery_voltage, t.status,
                      t.soil_moisture, t.soil_temperature,
                      t.air_temperature, t.humidity,
                      t.rainfall_pulses, t.flow_pulses
               FROM telemetry_readings t
               INNER JOIN (
                   SELECT node_id, MAX(timestamp) as max_ts
                   FROM telemetry_readings
                   GROUP BY node_id
               ) latest ON t.node_id = latest.node_id
                        AND t.timestamp = latest.max_ts
               ORDER BY t.node_id"""
        ).fetchall()

        return [dict(row) for row in rows]

    def get_readings(self, node_id: Optional[str] = None,
                     start_time: Optional[int] = None,
                     end_time: Optional[int] = None,
                     limit: int = 100) -> List[Dict]:
        """
        Query telemetry readings with optional filters.

        Args:
            node_id: Filter by node ID
            start_time: Filter readings after this timestamp
            end_time: Filter readings before this timestamp
            limit: Maximum number of results
        """
        query = """SELECT node_id, timestamp, firmware_version,
                          battery_voltage, status,
                          soil_moisture, soil_temperature,
                          air_temperature, humidity,
                          rainfall_pulses, flow_pulses
                   FROM telemetry_readings WHERE 1=1"""
        params = []

        if node_id:
            query += " AND node_id = ?"
            params.append(node_id)
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    # ─── Node Registry ───────────────────────────────────────────────────────

    def _update_node(self, reading: TelemetryIngestRequest) -> None:
        """Update or create node registry entry."""
        self.conn.execute(
            """INSERT INTO node_registry
                 (node_id, firmware_version, last_seen_at, total_readings,
                  last_status, last_battery_voltage)
               VALUES (?, ?, CURRENT_TIMESTAMP, 1, ?, ?)
               ON CONFLICT(node_id) DO UPDATE SET
                 firmware_version = COALESCE(excluded.firmware_version, firmware_version),
                 last_seen_at = CURRENT_TIMESTAMP,
                 total_readings = total_readings + 1,
                 last_status = excluded.last_status,
                 last_battery_voltage = COALESCE(excluded.last_battery_voltage, last_battery_voltage)""",
            (reading.node_id, reading.firmware_version,
             reading.status, reading.battery_voltage)
        )
        self.conn.commit()
