"""
auth.py — Optional bearer-token authentication.

Behavior:
- If BACKEND_API_TOKEN env var is unset or empty → all requests allowed (open mode).
  This matches the original behavior, useful for development.
- If BACKEND_API_TOKEN is set → all non-localhost requests require:
    Authorization: Bearer <token>
  matching the env var.

Localhost requests (127.0.0.1, ::1, localhost) are always allowed without a token,
so the AI agent running on the same Pi continues to work without changes.
"""

import os
from fastapi import HTTPException, Request, status


# Hosts considered internal — always allowed without a token.
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def verify_token(request: Request) -> None:
    """
    FastAPI dependency for bearer-token auth.

    Returns None on success. Raises HTTPException(401) on failure.
    """
    expected = os.getenv("BACKEND_API_TOKEN", "").strip()

    # Open mode — auth disabled
    if not expected:
        return

    # Whitelist: requests from the Pi itself (the AI agent calling localhost)
    client_host = request.client.host if request.client else ""
    if client_host in LOCAL_HOSTS:
        return

    # Authorization required for all other clients
    auth_header = request.headers.get("authorization")

    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = auth_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    presented = parts[1].strip()
    if presented != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return
