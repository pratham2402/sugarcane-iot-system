"""Tests for the telemetry repository."""

import time
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import DatabaseConnection
from app.db.repository import TelemetryRepository
from app.models.schemas import TelemetryIngestRequest, SensorReading


@pytest.fixture
def repo(tmp_path):
    db = DatabaseConnection(f"sqlite:///{tmp_path}/test.db")
    conn = db.connect()
    return TelemetryRepository(conn)


@pytest.fixture
def sample_request():
    return TelemetryIngestRequest(
        node_id="node-01",
        timestamp=int(time.time()),
        firmware_version="1.0.0",
        battery_voltage=3.72,
        status="ok",
        readings={
            "soil_moisture": SensorReading(value=62.5, unit="%", valid=True),
            "soil_temperature": SensorReading(value=28.3, unit="°C", valid=True),
        }
    )


class TestTelemetryRepository:

    def test_ingest_new_reading(self, repo, sample_request):
        result = repo.ingest_reading(sample_request)
        assert result is True
        assert repo.get_total_readings() == 1

    def test_ingest_duplicate(self, repo, sample_request):
        repo.ingest_reading(sample_request)
        result = repo.ingest_reading(sample_request)
        assert result is False
        assert repo.get_total_readings() == 1

    def test_ingest_batch(self, repo):
        readings = []
        ts = int(time.time())
        for i in range(5):
            readings.append(TelemetryIngestRequest(
                node_id="node-01",
                timestamp=ts + i,
                status="ok",
                readings={
                    "soil_moisture": SensorReading(value=60.0 + i, unit="%", valid=True),
                }
            ))

        ingested, dups = repo.ingest_batch(readings)
        assert ingested == 5
        assert dups == 0

    def test_node_registry_auto_created(self, repo, sample_request):
        repo.ingest_reading(sample_request)
        nodes = repo.get_nodes()
        assert len(nodes) == 1
        assert nodes[0]["node_id"] == "node-01"
        assert nodes[0]["total_readings"] == 1

    def test_node_registry_increments(self, repo):
        ts = int(time.time())
        for i in range(3):
            req = TelemetryIngestRequest(
                node_id="node-01",
                timestamp=ts + i,
                status="ok",
                readings={}
            )
            repo.ingest_reading(req)

        node = repo.get_node("node-01")
        assert node is not None
        assert node["total_readings"] == 3

    def test_get_latest_readings(self, repo):
        ts = int(time.time())
        # Insert readings for two nodes
        for node in ["node-01", "node-02"]:
            for i in range(3):
                repo.ingest_reading(TelemetryIngestRequest(
                    node_id=node,
                    timestamp=ts + i,
                    status="ok",
                    readings={
                        "soil_moisture": SensorReading(
                            value=50.0 + i, unit="%", valid=True
                        ),
                    }
                ))

        latest = repo.get_latest_readings()
        assert len(latest) == 2
        # Should return the latest timestamp for each node
        for reading in latest:
            assert reading["timestamp"] == ts + 2

    def test_get_readings_filtered(self, repo):
        ts = int(time.time())
        for i in range(10):
            repo.ingest_reading(TelemetryIngestRequest(
                node_id="node-01",
                timestamp=ts + i,
                status="ok",
                readings={}
            ))

        # Filter with limit
        results = repo.get_readings(node_id="node-01", limit=5)
        assert len(results) == 5

        # Filter by time range
        results = repo.get_readings(
            start_time=ts + 3,
            end_time=ts + 7,
        )
        assert len(results) == 5  # ts+3 through ts+7
