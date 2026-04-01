"""
Telemetry ingestion API endpoints.
"""

import logging
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
    """
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

    Accepts multiple readings in a single request for efficiency.
    Each reading is processed independently — partial success is possible.
    """
    repo = request.app.state.repository

    try:
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
