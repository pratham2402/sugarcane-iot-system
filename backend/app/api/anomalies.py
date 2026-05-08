"""
Anomaly detection API endpoint.
Wraps the preprocessing.detect_anomalies() function so the agent can
query it over HTTP without reaching into backend internals.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..preprocessing import load_readings, detect_anomalies

router = APIRouter()


class AnomalyDetail(BaseModel):
    timestamp: int
    reasons: str
    soil_moisture: Optional[float] = None
    soil_temperature: Optional[float] = None
    air_temperature: Optional[float] = None
    humidity: Optional[float] = None


class AnomalyResponse(BaseModel):
    node_id: str
    days_checked: int
    rows_analyzed: int
    anomalies_found: int
    anomalies: List[AnomalyDetail]
    summary: str


@router.get("/check-anomalies", response_model=AnomalyResponse, tags=["ML"])
async def check_anomalies(
    node_id: str = Query("node-01", description="Sensor node to check"),
    days: int = Query(7, ge=1, le=90, description="How many days of history to analyze"),
):
    """
    Check recent sensor data for anomalies using statistical methods
    (range checks, rolling z-score, stuck values).
    Returns a list of flagged readings with reasons.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    try:
        df = load_readings(
            node_id=node_id,
            start=start,
            end=end,
            include_invalid=True,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load readings: {str(e)}",
        )

    if df is None or df.empty:
        return AnomalyResponse(
            node_id=node_id,
            days_checked=days,
            rows_analyzed=0,
            anomalies_found=0,
            anomalies=[],
            summary="No data available for the specified period.",
        )

    rows_analyzed = len(df)

    try:
        df = detect_anomalies(df)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Anomaly detection failed: {str(e)}",
        )

    anomaly_rows = (
        df[df["is_anomaly"]]
        if "is_anomaly" in df.columns
        else df.iloc[0:0]
    )

    anomalies: List[AnomalyDetail] = []

    for _, row in anomaly_rows.iterrows():

        def _as_float(col):
            val = row.get(col)
            try:
                return float(val) if val is not None else None
            except (TypeError, ValueError):
                return None

        anomalies.append(
            AnomalyDetail(
                timestamp=int(row.get("timestamp", 0)),
                reasons=str(row.get("anomaly_reasons", "")),
                soil_moisture=_as_float("soil_moisture"),
                soil_temperature=_as_float("soil_temperature"),
                air_temperature=_as_float("air_temperature"),
                humidity=_as_float("humidity"),
            )
        )

    summary = (
        f"Checked {rows_analyzed} readings over last {days} days. "
        f"Found {len(anomalies)} anomalies."
    )

    return AnomalyResponse(
        node_id=node_id,
        days_checked=days,
        rows_analyzed=rows_analyzed,
        anomalies_found=len(anomalies),
        anomalies=anomalies,
        summary=summary,
    )
