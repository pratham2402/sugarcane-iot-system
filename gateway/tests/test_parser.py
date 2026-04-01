"""Tests for the telemetry parser."""

import json
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gateway.parser.telemetry_parser import TelemetryParser


@pytest.fixture
def parser():
    return TelemetryParser()


class TestTelemetryParser:
    """Test the telemetry parser with various payload formats."""

    def test_parse_compact_payload(self, parser):
        """Test parsing a compact (LoRa) format payload."""
        payload = json.dumps({
            "n": "node-01",
            "t": 1711929600,
            "fw": "1.0.0",
            "bv": 3.72,
            "s": "ok",
            "r": {
                "sm": [62.5, True],
                "st": [28.3, True],
                "at": [32.1, True],
                "hu": [71.0, True],
            }
        })

        record = parser.parse(payload)

        assert record is not None
        assert record.node_id == "node-01"
        assert record.timestamp == 1711929600
        assert record.firmware_version == "1.0.0"
        assert record.battery_voltage == 3.72
        assert record.status == "ok"
        assert len(record.readings) == 4

        # Check soil moisture
        sm = next(r for r in record.readings if r.sensor_type == "soil_moisture")
        assert sm.value == 62.5
        assert sm.valid is True
        assert sm.unit == "%"

    def test_parse_full_format_payload(self, parser):
        """Test parsing a full (expanded) format payload."""
        payload = json.dumps({
            "node_id": "node-02",
            "timestamp": 1711929600,
            "status": "ok",
            "readings": {
                "soil_moisture": {"value": 55.0, "unit": "%", "valid": True},
                "humidity": {"value": 80.0, "unit": "%", "valid": True},
            }
        })

        record = parser.parse(payload)

        assert record is not None
        assert record.node_id == "node-02"
        assert len(record.readings) == 2

    def test_parse_invalid_json(self, parser):
        """Test parsing invalid JSON returns None."""
        assert parser.parse("not json") is None
        assert parser.parse("{broken") is None

    def test_parse_missing_node_id(self, parser):
        """Test parsing without node_id returns None."""
        payload = json.dumps({"t": 12345, "s": "ok", "r": {}})
        assert parser.parse(payload) is None

    def test_parse_out_of_range_value(self, parser):
        """Test that out-of-range values are marked invalid."""
        payload = json.dumps({
            "n": "node-01",
            "t": 1711929600,
            "s": "ok",
            "r": {
                "sm": [150.0, True],  # Out of range (max 100)
            }
        })

        record = parser.parse(payload)
        assert record is not None
        sm = next(r for r in record.readings if r.sensor_type == "soil_moisture")
        assert sm.valid is False  # Should be invalidated by parser

    def test_parse_empty_readings(self, parser):
        """Test parsing with no readings."""
        payload = json.dumps({
            "n": "node-01",
            "t": 1711929600,
            "s": "error",
            "r": {}
        })

        record = parser.parse(payload)
        assert record is not None
        assert len(record.readings) == 0

    def test_to_dict_roundtrip(self, parser):
        """Test that parsed record can be serialized back to a dict."""
        payload = json.dumps({
            "n": "node-01",
            "t": 1711929600,
            "fw": "1.0.0",
            "s": "ok",
            "r": {"sm": [62.5, True]}
        })

        record = parser.parse(payload)
        d = record.to_dict()

        assert d["node_id"] == "node-01"
        assert d["timestamp"] == 1711929600
        assert "soil_moisture" in d["readings"]
        assert d["readings"]["soil_moisture"]["value"] == 62.5
