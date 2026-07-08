"""
Approval Manager — Human-in-the-Loop for Write Operations
==========================================================

Every *write* tool call follows this flow:

    1. Agent proposes a change → ``create_pending_action()``
    2. Frontend displays before/after diff to the vendor
    3. Vendor clicks Approve or Reject
    4. On approval → ``approve()`` executes the actual DB mutation
    5. Result is logged to the audit trail
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from database import get_db, fetch_all, fetch_one
from agent.audit import AuditLogger


class ApprovalManager:
    """Queue and process write-operation approvals."""

    @staticmethod
    async def create_pending_action(
        tool_name: str,
        params: dict,
        description: str,
        before_state: dict | None = None,
        after_state: dict | None = None,
        conversation_id: str | None = None,
    ) -> dict:
        """Queue a write action for vendor review.  Returns the pending action record."""
        action_id = str(uuid.uuid4())
        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO pending_actions
                   (id, conversation_id, tool_name, params, description,
                    before_state, after_state)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    action_id,
                    conversation_id,
                    tool_name,
                    json.dumps(params),
                    description,
                    json.dumps(before_state) if before_state else None,
                    json.dumps(after_state) if after_state else None,
                ),
            )
            await db.commit()
            return {
                "id": action_id,
                "tool_name": tool_name,
                "description": description,
                "before_state": before_state,
                "after_state": after_state,
                "status": "pending",
            }
        finally:
            await db.close()

    @staticmethod
    async def get_pending(limit: int = 50) -> list[dict]:
        """List actions waiting for approval."""
        db = await get_db()
        try:
            rows = await fetch_all(
                db,
                """SELECT * FROM pending_actions
                   WHERE status = 'pending'
                   ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            )
            for r in rows:
                for key in ("params", "before_state", "after_state"):
                    if r.get(key):
                        try:
                            r[key] = json.loads(r[key])
                        except (json.JSONDecodeError, TypeError):
                            pass
            return rows
        finally:
            await db.close()

    @staticmethod
    async def get_all_actions(limit: int = 50) -> list[dict]:
        """List all actions (pending + resolved)."""
        db = await get_db()
        try:
            rows = await fetch_all(
                db,
                "SELECT * FROM pending_actions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            for r in rows:
                for key in ("params", "before_state", "after_state"):
                    if r.get(key):
                        try:
                            r[key] = json.loads(r[key])
                        except (json.JSONDecodeError, TypeError):
                            pass
            return rows
        finally:
            await db.close()

    @staticmethod
    async def approve(action_id: str, vendor_id: str = "V001") -> dict:
        """Execute the approved write action."""
        db = await get_db()
        try:
            row = await fetch_one(
                db,
                "SELECT * FROM pending_actions WHERE id = ?",
                (action_id,),
            )
            if not row:
                return {"error": "Action not found"}
            if row["status"] != "pending":
                return {"error": f"Action already {row['status']}"}

            params = json.loads(row["params"]) if isinstance(row["params"], str) else row["params"]
            tool_name = row["tool_name"]

            # Execute the actual write
            from agent.registry import registry

            tool = registry.get(tool_name)
            if tool is None:
                return {"error": f"Tool '{tool_name}' not found in registry"}

            result = await tool.handler(params, db)

            # Mark as approved
            now = datetime.utcnow().isoformat()
            await db.execute(
                """UPDATE pending_actions
                   SET status = 'approved', resolved_at = ?, resolved_by = ?
                   WHERE id = ?""",
                (now, vendor_id, action_id),
            )
            await db.commit()

            # Audit log
            await AuditLogger.log(
                action_type="write",
                tool_name=tool_name,
                params=params,
                result=result,
                vendor_id=vendor_id,
                approved_by=vendor_id,
            )

            return {"success": True, "result": result}
        finally:
            await db.close()

    @staticmethod
    async def reject(action_id: str, vendor_id: str = "V001") -> dict:
        """Reject a pending action."""
        db = await get_db()
        try:
            now = datetime.utcnow().isoformat()
            await db.execute(
                """UPDATE pending_actions
                   SET status = 'rejected', resolved_at = ?, resolved_by = ?
                   WHERE id = ?""",
                (now, vendor_id, action_id),
            )
            await db.commit()

            await AuditLogger.log(
                action_type="approval",
                tool_name="reject_action",
                params={"action_id": action_id},
                vendor_id=vendor_id,
            )

            return {"success": True}
        finally:
            await db.close()
