"""
Readings query API endpoints.
"""

from typing import Optional, List
from fastapi import APIRouter, Request, Query
from ..models.schemas import ReadingResponse, LatestReadingsResponse

router = APIRouter(tags=["Readings"])


@router.get("/latest-readings", response_model=LatestReadingsResponse)
async def get_latest_readings(request: Request):
    """
    Get the most recent telemetry reading for each registered node.

    Useful for dashboard overview displays showing current field status.
    """
    repo = request.app.state.repository
    readings = repo.get_latest_readings()

    return LatestReadingsResponse(
        nodes=[ReadingResponse(**r) for r in readings]
    )


@router.get("/readings", response_model=List[ReadingResponse])
async def query_readings(
    request: Request,
    node_id: Optional[str] = Query(None, description="Filter by node ID"),
    start: Optional[int] = Query(None, description="Start timestamp (Unix)"),
    end: Optional[int] = Query(None, description="End timestamp (Unix)"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
):
    """
    Query historical telemetry readings with optional filters.

    Supports filtering by node ID, time range, and result limit.
    Results are ordered by timestamp descending (newest first).
    """
    repo = request.app.state.repository
    readings = repo.get_readings(
        node_id=node_id,
        start_time=start,
        end_time=end,
        limit=limit,
    )

    return [ReadingResponse(**r) for r in readings]
