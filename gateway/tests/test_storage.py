"""Tests for the gateway storage layer."""

import json
import time
import pytest
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gateway.storage.migrations import initialize_database
from gateway.storage.database import GatewayDatabase
from gateway.parser.telemetry_parser import TelemetryParser, TelemetryRecord
from gateway.receiver.base_receiver import RawPacket


@pytest.fixture
def db():
    """Create an in-memory database for testing."""
    conn = initialize_database(":memory:")
    return GatewayDatabase(conn)


@pytest.fixture
def parser():
    return TelemetryParser()


@pytest.fixture
def sample_record(parser):
    payload = json.dumps({
        "n": "node-01",
        "t": int(time.time()),
        "fw": "1.0.0",
        "bv": 3.8,
        "s": "ok",
        "r": {
            "sm": [65.0, True],
            "st": [27.5, True],
            "at": [31.0, True],
            "hu": [72.0, True],
        }
    })
    return parser.parse(payload)


class TestGatewayDatabase:

    def test_store_raw_packet(self, db):
        packet = RawPacket(
            data='{"n":"node-01","t":12345}',
            received_at=time.time(),
            rssi=-65.0,
            source="mock"
        )
        row_id = db.store_raw_packet(packet)
        assert row_id is not None
        assert row_id > 0

    def test_store_telemetry(self, db, sample_record):
        row_id = db.store_telemetry(sample_record)
        assert row_id is not None
        assert row_id > 0
        assert db.get_reading_count() == 1

    def test_store_duplicate_telemetry(self, db, sample_record):
        row_id1 = db.store_telemetry(sample_record)
        row_id2 = db.store_telemetry(sample_record)
        assert row_id1 is not None
        assert row_id2 is None  # Duplicate
        assert db.get_reading_count() == 1

    def test_enqueue_and_get_pending(self, db, sample_record):
        telemetry_id = db.store_telemetry(sample_record)
        db.enqueue_for_upload(telemetry_id, sample_record)

        pending = db.get_pending_uploads(limit=5)
        assert len(pending) == 1
        queue_id, payload = pending[0]
        assert queue_id > 0

        data = json.loads(payload)
        assert data["node_id"] == "node-01"

    def test_mark_uploaded(self, db, sample_record):
        telemetry_id = db.store_telemetry(sample_record)
        db.enqueue_for_upload(telemetry_id, sample_record)

        pending = db.get_pending_uploads()
        queue_id = pending[0][0]

        db.mark_uploaded(queue_id)

        # Should no longer appear in pending
        pending_after = db.get_pending_uploads()
        assert len(pending_after) == 0

    def test_mark_upload_failed(self, db, sample_record):
        telemetry_id = db.store_telemetry(sample_record)
        db.enqueue_for_upload(telemetry_id, sample_record)

        pending = db.get_pending_uploads()
        queue_id = pending[0][0]

        # Mark as failed with future retry
        future_time = time.time() + 3600
        db.mark_upload_failed(queue_id, "Connection refused", future_time)

        # Should not appear in pending (retry time is in future)
        pending_after = db.get_pending_uploads()
        assert len(pending_after) == 0

    def test_node_registry(self, db, sample_record):
        db.store_telemetry(sample_record)

        nodes = db.get_registered_nodes()
        assert len(nodes) == 1
        assert nodes[0]["node_id"] == "node-01"
        assert nodes[0]["total_readings"] == 1

    def test_queue_stats(self, db, sample_record):
        telemetry_id = db.store_telemetry(sample_record)
        db.enqueue_for_upload(telemetry_id, sample_record)

        stats = db.get_queue_stats()
        assert stats["pending"] == 1
        assert stats["uploaded"] == 0
