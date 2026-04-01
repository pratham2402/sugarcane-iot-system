"""
Node management API endpoints.
"""

from typing import List
from fastapi import APIRouter, Request, HTTPException
from ..models.schemas import NodeResponse

router = APIRouter(prefix="/nodes", tags=["Nodes"])


@router.get("", response_model=List[NodeResponse])
async def list_nodes(request: Request):
    """
    List all registered field nodes.

    Nodes are automatically registered when their first telemetry
    reading is ingested.
    """
    repo = request.app.state.repository
    nodes = repo.get_nodes()

    return [NodeResponse(**node) for node in nodes]


@router.get("/{node_id}", response_model=NodeResponse)
async def get_node(node_id: str, request: Request):
    """
    Get details for a specific field node.
    """
    repo = request.app.state.repository
    node = repo.get_node(node_id)

    if node is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

    return NodeResponse(**node)
