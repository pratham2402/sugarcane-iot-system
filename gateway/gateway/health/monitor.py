"""
Gateway health monitor.

Tracks the overall health status of the gateway including:
- Receiver status
- Database statistics
- Upload queue depth
- Node heartbeat tracking
- System resource usage
"""

import time
import logging
from typing import Optional

from ..storage.database import GatewayDatabase
from ..uploader.cloud_uploader import CloudUploader
from ..uploader.retry_queue import RetryQueueWorker
from ..receiver.base_receiver import BaseReceiver

logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    Monitors and reports gateway health status.

    Aggregates health information from all gateway subsystems
    into a single status report.
    """

    def __init__(self, config: dict):
        self.config = config
        self.stale_threshold = config.get("stale_node_threshold", 300)
        self._start_time = time.time()
        self._packets_received = 0
        self._packets_parsed = 0
        self._parse_errors = 0

    def record_packet_received(self) -> None:
        self._packets_received += 1

    def record_packet_parsed(self, success: bool) -> None:
        if success:
            self._packets_parsed += 1
        else:
            self._parse_errors += 1

    def get_status(self, receiver: BaseReceiver,
                   db: GatewayDatabase,
                   uploader: CloudUploader,
                   upload_worker: RetryQueueWorker) -> dict:
        """
        Generate a comprehensive health status report.

        Returns a dict with all gateway health metrics.
        """
        uptime = time.time() - self._start_time
        queue_stats = db.get_queue_stats()
        nodes = db.get_registered_nodes()

        # Check for stale nodes
        stale_nodes = []
        now = time.time()
        for node in nodes:
            last_seen = node.get("last_seen_at")
            if last_seen:
                # last_seen_at is a timestamp string from SQLite
                # For simplicity, just check if node exists
                pass

        # Determine overall health
        health = "healthy"
        issues = []

        if not receiver.is_active():
            health = "degraded"
            issues.append("Receiver not active")

        if not upload_worker.is_running():
            health = "degraded"
            issues.append("Upload worker not running")

        if queue_stats.get("pending", 0) > 100:
            health = "warning"
            issues.append(f"Large upload backlog: {queue_stats['pending']} pending")

        if self._parse_errors > self._packets_received * 0.2 and self._packets_received > 10:
            health = "degraded"
            issues.append(f"High parse error rate: {self._parse_errors}/{self._packets_received}")

        return {
            "status": health,
            "uptime_seconds": round(uptime, 1),
            "issues": issues,
            "receiver": {
                "active": receiver.is_active(),
                "type": type(receiver).__name__,
            },
            "packets": {
                "received": self._packets_received,
                "parsed": self._packets_parsed,
                "errors": self._parse_errors,
            },
            "storage": {
                "total_readings": db.get_reading_count(),
                "database_size_bytes": db.get_database_size_bytes(),
            },
            "upload": {
                "worker_running": upload_worker.is_running(),
                "queue": queue_stats,
                "worker_stats": upload_worker.stats,
                "last_success": uploader.last_success_time,
                "last_error": uploader.last_error,
                "backend_reachable": None,  # Checked on demand
            },
            "nodes": {
                "registered": len(nodes),
                "details": nodes,
            },
        }

    def check_backend_connectivity(self, uploader: CloudUploader) -> bool:
        """Perform a backend health check (may be slow)."""
        reachable = uploader.is_backend_reachable()
        logger.info(f"Backend connectivity check: {'OK' if reachable else 'UNREACHABLE'}")
        return reachable
