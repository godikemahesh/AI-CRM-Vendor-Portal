"""
Audit Logger — Immutable record of every agent action
======================================================

Every tool call (read or write) is logged with:
  • Timestamp, tool name, parameters, result
  • Vendor who triggered it
  • Affected user (if applicable)
  • Approval info for write actions
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from database import get_db, fetch_all


class AuditLogger:
    """Append-only audit trail stored in ``audit_logs`` table."""

    @staticmethod
    async def log(
        action_type: str,
        tool_name: str,
        params: dict | None = None,
        result: dict | None = None,
        vendor_id: str | None = None,
        affected_user_id: str | None = None,
        approved_by: str | None = None,
    ) -> str:
        """Create an audit entry.  Returns the log id."""
        log_id = str(uuid.uuid4())
        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO audit_logs
                   (id, action_type, tool_name, params, result,
                    vendor_id, affected_user_id, approved_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    log_id,
                    action_type,
                    tool_name,
                    json.dumps(params) if params else None,
                    json.dumps(result) if result else None,
                    vendor_id,
                    affected_user_id,
                    approved_by,
                ),
            )
            await db.commit()
            return log_id
        finally:
            await db.close()

    @staticmethod
    async def get_logs(
        limit: int = 50,
        action_type: str | None = None,
    ) -> list[dict]:
        """Retrieve audit logs, most-recent first."""
        db = await get_db()
        try:
            if action_type:
                rows = await fetch_all(
                    db,
                    """SELECT * FROM audit_logs
                       WHERE action_type = ?
                       ORDER BY timestamp DESC LIMIT ?""",
                    (action_type, limit),
                )
            else:
                rows = await fetch_all(
                    db,
                    "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )
            # Parse JSON blobs for the frontend
            for r in rows:
                for key in ("params", "result"):
                    if r.get(key):
                        try:
                            r[key] = json.loads(r[key])
                        except (json.JSONDecodeError, TypeError):
                            pass
            return rows
        finally:
            await db.close()
