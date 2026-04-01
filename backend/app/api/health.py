"""
Health check API endpoint.
"""

from fastapi import APIRouter, Request
from ..models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check(request: Request):
    """
    Check backend health status.

    Returns the service version, total readings, and node count.
    """
    repo = request.app.state.repository

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        total_readings=repo.get_total_readings(),
        total_nodes=repo.get_total_nodes(),
    )
