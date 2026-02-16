"""FastAPI application factory for the Breslow QuoteApp API."""

from __future__ import annotations

import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .routers import conversations, health, messages, messages_v2, messages_v3


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    await init_db()
    yield


app = FastAPI(
    title="Breslow QuoteApp API",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(conversations.router)
app.include_router(messages.router)
app.include_router(messages_v2.router)
app.include_router(messages_v3.router)

# ── Admin Panel (static files) ─────────────────────────────────────

_ADMIN_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "admin"

if _ADMIN_DIR.is_dir():
    @app.get("/admin", include_in_schema=False)
    async def admin_index():
        """Serve the A.S.C.E.N.D. admin panel."""
        return FileResponse(_ADMIN_DIR / "index.html")

    app.mount("/admin", StaticFiles(directory=str(_ADMIN_DIR), html=True), name="admin")


# ── Global error handler ────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Return errors in the { error: { message } } format the client expects."""
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": str(exc)}},
    )
