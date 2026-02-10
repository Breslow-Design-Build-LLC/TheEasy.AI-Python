"""FastAPI dependency-injection helpers.

Re-exports are gathered here so routers can import from a single module
if needed. Currently the app is small enough that services are imported
directly, but this module exists as a convenient extension point.
"""

from __future__ import annotations

from .auth import require_bearer_token
from .database import get_db_connection

__all__ = ["require_bearer_token", "get_db_connection"]
