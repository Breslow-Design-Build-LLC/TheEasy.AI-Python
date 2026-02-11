"""Conversation and message CRUD backed by aiosqlite."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite

from ..database import get_db_connection


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ── Conversations ───────────────────────────────────────────────────


async def create_conversation(
    client_id: int,
    user_id: int,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    conv_id = _new_id("conv")
    now = datetime.now(timezone.utc).isoformat()
    async with get_db_connection() as db:
        await db.execute(
            """
            INSERT INTO conversations (id, client_id, user_id, status, config_json, created_at, updated_at)
            VALUES (?, ?, ?, 'active', ?, ?, ?)
            """,
            (conv_id, client_id, user_id, json.dumps(config or {}), now, now),
        )
        await db.commit()
    return {"conversation_id": conv_id, "status": "active", "created_at": now}


async def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def cancel_conversation(conversation_id: str) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc).isoformat()
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        await db.execute(
            "UPDATE conversations SET status = 'cancelled', updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        await db.commit()
    return {"conversation_id": conversation_id, "status": "cancelled"}


# ── Messages ────────────────────────────────────────────────────────


async def add_message(
    conversation_id: str,
    role: str,
    content: str,
    response_json: dict[str, Any] | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    msg_id = _new_id("msg")
    now = datetime.now(timezone.utc).isoformat()
    async with get_db_connection() as db:
        await db.execute(
            """
            INSERT INTO messages (id, conversation_id, role, content, response_json, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg_id,
                conversation_id,
                role,
                content,
                json.dumps(response_json) if response_json else None,
                json.dumps(metadata_json or {}),
                now,
            ),
        )
        await db.commit()
    return {
        "id": msg_id,
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "response": response_json,
        "metadata": metadata_json or {},
        "created_at": now,
    }


async def get_messages(
    conversation_id: str,
    after: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    async with get_db_connection() as db:
        if after:
            cursor = await db.execute(
                """
                SELECT * FROM messages
                WHERE conversation_id = ?
                  AND created_at > (SELECT created_at FROM messages WHERE id = ?)
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (conversation_id, after, limit),
            )
        else:
            cursor = await db.execute(
                """
                SELECT * FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (conversation_id, limit),
            )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["response"] = json.loads(d.pop("response_json")) if d.get("response_json") else None
            d["metadata"] = json.loads(d.pop("metadata_json")) if d.get("metadata_json") else None
            results.append(d)
        return results


async def get_session_state(conversation_id: str) -> dict[str, Any]:
    """Read session state from the conversation's config_json column."""
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT config_json FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return {}
        raw = row["config_json"]
        if not raw:
            return {}
        return json.loads(raw)


async def update_session_state(
    conversation_id: str, state_dict: dict[str, Any]
) -> None:
    """Write session state back to the conversation's config_json column."""
    now = datetime.now(timezone.utc).isoformat()
    async with get_db_connection() as db:
        await db.execute(
            "UPDATE conversations SET config_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(state_dict), now, conversation_id),
        )
        await db.commit()


async def get_conversation_history(conversation_id: str) -> list[dict[str, str]]:
    """Return messages in OpenAI chat format [{role, content}, ...]."""
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        )
        rows = await cursor.fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]
