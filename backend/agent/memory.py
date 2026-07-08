"""
Conversation Memory — Sliding-Window + Entity Tracking
======================================================

Mirrors Mastra's memory primitives:
  • Full conversation history stored in SQLite
  • Sliding window (last N messages) sent to the LLM context
  • Lightweight entity extraction to track mentioned users/items

Design choice: we keep the *entire* history in the DB but only send a
configurable window to the LLM to stay within token limits.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from database import get_db, fetch_all, fetch_one


WINDOW_SIZE = 20  # messages sent to LLM per turn


class ConversationMemory:
    """Manage conversation history for a single vendor session."""

    def __init__(self, vendor_id: str, conversation_id: str | None = None):
        self.vendor_id = vendor_id
        self.conversation_id = conversation_id

    # -- lifecycle ------------------------------------------------------

    async def get_or_create_conversation(self) -> str:
        """Return existing conversation id or create a new one."""
        db = await get_db()
        try:
            if self.conversation_id:
                row = await fetch_one(
                    db,
                    "SELECT id FROM conversations WHERE id = ?",
                    (self.conversation_id,),
                )
                if row:
                    return self.conversation_id

            self.conversation_id = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO conversations (id, vendor_id) VALUES (?, ?)",
                (self.conversation_id, self.vendor_id),
            )
            await db.commit()
            return self.conversation_id
        finally:
            await db.close()

    # -- read -----------------------------------------------------------

    async def get_history(self, limit: int = WINDOW_SIZE) -> list[dict]:
        """Return the last *limit* messages for this conversation."""
        db = await get_db()
        try:
            rows = await fetch_all(
                db,
                """SELECT role, content, tool_calls, timestamp
                   FROM messages
                   WHERE conversation_id = ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (self.conversation_id, limit),
            )
            # Reverse so oldest-first (chronological)
            rows.reverse()
            return rows
        finally:
            await db.close()

    async def get_message_count(self) -> int:
        db = await get_db()
        try:
            row = await fetch_one(
                db,
                "SELECT COUNT(*) as cnt FROM messages WHERE conversation_id = ?",
                (self.conversation_id,),
            )
            return row["cnt"] if row else 0
        finally:
            await db.close()

    # -- write ----------------------------------------------------------

    async def add_message(
        self,
        role: str,
        content: str,
        tool_calls: dict | None = None,
    ) -> str:
        """Persist a message and return its id."""
        msg_id = str(uuid.uuid4())
        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO messages (id, conversation_id, role, content, tool_calls)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    msg_id,
                    self.conversation_id,
                    role,
                    content,
                    json.dumps(tool_calls) if tool_calls else None,
                ),
            )
            await db.commit()
            return msg_id
        finally:
            await db.close()

    # -- context builder ------------------------------------------------

    async def build_context_messages(self) -> list[dict]:
        """Build the ``messages`` array for the LLM call.

        Returns a list of ``{"role": ..., "content": ...}`` dicts ready
        for the Cerebras chat-completion API.
        """
        history = await self.get_history(limit=WINDOW_SIZE)
        messages = []
        for msg in history:
            entry = {"role": msg["role"], "content": msg["content"]}
            messages.append(entry)
        return messages
