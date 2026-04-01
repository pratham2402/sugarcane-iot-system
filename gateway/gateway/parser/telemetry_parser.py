"""
Telemetry payload parser and validator.

Parses compact JSON payloads from ESP32 nodes, expands short keys to
full names, validates readings against known ranges, and produces
normalized telemetry records for storage and upload.
"""

import json
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Compact ↔ Full Key Mapping ──────────────────────────────────────────────

COMPACT_TOP_LEVEL = {
    "n": "node_id",
    "t": "timestamp",
    "fw": "firmware_version",
    "bv": "battery_voltage",
    "s": "status",
    "r": "readings",
}

COMPACT_READINGS = {
    "sm": "soil_moisture",
    "st": "soil_temperature",
    "at": "air_temperature",
    "hu": "humidity",
    "rp": "rainfall_pulses",
    "fp": "flow_pulses",
}

READING_UNITS = {
    "soil_moisture": "%",
    "soil_temperature": "°C",
    "air_temperature": "°C",
    "humidity": "%",
    "rainfall_pulses": "pulses",
    "flow_pulses": "pulses",
}

# Validation ranges: (min, max)
VALIDATION_RANGES = {
    "soil_moisture": (0.0, 100.0),
    "soil_temperature": (-10.0, 80.0),
    "air_temperature": (-40.0, 85.0),
    "humidity": (0.0, 100.0),
    "rainfall_pulses": (0, 65535),
    "flow_pulses": (0, 65535),
}

VALID_STATUSES = {"ok", "degraded", "error"}


# ─── Parsed Telemetry Record ─────────────────────────────────────────────────

@dataclass
class TelemetryReading:
    """A single sensor reading."""
    sensor_type: str
    value: float
    unit: str
    valid: bool


@dataclass
class TelemetryRecord:
    """A fully parsed and validated telemetry record."""
    node_id: str
    timestamp: int
    firmware_version: Optional[str] = None
    battery_voltage: Optional[float] = None
    status: str = "ok"
    readings: list = field(default_factory=list)
    parse_errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to the full-format dictionary for storage/upload."""
        readings_dict = {}
        for r in self.readings:
            readings_dict[r.sensor_type] = {
                "value": r.value,
                "unit": r.unit,
                "valid": r.valid,
            }

        result = {
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "status": self.status,
            "readings": readings_dict,
        }

        if self.firmware_version:
            result["firmware_version"] = self.firmware_version
        if self.battery_voltage is not None:
            result["battery_voltage"] = self.battery_voltage

        return result


# ─── Parser ──────────────────────────────────────────────────────────────────

class TelemetryParser:
    """
    Parse and validate telemetry payloads from ESP32 nodes.

    Handles both compact (LoRa) and full-format payloads.
    """

    def parse(self, raw_data: str) -> Optional[TelemetryRecord]:
        """
        Parse a raw JSON payload into a TelemetryRecord.

        Args:
            raw_data: Raw JSON string (compact or full format)

        Returns:
            TelemetryRecord on success, None if the payload is completely invalid
        """
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return None

        if not isinstance(data, dict):
            logger.error("Payload is not a JSON object")
            return None

        # Expand compact keys if needed
        data = self._expand_compact(data)

        # Validate required fields
        node_id = data.get("node_id")
        timestamp = data.get("timestamp")

        if not node_id or not isinstance(node_id, str):
            logger.error("Missing or invalid node_id")
            return None

        if timestamp is None:
            logger.warning(f"Missing timestamp for {node_id}, using current time")
            timestamp = int(time.time())

        if not isinstance(timestamp, (int, float)):
            logger.error(f"Invalid timestamp type for {node_id}: {type(timestamp)}")
            return None

        timestamp = int(timestamp)

        # Build record
        record = TelemetryRecord(
            node_id=node_id,
            timestamp=timestamp,
            firmware_version=data.get("firmware_version"),
            battery_voltage=data.get("battery_voltage"),
            status=self._validate_status(data.get("status", "ok")),
        )

        # Parse readings
        readings_data = data.get("readings", {})
        if isinstance(readings_data, dict):
            for sensor_type, reading_data in readings_data.items():
                reading = self._parse_reading(sensor_type, reading_data)
                if reading:
                    record.readings.append(reading)
                else:
                    record.parse_errors.append(
                        f"Failed to parse reading: {sensor_type}"
                    )

        logger.debug(
            f"Parsed {node_id}: {len(record.readings)} readings, "
            f"{len(record.parse_errors)} errors"
        )
        return record

    def _expand_compact(self, data: dict) -> dict:
        """Expand compact keys to full names."""
        expanded = {}

        for key, value in data.items():
            full_key = COMPACT_TOP_LEVEL.get(key, key)

            if full_key == "readings" and isinstance(value, dict):
                expanded_readings = {}
                for rkey, rval in value.items():
                    full_rkey = COMPACT_READINGS.get(rkey, rkey)
                    # Compact format: [value, valid] → full format dict
                    if isinstance(rval, list) and len(rval) == 2:
                        expanded_readings[full_rkey] = {
                            "value": rval[0],
                            "unit": READING_UNITS.get(full_rkey, "unknown"),
                            "valid": bool(rval[1]),
                        }
                    elif isinstance(rval, dict):
                        expanded_readings[full_rkey] = rval
                    else:
                        logger.warning(f"Unexpected reading format for {rkey}: {rval}")
                expanded["readings"] = expanded_readings
            else:
                expanded[full_key] = value

        return expanded

    def _parse_reading(self, sensor_type: str,
                       reading_data) -> Optional[TelemetryReading]:
        """Parse a single sensor reading."""
        if isinstance(reading_data, dict):
            value = reading_data.get("value")
            unit = reading_data.get("unit", READING_UNITS.get(sensor_type, "unknown"))
            valid = reading_data.get("valid", True)
        elif isinstance(reading_data, list) and len(reading_data) == 2:
            # Compact format: [value, valid]
            value = reading_data[0]
            unit = READING_UNITS.get(sensor_type, "unknown")
            valid = bool(reading_data[1])
        else:
            logger.warning(f"Invalid reading format for {sensor_type}")
            return None

        if value is None:
            return None

        try:
            value = float(value)
        except (TypeError, ValueError):
            logger.warning(f"Non-numeric value for {sensor_type}: {value}")
            return None

        # Cross-validate against known ranges
        if sensor_type in VALIDATION_RANGES:
            min_val, max_val = VALIDATION_RANGES[sensor_type]
            if not (min_val <= value <= max_val):
                logger.warning(
                    f"Out of range: {sensor_type}={value} "
                    f"(expected {min_val}–{max_val})"
                )
                valid = False

        return TelemetryReading(
            sensor_type=sensor_type,
            value=value,
            unit=unit,
            valid=valid,
        )

    @staticmethod
    def _validate_status(status: str) -> str:
        """Validate and normalize the status field."""
        if status in VALID_STATUSES:
            return status
        logger.warning(f"Unknown status '{status}', defaulting to 'degraded'")
        return "degraded"
