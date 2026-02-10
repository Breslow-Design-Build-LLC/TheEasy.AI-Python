"""SQLite database helpers using aiosqlite."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiosqlite

from .config import settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    client_id   INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    config_json TEXT DEFAULT '{}',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role            TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    response_json   TEXT DEFAULT NULL,
    metadata_json   TEXT DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, created_at);
"""


async def init_db() -> None:
    """Create tables if they don't exist."""
    db_path = settings.database_url
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()


@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Yield an aiosqlite connection with row_factory enabled."""
    db = await aiosqlite.connect(settings.database_url)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()
