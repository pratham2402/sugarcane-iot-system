"""
Database connection manager.

Handles SQLite (MVP) database initialization and provides a connection
interface. Structured so PostgreSQL can replace SQLite by changing this module.
"""

import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

# ─── Schema ──────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS telemetry_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    firmware_version TEXT,
    battery_voltage REAL,
    status TEXT DEFAULT 'ok',
    soil_moisture REAL,
    soil_moisture_valid INTEGER,
    soil_temperature REAL,
    soil_temperature_valid INTEGER,
    air_temperature REAL,
    air_temperature_valid INTEGER,
    humidity REAL,
    humidity_valid INTEGER,
    rainfall_pulses INTEGER,
    rainfall_pulses_valid INTEGER,
    flow_pulses INTEGER,
    flow_pulses_valid INTEGER,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(node_id, timestamp)
);

CREATE TABLE IF NOT EXISTS node_registry (
    node_id TEXT PRIMARY KEY,
    firmware_version TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_readings INTEGER DEFAULT 0,
    last_status TEXT,
    last_battery_voltage REAL
);

CREATE INDEX IF NOT EXISTS idx_readings_node_ts
    ON telemetry_readings(node_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_readings_timestamp
    ON telemetry_readings(timestamp DESC);
"""


class DatabaseConnection:
    """
    SQLite database connection manager.

    For PostgreSQL migration:
    - Replace sqlite3 with psycopg2 or asyncpg
    - Update SCHEMA_SQL to use PostgreSQL syntax
    - Keep the same public interface
    """

    def __init__(self, db_url: str):
        """
        Initialize database connection.

        Args:
            db_url: Database URL. For SQLite: "sqlite:///path/to/db.db"
        """
        self.db_url = db_url
        self._conn = None

        # Parse SQLite path from URL
        if db_url.startswith("sqlite:///"):
            self.db_path = db_url.replace("sqlite:///", "")
        else:
            self.db_path = db_url

    def connect(self) -> sqlite3.Connection:
        """Open the database connection and initialize schema."""
        # Ensure directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        # SQLite optimizations
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

        # Apply schema
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

        logger.info(f"Database connected: {self.db_path}")
        return self._conn

    def get_connection(self) -> sqlite3.Connection:
        """Get the active database connection."""
        if self._conn is None:
            return self.connect()
        return self._conn

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Database connection closed")
