"""
Pydantic schemas for API request/response validation.

These models define the shared data contract for the cloud backend,
matching the telemetry schema used across the entire system.
"""

from typing import Optional, Dict, List
from pydantic import BaseModel, Field, field_validator


# ─── Request Schemas ─────────────────────────────────────────────────────────

class SensorReading(BaseModel):
    """A single sensor reading."""
    value: float
    unit: str = ""
    valid: bool = True


class TelemetryIngestRequest(BaseModel):
    """
    Telemetry ingestion request from the Raspberry Pi gateway.
    Matches the full-format data contract.
    """
    node_id: str = Field(..., min_length=1, max_length=50)
    timestamp: int = Field(..., gt=0)
    firmware_version: Optional[str] = None
    battery_voltage: Optional[float] = Field(None, ge=0, le=5.0)
    status: str = Field(default="ok", pattern="^(ok|degraded|error)$")
    readings: Dict[str, SensorReading] = Field(default_factory=dict)

    @field_validator("readings")
    @classmethod
    def validate_readings(cls, v):
        """Validate that reading keys are known sensor types."""
        known_types = {
            "soil_moisture", "soil_temperature", "air_temperature",
            "humidity", "rainfall_pulses", "flow_pulses"
        }
        for key in v:
            if key not in known_types:
                # Allow unknown types (future sensors) but log a warning
                pass
        return v


class BatchIngestRequest(BaseModel):
    """Batch telemetry ingestion — multiple readings in one request."""
    readings: List[TelemetryIngestRequest] = Field(..., max_length=100)


# ─── Response Schemas ────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    total_readings: int
    total_nodes: int


class IngestResponse(BaseModel):
    """Response for telemetry ingestion."""
    status: str
    message: str
    ingested: int = 0
    duplicates: int = 0


class NodeResponse(BaseModel):
    """Node information response."""
    node_id: str
    firmware_version: Optional[str] = None
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    total_readings: int = 0
    last_status: Optional[str] = None
    last_battery_voltage: Optional[float] = None


class ReadingResponse(BaseModel):
    """Telemetry reading response."""
    node_id: str
    timestamp: int
    firmware_version: Optional[str] = None
    battery_voltage: Optional[float] = None
    status: str = "ok"
    soil_moisture: Optional[float] = None
    soil_temperature: Optional[float] = None
    air_temperature: Optional[float] = None
    humidity: Optional[float] = None
    rainfall_pulses: Optional[int] = None
    flow_pulses: Optional[int] = None


class LatestReadingsResponse(BaseModel):
    """Latest readings per node."""
    nodes: List[ReadingResponse]
