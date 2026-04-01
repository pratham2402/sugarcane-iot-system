"""
Validation utilities for the gateway.

Provides reusable validation functions for telemetry data.
"""


def is_valid_node_id(node_id: str) -> bool:
    """Check if a node_id looks valid."""
    if not node_id or not isinstance(node_id, str):
        return False
    if len(node_id) > 50:
        return False
    return True


def is_valid_timestamp(timestamp) -> bool:
    """Check if a timestamp is reasonable (within last year to future year)."""
    if not isinstance(timestamp, (int, float)):
        return False
    # Reasonable range: 2024-01-01 to 2030-01-01
    return 1704067200 <= timestamp <= 1893456000


def is_in_range(value: float, min_val: float, max_val: float) -> bool:
    """Check if a value is within a range."""
    return min_val <= value <= max_val
