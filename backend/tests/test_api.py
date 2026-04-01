"""Tests for the backend API."""

import json
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    """Create a test client with a temporary database."""
    config = {
        "server": {"title": "Test API", "version": "test"},
        "database": {"url": f"sqlite:///{tmp_path}/test.db"},
    }
    app = create_app(config)

    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_reading():
    return {
        "node_id": "node-01",
        "timestamp": 1711929600,
        "firmware_version": "1.0.0",
        "battery_voltage": 3.72,
        "status": "ok",
        "readings": {
            "soil_moisture": {"value": 62.5, "unit": "%", "valid": True},
            "soil_temperature": {"value": 28.3, "unit": "°C", "valid": True},
            "air_temperature": {"value": 32.1, "unit": "°C", "valid": True},
            "humidity": {"value": 71.0, "unit": "%", "valid": True},
        }
    }


class TestHealthEndpoint:

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "total_readings" in data
        assert "total_nodes" in data


class TestTelemetryEndpoints:

    def test_ingest_single(self, client, sample_reading):
        response = client.post("/telemetry/ingest", json=sample_reading)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["ingested"] == 1
        assert data["duplicates"] == 0

    def test_ingest_duplicate(self, client, sample_reading):
        client.post("/telemetry/ingest", json=sample_reading)
        response = client.post("/telemetry/ingest", json=sample_reading)
        assert response.status_code == 200
        data = response.json()
        assert data["ingested"] == 0
        assert data["duplicates"] == 1

    def test_ingest_invalid_node_id(self, client):
        response = client.post("/telemetry/ingest", json={
            "node_id": "",
            "timestamp": 12345,
            "readings": {}
        })
        assert response.status_code == 422  # Validation error

    def test_ingest_batch(self, client):
        readings = [
            {
                "node_id": "node-01",
                "timestamp": 1711929600 + i,
                "status": "ok",
                "readings": {
                    "soil_moisture": {"value": 60.0 + i, "unit": "%", "valid": True}
                }
            }
            for i in range(5)
        ]

        response = client.post("/telemetry/ingest/batch", json={"readings": readings})
        assert response.status_code == 200
        data = response.json()
        assert data["ingested"] == 5


class TestNodeEndpoints:

    def test_list_nodes_empty(self, client):
        response = client.get("/nodes")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_nodes_after_ingest(self, client, sample_reading):
        client.post("/telemetry/ingest", json=sample_reading)
        response = client.get("/nodes")
        assert response.status_code == 200
        nodes = response.json()
        assert len(nodes) == 1
        assert nodes[0]["node_id"] == "node-01"

    def test_get_node_not_found(self, client):
        response = client.get("/nodes/nonexistent")
        assert response.status_code == 404


class TestReadingsEndpoints:

    def test_latest_readings(self, client, sample_reading):
        client.post("/telemetry/ingest", json=sample_reading)
        response = client.get("/latest-readings")
        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["node_id"] == "node-01"

    def test_query_readings(self, client, sample_reading):
        client.post("/telemetry/ingest", json=sample_reading)
        response = client.get("/readings?node_id=node-01")
        assert response.status_code == 200
        readings = response.json()
        assert len(readings) == 1

    def test_query_readings_empty(self, client):
        response = client.get("/readings?node_id=nonexistent")
        assert response.status_code == 200
        assert response.json() == []
