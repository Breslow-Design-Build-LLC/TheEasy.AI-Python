"""Bearer token authentication dependency."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

_scheme = HTTPBearer()


async def require_bearer_token(
    credentials: HTTPAuthorizationCredentials = Depends(_scheme),
) -> str:
    """Validate Bearer token and return it."""
    if credentials.credentials != settings.bearer_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "unauthorized", "message": "Invalid or missing bearer token"}},
        )
    return credentials.credentials
