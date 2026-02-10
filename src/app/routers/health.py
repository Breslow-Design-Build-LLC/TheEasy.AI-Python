"""Health check endpoint (no auth required)."""

from fastapi import APIRouter

from ..models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok")
