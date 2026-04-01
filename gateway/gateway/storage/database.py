"""
SQLite database manager for the gateway.

Provides high-level methods for storing raw packets, parsed telemetry,
managing the upload queue, and querying data. All operations use the
SQLite database initialized by migrations.py.
"""

import json
import sqlite3
import time
import logging
from typing import Optional, List, Tuple

from ..parser.telemetry_parser import TelemetryRecord
from ..receiver.base_receiver import RawPacket

logger = logging.getLogger(__name__)


class GatewayDatabase:
    """
    High-level database operations for the gateway.

    Thread-safe through SQLite's WAL mode and check_same_thread=False.
    """

    def __init__(self, connection: sqlite3.Connection):
        self.conn = connection

    # ─── Raw Packets ─────────────────────────────────────────────────────────

    def store_raw_packet(self, packet: RawPacket) -> int:
        """Store a raw packet and return its row ID."""
        cursor = self.conn.execute(
            """INSERT INTO raw_packets (data, received_at, rssi, snr, source)
               VALUES (?, ?, ?, ?, ?)""",
            (packet.data, packet.received_at, packet.rssi, packet.snr, packet.source)
        )
        self.conn.commit()
        return cursor.lastrowid

    # ─── Telemetry Readings ──────────────────────────────────────────────────

    def store_telemetry(self, record: TelemetryRecord) -> Optional[int]:
        """
        Store a parsed telemetry record.

        Returns the row ID on success, None if duplicate (same node_id + timestamp).
        """
        # Extract reading values
        readings_map = {r.sensor_type: r for r in record.readings}

        def get_val(key):
            r = readings_map.get(key)
            return r.value if r else None

        def get_valid(key):
            r = readings_map.get(key)
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
                    record.node_id, record.timestamp,
                    record.firmware_version, record.battery_voltage, record.status,
                    get_val("soil_moisture"), get_valid("soil_moisture"),
                    get_val("soil_temperature"), get_valid("soil_temperature"),
                    get_val("air_temperature"), get_valid("air_temperature"),
                    get_val("humidity"), get_valid("humidity"),
                    get_val("rainfall_pulses"), get_valid("rainfall_pulses"),
                    get_val("flow_pulses"), get_valid("flow_pulses"),
                )
            )
            self.conn.commit()

            if cursor.rowcount == 0:
                logger.debug(
                    f"Duplicate telemetry: {record.node_id}@{record.timestamp}"
                )
                return None

            row_id = cursor.lastrowid

            # Update node registry
            self._update_node_registry(record)

            return row_id

        except sqlite3.Error as e:
            logger.error(f"Failed to store telemetry: {e}")
            return None

    # ─── Upload Queue ────────────────────────────────────────────────────────

    def enqueue_for_upload(self, telemetry_id: int,
                           record: TelemetryRecord) -> int:
        """Add a telemetry record to the upload queue."""
        payload = json.dumps(record.to_dict())
        cursor = self.conn.execute(
            """INSERT INTO upload_queue (telemetry_id, payload, status, next_retry_at)
               VALUES (?, ?, 'pending', ?)""",
            (telemetry_id, payload, time.time())
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_pending_uploads(self, limit: int = 10) -> List[Tuple[int, str]]:
        """
        Get pending upload queue entries ready for sending.

        Returns list of (queue_id, payload_json) tuples.
        """
        now = time.time()
        rows = self.conn.execute(
            """SELECT id, payload FROM upload_queue
               WHERE status = 'pending' AND (next_retry_at IS NULL OR next_retry_at <= ?)
               ORDER BY created_at ASC
               LIMIT ?""",
            (now, limit)
        ).fetchall()
        return [(row[0], row[1]) for row in rows]

    def mark_uploaded(self, queue_id: int) -> None:
        """Mark a queue entry as successfully uploaded."""
        self.conn.execute(
            """UPDATE upload_queue
               SET status = 'uploaded', uploaded_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (queue_id,)
        )
        self.conn.commit()

    def mark_upload_failed(self, queue_id: int, error: str,
                           next_retry_at: float) -> None:
        """Mark a queue entry as failed and schedule retry."""
        self.conn.execute(
            """UPDATE upload_queue
               SET status = 'pending', retry_count = retry_count + 1,
                   last_error = ?, next_retry_at = ?
               WHERE id = ?""",
            (error, next_retry_at, queue_id)
        )
        self.conn.commit()

    def get_queue_stats(self) -> dict:
        """Get upload queue statistics."""
        row = self.conn.execute(
            """SELECT
                 COUNT(*) FILTER (WHERE status = 'pending') as pending,
                 COUNT(*) FILTER (WHERE status = 'uploaded') as uploaded,
                 MAX(retry_count) as max_retries
               FROM upload_queue"""
        ).fetchone()

        if row:
            return {
                "pending": row[0] or 0,
                "uploaded": row[1] or 0,
                "max_retries": row[2] or 0,
            }
        return {"pending": 0, "uploaded": 0, "max_retries": 0}

    # ─── Node Registry ───────────────────────────────────────────────────────

    def _update_node_registry(self, record: TelemetryRecord) -> None:
        """Update or insert node registry entry."""
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
            (record.node_id, record.firmware_version,
             record.status, record.battery_voltage)
        )
        self.conn.commit()

    def get_registered_nodes(self) -> List[dict]:
        """Get all registered nodes."""
        rows = self.conn.execute(
            """SELECT node_id, firmware_version, first_seen_at, last_seen_at,
                      total_readings, last_status, last_battery_voltage
               FROM node_registry ORDER BY node_id"""
        ).fetchall()

        return [
            {
                "node_id": r[0],
                "firmware_version": r[1],
                "first_seen_at": r[2],
                "last_seen_at": r[3],
                "total_readings": r[4],
                "last_status": r[5],
                "last_battery_voltage": r[6],
            }
            for r in rows
        ]

    # ─── Statistics ──────────────────────────────────────────────────────────

    def get_reading_count(self) -> int:
        """Get total number of stored telemetry readings."""
        row = self.conn.execute(
            "SELECT COUNT(*) FROM telemetry_readings"
        ).fetchone()
        return row[0] if row else 0

    def get_database_size_bytes(self) -> int:
        """Get the database file size in bytes."""
        row = self.conn.execute("PRAGMA page_count").fetchone()
        page_size_row = self.conn.execute("PRAGMA page_size").fetchone()
        if row and page_size_row:
            return row[0] * page_size_row[0]
        return 0
