"""
Cloud uploader — sends telemetry to the backend API.

Handles HTTP POST requests to the cloud backend with timeout
and error classification (transient vs permanent failures).
"""

import json
import time
import logging
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class CloudUploader:
    """
    Sends telemetry batches to the cloud backend via HTTP POST.

    Features:
    - Configurable endpoint and timeout
    - Distinguishes transient (retry-worthy) vs permanent errors
    - Connection error handling for offline scenarios
    """

    def __init__(self, config: dict):
        self.base_url = config.get("base_url", "http://localhost:8000")
        self.ingest_endpoint = config.get("ingest_endpoint", "/telemetry/ingest")
        self.timeout = config.get("request_timeout", 15)
        self._url = f"{self.base_url}{self.ingest_endpoint}"
        self._last_success = None
        self._last_error = None

    def upload(self, payload_json: str) -> Tuple[bool, Optional[str]]:
        """
        Upload a single telemetry payload to the cloud.

        Args:
            payload_json: JSON string of the telemetry record

        Returns:
            (success: bool, error_message: str or None)
        """
        try:
            data = json.loads(payload_json)

            response = requests.post(
                self._url,
                json=data,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code in (200, 201):
                self._last_success = time.time()
                logger.debug(f"Upload OK: {response.status_code}")
                return True, None

            elif response.status_code == 409:
                # Duplicate — treat as success (data already exists)
                logger.debug("Upload: duplicate record (409), treated as success")
                return True, None

            elif response.status_code >= 500:
                # Server error — transient, worth retrying
                error = f"Server error: {response.status_code}"
                self._last_error = error
                logger.warning(f"Upload failed (transient): {error}")
                return False, error

            else:
                # Client error (4xx except 409) — likely permanent
                error = f"Client error: {response.status_code} - {response.text[:200]}"
                self._last_error = error
                logger.error(f"Upload failed (permanent): {error}")
                return False, error

        except requests.ConnectionError:
            error = "Connection failed — backend unreachable"
            self._last_error = error
            logger.warning(f"Upload failed: {error}")
            return False, error

        except requests.Timeout:
            error = f"Request timeout ({self.timeout}s)"
            self._last_error = error
            logger.warning(f"Upload failed: {error}")
            return False, error

        except json.JSONDecodeError as e:
            error = f"Invalid JSON payload: {e}"
            self._last_error = error
            logger.error(f"Upload failed: {error}")
            return False, error

        except Exception as e:
            error = f"Unexpected error: {e}"
            self._last_error = error
            logger.error(f"Upload failed: {error}")
            return False, error

    def upload_batch(self, payloads: list) -> Tuple[int, int]:
        """
        Upload a batch of payloads.

        Args:
            payloads: List of (queue_id, payload_json) tuples

        Returns:
            (success_count, failure_count)
        """
        success = 0
        failure = 0

        for queue_id, payload_json in payloads:
            ok, error = self.upload(payload_json)
            if ok:
                success += 1
            else:
                failure += 1

        return success, failure

    def is_backend_reachable(self) -> bool:
        """Quick health check against the backend."""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except (requests.ConnectionError, requests.Timeout):
            return False

    @property
    def last_success_time(self) -> Optional[float]:
        return self._last_success

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error
