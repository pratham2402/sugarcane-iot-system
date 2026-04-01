"""
SQLite database models and data access layer.

Provides typed helpers for inserting and querying telemetry data.
These models mirror the database schema from migrations.py.
"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class RawPacketRow:
    """Represents a row in the raw_packets table."""
    id: Optional[int] = None
    data: str = ""
    received_at: float = 0.0
    rssi: Optional[float] = None
    snr: Optional[float] = None
    source: str = "unknown"


@dataclass
class TelemetryRow:
    """Represents a row in the telemetry_readings table."""
    id: Optional[int] = None
    node_id: str = ""
    timestamp: int = 0
    firmware_version: Optional[str] = None
    battery_voltage: Optional[float] = None
    status: str = "ok"
    soil_moisture: Optional[float] = None
    soil_moisture_valid: Optional[bool] = None
    soil_temperature: Optional[float] = None
    soil_temperature_valid: Optional[bool] = None
    air_temperature: Optional[float] = None
    air_temperature_valid: Optional[bool] = None
    humidity: Optional[float] = None
    humidity_valid: Optional[bool] = None
    rainfall_pulses: Optional[int] = None
    rainfall_pulses_valid: Optional[bool] = None
    flow_pulses: Optional[int] = None
    flow_pulses_valid: Optional[bool] = None


@dataclass
class UploadQueueRow:
    """Represents a row in the upload_queue table."""
    id: Optional[int] = None
    telemetry_id: int = 0
    payload: str = ""
    status: str = "pending"
    retry_count: int = 0
    next_retry_at: Optional[float] = None
    last_error: Optional[str] = None
    uploaded_at: Optional[str] = None


@dataclass
class NodeRegistryRow:
    """Represents a row in the node_registry table."""
    node_id: str = ""
    firmware_version: Optional[str] = None
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    total_readings: int = 0
    last_status: Optional[str] = None
    last_battery_voltage: Optional[float] = None
