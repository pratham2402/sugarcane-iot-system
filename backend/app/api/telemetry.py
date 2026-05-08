"""
Telemetry ingestion API endpoints.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException
from ..models.schemas import (
    TelemetryIngestRequest,
    BatchIngestRequest,
    IngestResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_telemetry(reading: TelemetryIngestRequest, request: Request):
    """
    Ingest a single telemetry reading from the gateway.

    Accepts the full-format telemetry payload. Duplicates (same node_id
    and timestamp) are silently ignored.

    NOTE: ESP32 firmware sends millis()/1000 as timestamp (seconds since boot,
    NOT real Unix time). We override with the server's actual UTC time on
    receipt so storage and PWA display work correctly without ESP32-side NTP.
    """

    # ✅ Override ESP32 timestamp (Pydantic-safe)
    server_ts = int(datetime.now(timezone.utc).timestamp())
    reading = reading.model_copy(update={"timestamp": server_ts})

    repo = request.app.state.repository

    try:
        inserted = repo.ingest_reading(reading)

        if inserted:
            logger.info(
                f"Ingested: node={reading.node_id}, "
                f"ts={reading.timestamp}, "
                f"sensors={len(reading.readings)}"
            )
            return IngestResponse(
                status="ok",
                message="Reading ingested successfully",
                ingested=1,
                duplicates=0,
            )
        else:
            logger.debug(
                f"Duplicate: node={reading.node_id}, ts={reading.timestamp}"
            )
            return IngestResponse(
                status="ok",
                message="Duplicate reading ignored",
                ingested=0,
                duplicates=1,
            )

    except Exception as e:
        logger.error(f"Ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/batch", response_model=IngestResponse)
async def ingest_batch(batch: BatchIngestRequest, request: Request):
    """
    Ingest a batch of telemetry readings.

    Each reading's timestamp is overridden with server time on receipt,
    spaced 1 second apart to preserve ordering within the batch.
    """

    repo = request.app.state.repository

    try:
        # ✅ Override timestamps for batch (ordered spacing)
        server_ts = int(datetime.now(timezone.utc).timestamp())

        new_readings = [
            r.model_copy(
                update={
                    "timestamp": server_ts - (len(batch.readings) - i - 1)
                }
            )
            for i, r in enumerate(batch.readings)
        ]

        batch = batch.model_copy(update={"readings": new_readings})

        ingested, duplicates = repo.ingest_batch(batch.readings)

        logger.info(
            f"Batch ingest: {ingested} new, {duplicates} duplicates "
            f"(total: {len(batch.readings)})"
        )

        return IngestResponse(
            status="ok",
            message=f"Batch processed: {ingested} ingested, {duplicates} duplicates",
            ingested=ingested,
            duplicates=duplicates,
        )

    except Exception as e:
        logger.error(f"Batch ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
