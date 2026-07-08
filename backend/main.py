"""
HobbyFi Copilot — FastAPI Backend
===================================

Entry point.  Mounts:
  • POST /api/chat          — Agent chat endpoint
  • GET  /api/dashboard     — KPI stats for the dashboard
  • GET  /api/approvals     — Pending approval queue
  • POST /api/approvals/:id/approve
  • POST /api/approvals/:id/reject
  • GET  /api/audit         — Audit log viewer
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from database import init_db, get_db, fetch_one, fetch_all
from seed_data import seed_if_empty
from agent.engine import AgentEngine
from agent.approval import ApprovalManager
from agent.audit import AuditLogger


# ─── Lifespan ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables + seed mock data."""
    await init_db()
    await seed_if_empty()
    print("[OK] HobbyFi Copilot backend ready")
    yield


app = FastAPI(
    title="HobbyFi Copilot API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Models ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ApprovalAction(BaseModel):
    vendor_id: str = "V001"


# ═══════════════════════════════════════════════════════════════════════
#  CHAT ENDPOINT
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Send a message to the HobbyFi Copilot and get a response."""
    engine = AgentEngine()
    result = await engine.chat(
        user_message=req.message,
        conversation_id=req.conversation_id,
    )
    return result


# ═══════════════════════════════════════════════════════════════════════
#  DASHBOARD — KPI Stats
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/dashboard")
async def dashboard():
    """Return aggregate KPIs for the vendor dashboard."""
    db = await get_db()
    try:
        # Today's revenue
        from datetime import date
        today = date.today().isoformat()
        rev = await fetch_one(
            db,
            "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE status='paid' AND date(date) = date(?)",
            (today,),
        )

        # Active users
        users = await fetch_one(db, "SELECT COUNT(*) AS count FROM users WHERE status='active'")

        # Trial users
        trials = await fetch_one(
            db,
            "SELECT COUNT(*) AS count FROM memberships WHERE type='trial' AND status='active'"
        )

        # Total bookings (last 30 days)
        from datetime import timedelta
        thirty_days_ago = (date.today() - timedelta(days=30)).isoformat()
        bookings = await fetch_one(
            db,
            "SELECT COUNT(*) AS count FROM bookings WHERE date >= ? AND status != 'cancelled'",
            (thirty_days_ago,),
        )

        # Revenue trend (last 7 days)
        trend = await fetch_all(
            db,
            """SELECT date(date) AS day, COALESCE(SUM(amount), 0) AS revenue
               FROM payments
               WHERE status='paid' AND date(date) >= date(?, '-6 days')
               GROUP BY date(date)
               ORDER BY day""",
            (today,),
        )

        # Recent activity
        recent_activity = await fetch_all(
            db,
            """SELECT al.action_type, al.tool_name, al.timestamp,
                      al.params, al.result
               FROM audit_logs al
               ORDER BY al.timestamp DESC
               LIMIT 10""",
        )

        # Membership breakdown
        membership_breakdown = await fetch_all(
            db,
            """SELECT type, COUNT(*) AS count
               FROM memberships
               GROUP BY type"""
        )

        return {
            "today_revenue": rev["total"] if rev else 0,
            "active_users": users["count"] if users else 0,
            "trial_users": trials["count"] if trials else 0,
            "total_bookings": bookings["count"] if bookings else 0,
            "revenue_trend": trend,
            "recent_activity": recent_activity,
            "membership_breakdown": membership_breakdown,
        }
    finally:
        await db.close()


# ═══════════════════════════════════════════════════════════════════════
#  APPROVALS
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/approvals")
async def list_approvals(status: str | None = None):
    """List pending or all approval actions."""
    if status == "pending":
        return await ApprovalManager.get_pending()
    return await ApprovalManager.get_all_actions()


@app.post("/api/approvals/{action_id}/approve")
async def approve_action(action_id: str, body: ApprovalAction | None = None):
    """Approve a pending write action."""
    vendor_id = body.vendor_id if body else "V001"
    return await ApprovalManager.approve(action_id, vendor_id)


@app.post("/api/approvals/{action_id}/reject")
async def reject_action(action_id: str, body: ApprovalAction | None = None):
    """Reject a pending write action."""
    vendor_id = body.vendor_id if body else "V001"
    return await ApprovalManager.reject(action_id, vendor_id)


# ═══════════════════════════════════════════════════════════════════════
#  AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/audit")
async def audit_logs(
    action_type: str | None = Query(None, description="Filter: read, write, approval"),
    limit: int = Query(50, ge=1, le=200),
):
    """Retrieve the audit trail."""
    return await AuditLogger.get_logs(limit=limit, action_type=action_type)


# ═══════════════════════════════════════════════════════════════════════
#  Run
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
