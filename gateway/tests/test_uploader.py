"""Tests for the cloud uploader."""

import json
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gateway.uploader.cloud_uploader import CloudUploader


@pytest.fixture
def uploader():
    return CloudUploader({
        "base_url": "http://localhost:8000",
        "ingest_endpoint": "/telemetry/ingest",
        "request_timeout": 5,
    })


@pytest.fixture
def sample_payload():
    return json.dumps({
        "node_id": "node-01",
        "timestamp": 1711929600,
        "status": "ok",
        "readings": {
            "soil_moisture": {"value": 62.5, "unit": "%", "valid": True}
        }
    })


class TestCloudUploader:

    @patch("gateway.uploader.cloud_uploader.requests.post")
    def test_upload_success(self, mock_post, uploader, sample_payload):
        mock_post.return_value = MagicMock(status_code=200)

        success, error = uploader.upload(sample_payload)

        assert success is True
        assert error is None
        mock_post.assert_called_once()

    @patch("gateway.uploader.cloud_uploader.requests.post")
    def test_upload_duplicate(self, mock_post, uploader, sample_payload):
        mock_post.return_value = MagicMock(status_code=409)

        success, error = uploader.upload(sample_payload)

        assert success is True  # Duplicates treated as success

    @patch("gateway.uploader.cloud_uploader.requests.post")
    def test_upload_server_error(self, mock_post, uploader, sample_payload):
        mock_post.return_value = MagicMock(status_code=500)

        success, error = uploader.upload(sample_payload)

        assert success is False
        assert "Server error" in error

    @patch("gateway.uploader.cloud_uploader.requests.post")
    def test_upload_connection_error(self, mock_post, uploader, sample_payload):
        import requests
        mock_post.side_effect = requests.ConnectionError()

        success, error = uploader.upload(sample_payload)

        assert success is False
        assert "unreachable" in error.lower()

    def test_upload_invalid_json(self, uploader):
        success, error = uploader.upload("not valid json")

        assert success is False
        assert "JSON" in error

    @patch("gateway.uploader.cloud_uploader.requests.get")
    def test_backend_reachable(self, mock_get, uploader):
        mock_get.return_value = MagicMock(status_code=200)
        assert uploader.is_backend_reachable() is True

    @patch("gateway.uploader.cloud_uploader.requests.get")
    def test_backend_unreachable(self, mock_get, uploader):
        import requests
        mock_get.side_effect = requests.ConnectionError()
        assert uploader.is_backend_reachable() is False
