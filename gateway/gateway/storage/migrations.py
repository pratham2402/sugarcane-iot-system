"""
SQLite database schema definitions and migration.

Creates and manages the gateway's local database tables for
raw packets, parsed telemetry, upload queue, and node registry.
"""

import sqlite3
import logging
import os

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Raw packets as received from the transport layer
CREATE TABLE IF NOT EXISTS raw_packets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    received_at REAL NOT NULL,
    rssi REAL,
    snr REAL,
    source TEXT DEFAULT 'unknown',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Parsed and validated telemetry readings
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(node_id, timestamp)
);

-- Upload queue for cloud synchronization
CREATE TABLE IF NOT EXISTS upload_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telemetry_id INTEGER NOT NULL,
    payload TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    next_retry_at REAL,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_at TIMESTAMP,
    FOREIGN KEY (telemetry_id) REFERENCES telemetry_readings(id)
);

-- Known node registry
CREATE TABLE IF NOT EXISTS node_registry (
    node_id TEXT PRIMARY KEY,
    firmware_version TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_readings INTEGER DEFAULT 0,
    last_status TEXT,
    last_battery_voltage REAL
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_info (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_telemetry_node_ts
    ON telemetry_readings(node_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_upload_status
    ON upload_queue(status, next_retry_at);
CREATE INDEX IF NOT EXISTS idx_raw_received
    ON raw_packets(received_at);
"""


def initialize_database(db_path: str) -> sqlite3.Connection:
    """
    Initialize the SQLite database with the schema.

    Creates the database file and parent directories if needed.
    Applies schema migrations if the database already exists.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        An open database connection
    """
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)

    conn = sqlite3.connect(db_path, check_same_thread=False)

    # Enable WAL mode for better concurrent read/write performance
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Apply schema
    conn.executescript(SCHEMA_SQL)

    # Record schema version
    conn.execute(
        "INSERT OR REPLACE INTO schema_info (key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION))
    )
    conn.commit()

    logger.info(f"Database initialized at {db_path} (schema v{SCHEMA_VERSION})")
    return conn
