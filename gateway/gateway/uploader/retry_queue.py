"""
Upload retry queue worker.

Manages the background process of uploading queued telemetry to the cloud.
Implements exponential backoff with jitter for failed uploads.
"""

import time
import random
import logging
import threading
from typing import Optional

from ..storage.database import GatewayDatabase
from .cloud_uploader import CloudUploader

logger = logging.getLogger(__name__)


class RetryQueueWorker:
    """
    Background worker that processes the upload queue.

    Runs in a separate thread, periodically checking for pending uploads
    and sending them to the cloud backend with retry logic.
    """

    def __init__(self, db: GatewayDatabase, uploader: CloudUploader,
                 config: dict):
        self.db = db
        self.uploader = uploader
        self.config = config

        self.batch_size = config.get("batch_size", 10)
        self.upload_interval = config.get("upload_interval", 30)
        self.max_retries = config.get("max_retries", 5)
        self.retry_base_delay = config.get("retry_base_delay", 2)
        self.retry_max_delay = config.get("retry_max_delay", 300)

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._stats = {
            "total_uploaded": 0,
            "total_failed": 0,
            "total_retries": 0,
        }

    def start(self) -> None:
        """Start the upload worker thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="upload-worker",
            daemon=True
        )
        self._thread.start()
        logger.info(
            f"Upload worker started (interval={self.upload_interval}s, "
            f"batch={self.batch_size})"
        )

    def stop(self) -> None:
        """Signal the upload worker to stop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Upload worker stopped")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    def _run(self) -> None:
        """Main worker loop."""
        logger.info("Upload worker thread running")

        while not self._stop_event.is_set():
            try:
                self._process_batch()
            except Exception as e:
                logger.error(f"Upload worker error: {e}", exc_info=True)

            # Wait for the next cycle
            self._stop_event.wait(timeout=self.upload_interval)

        logger.info("Upload worker thread exiting")

    def _process_batch(self) -> None:
        """Process one batch of pending uploads."""
        pending = self.db.get_pending_uploads(limit=self.batch_size)

        if not pending:
            return

        logger.info(f"Processing {len(pending)} pending uploads")

        for queue_id, payload_json in pending:
            if self._stop_event.is_set():
                break

            success, error = self.uploader.upload(payload_json)

            if success:
                self.db.mark_uploaded(queue_id)
                self._stats["total_uploaded"] += 1
                logger.debug(f"Uploaded queue entry {queue_id}")
            else:
                self._stats["total_failed"] += 1
                self._stats["total_retries"] += 1

                # Calculate next retry time with exponential backoff + jitter
                next_retry = self._calculate_next_retry(queue_id)
                self.db.mark_upload_failed(queue_id, error or "Unknown", next_retry)

                logger.warning(
                    f"Upload failed for queue entry {queue_id}: {error}. "
                    f"Next retry at {time.strftime('%H:%M:%S', time.localtime(next_retry))}"
                )

    def _calculate_next_retry(self, queue_id: int) -> float:
        """
        Calculate the next retry timestamp using exponential backoff with jitter.

        backoff = min(base_delay * 2^retry_count + jitter, max_delay)
        """
        # Get current retry count from DB
        row = self.db.conn.execute(
            "SELECT retry_count FROM upload_queue WHERE id = ?",
            (queue_id,)
        ).fetchone()

        retry_count = row[0] if row else 0

        # Exponential backoff
        delay = min(
            self.retry_base_delay * (2 ** retry_count),
            self.retry_max_delay
        )

        # Add jitter (±25%)
        jitter = delay * random.uniform(-0.25, 0.25)
        delay = max(1, delay + jitter)

        return time.time() + delay
