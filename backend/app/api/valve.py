"""
valve.py — Simulated irrigation valve actuation endpoint.

For the prototype, "actuating" the valve means logging the action to SQLite.
Real deployment would trigger a relay or solenoid here.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from ..auth import verify_token


router = APIRouter()

DB_PATH = Path(__file__).parent.parent.parent / "data" / "telemetry.db"


# -------------------- SCHEMAS --------------------

class ValveActionRequest(BaseModel):
    node_id: str = Field(default="node-01", description="Which node's valve")
    action: str = Field(..., description="open | close")
    duration_min: Optional[int] = Field(None, description="How long to keep open (minutes)")
    water_mm: Optional[float] = Field(None, description="Target irrigation amount (mm)")
    requested_by: str = Field(default="agent", description="agent | user | scheduler")
    reasoning: Optional[str] = Field(None, description="Why this action was triggered")


class ValveActionResponse(BaseModel):
    status: str
    action_id: int
    node_id: str
    action: str
    duration_min: Optional[int]
    water_mm: Optional[float]
    timestamp: int
    message: str


# -------------------- ENDPOINTS --------------------

@router.post("/actuate/valve", response_model=ValveActionResponse)
def actuate_valve(req: ValveActionRequest):
    """
    Trigger a simulated valve action and log it.
    Returns the action_id for downstream tracking.
    """
    if req.action not in ("open", "close"):
        raise HTTPException(
            status_code=400,
            detail=f"action must be 'open' or 'close', got '{req.action}'",
        )

    timestamp = int(datetime.now(timezone.utc).timestamp())

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO valve_actions
            (node_id, action, duration_min, water_mm, requested_by, reasoning, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            req.node_id,
            req.action,
            req.duration_min,
            req.water_mm,
            req.requested_by,
            req.reasoning,
            timestamp,
        ),
    )
    action_id = cursor.lastrowid
    conn.commit()
    conn.close()

    msg = f"Valve {req.action} logged for {req.node_id}"
    if req.action == "open" and req.duration_min:
        msg += f" (duration: {req.duration_min} min, target: {req.water_mm or 'n/a'} mm)"

    return ValveActionResponse(
        status="ok",
        action_id=action_id,
        node_id=req.node_id,
        action=req.action,
        duration_min=req.duration_min,
        water_mm=req.water_mm,
        timestamp=timestamp,
        message=msg,
    )


@router.get("/valve-history")
def get_valve_history(node_id: str = "node-01", limit: int = 20):
    """
    Return recent valve actions for a node.
    Used by the dashboard and agent to show recent irrigation events.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, node_id, action, duration_min, water_mm,
               requested_by, reasoning, timestamp, created_at
        FROM valve_actions
        WHERE node_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (node_id, limit),
    )
    rows = cursor.fetchall()
    conn.close()

    actions = []
    for row in rows:
        actions.append(
            {
                "id": row[0],
                "node_id": row[1],
                "action": row[2],
                "duration_min": row[3],
                "water_mm": row[4],
                "requested_by": row[5],
                "reasoning": row[6],
                "timestamp": row[7],
                "created_at": row[8],
            }
        )

    return {
        "node_id": node_id,
        "count": len(actions),
        "actions": actions,
    }


@router.delete("/valve-history", tags=["Valve"])
async def delete_valve_history(
    node_id: str = Query(..., description="Node ID to clear history for"),
    confirm: bool = Query(False, description="Must be True to actually delete"),
    _auth: None = Depends(verify_token),
):
    """
    Delete all valve actions for a given node. Requires ?confirm=true.
    Used by the PWA's 'Clear History' button.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Add ?confirm=true to actually delete history",
        )

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM valve_actions WHERE node_id = ?", (node_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "deleted": deleted,
        "node_id": node_id,
        "message": f"Deleted {deleted} valve action(s) for {node_id}",
    }
