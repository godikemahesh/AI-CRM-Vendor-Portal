"""
CRM Tools — Read & Write Operations for HobbyFi Copilot
========================================================

Every tool self-registers through the ``@registry.tool()`` decorator.

Read Tools  → execute immediately, result returned to agent
Write Tools → create a pending_action for vendor approval
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from agent.registry import registry
from database import fetch_all, fetch_one


# ═══════════════════════════════════════════════════════════════════════
#  READ TOOLS — execute immediately
# ═══════════════════════════════════════════════════════════════════════


@registry.tool(
    name="get_today_revenue",
    description=(
        "Get the total revenue (sum of paid payments) for today or a "
        "specified date/range. Accepts optional 'date' (YYYY-MM-DD) or "
        "'start_date' and 'end_date'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Single date (YYYY-MM-DD). Defaults to today.",
            },
            "start_date": {
                "type": "string",
                "description": "Range start (YYYY-MM-DD).",
            },
            "end_date": {
                "type": "string",
                "description": "Range end (YYYY-MM-DD).",
            },
        },
    },
    access_level="read",
    category="revenue",
    examples=["What is today's revenue?", "Revenue for last week"],
)
async def get_today_revenue(args: dict, db) -> dict:
    target_date = args.get("date", date.today().isoformat())
    start = args.get("start_date", target_date)
    end = args.get("end_date", target_date)

    row = await fetch_one(
        db,
        """SELECT COALESCE(SUM(amount), 0) AS total,
                  COUNT(*) AS transaction_count
           FROM payments
           WHERE status = 'paid'
             AND date(date) BETWEEN date(?) AND date(?)""",
        (start, end),
    )
    return {
        "total_revenue": row["total"] if row else 0,
        "transaction_count": row["transaction_count"] if row else 0,
        "period": f"{start} to {end}" if start != end else start,
    }


@registry.tool(
    name="get_user_list",
    description=(
        "List users, optionally filtered by activity name, membership type, "
        "or status. Returns user name, email, phone, status."
    ),
    parameters={
        "type": "object",
        "properties": {
            "activity": {
                "type": "string",
                "description": "Filter by activity name (e.g. 'Badminton').",
            },
            "membership_type": {
                "type": "string",
                "enum": ["trial", "monthly", "quarterly", "annual"],
                "description": "Filter by membership type.",
            },
            "status": {
                "type": "string",
                "enum": ["active", "inactive"],
                "description": "Filter by user status.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results (default 20).",
            },
        },
    },
    access_level="read",
    category="users",
    examples=["List all active users", "Show badminton users"],
)
async def get_user_list(args: dict, db) -> dict:
    conditions = []
    params = []

    if args.get("activity"):
        conditions.append(
            """u.id IN (
                SELECT m.user_id FROM memberships m
                JOIN activities a ON m.activity_id = a.id
                WHERE LOWER(a.name) = LOWER(?)
            )"""
        )
        params.append(args["activity"])

    if args.get("membership_type"):
        conditions.append(
            """u.id IN (
                SELECT m.user_id FROM memberships m WHERE m.type = ?
            )"""
        )
        params.append(args["membership_type"])

    if args.get("status"):
        conditions.append("u.status = ?")
        params.append(args["status"])

    where = " AND ".join(conditions) if conditions else "1=1"
    limit = args.get("limit", 20)
    params.append(limit)

    users = await fetch_all(
        db,
        f"""SELECT u.id, u.name, u.email, u.phone, u.city,
                   u.joined_date, u.status
            FROM users u
            WHERE {where}
            ORDER BY u.name
            LIMIT ?""",
        tuple(params),
    )
    return {"users": users, "count": len(users)}


@registry.tool(
    name="get_user_details",
    description=(
        "Get full details for a single user: profile, memberships, "
        "recent bookings, and payment history."
    ),
    parameters={
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "The user ID."},
            "user_name": {
                "type": "string",
                "description": "Partial or full user name to search.",
            },
        },
    },
    access_level="read",
    category="users",
    examples=["Show me Rahul's details", "User info for U005"],
)
async def get_user_details(args: dict, db) -> dict:
    if args.get("user_id"):
        user = await fetch_one(db, "SELECT * FROM users WHERE id = ?", (args["user_id"],))
    elif args.get("user_name"):
        user = await fetch_one(
            db,
            "SELECT * FROM users WHERE LOWER(name) LIKE LOWER(?)",
            (f"%{args['user_name']}%",),
        )
    else:
        return {"error": "Provide user_id or user_name"}

    if not user:
        return {"error": "User not found"}

    memberships = await fetch_all(
        db,
        """SELECT m.*, a.name AS activity_name
           FROM memberships m
           JOIN activities a ON m.activity_id = a.id
           WHERE m.user_id = ?
           ORDER BY m.start_date DESC""",
        (user["id"],),
    )

    bookings = await fetch_all(
        db,
        """SELECT b.*, a.name AS activity_name
           FROM bookings b
           JOIN activities a ON b.activity_id = a.id
           WHERE b.user_id = ?
           ORDER BY b.date DESC LIMIT 10""",
        (user["id"],),
    )

    payments = await fetch_all(
        db,
        "SELECT * FROM payments WHERE user_id = ? ORDER BY date DESC LIMIT 10",
        (user["id"],),
    )

    return {
        "user": user,
        "memberships": memberships,
        "recent_bookings": bookings,
        "recent_payments": payments,
    }


@registry.tool(
    name="get_trial_users",
    description=(
        "List all users currently on a free trial, optionally filtered "
        "by activity name."
    ),
    parameters={
        "type": "object",
        "properties": {
            "activity": {
                "type": "string",
                "description": "Filter by activity name (e.g. 'Badminton').",
            },
        },
    },
    access_level="read",
    category="users",
    examples=["List trial users of badminton", "Who is on trial?"],
)
async def get_trial_users(args: dict, db) -> dict:
    conditions = ["m.type = 'trial'", "m.status = 'active'"]
    params: list = []

    if args.get("activity"):
        conditions.append("LOWER(a.name) = LOWER(?)")
        params.append(args["activity"])

    where = " AND ".join(conditions)

    users = await fetch_all(
        db,
        f"""SELECT u.id, u.name, u.email, u.phone, u.status,
                   m.start_date, m.end_date, a.name AS activity_name
            FROM users u
            JOIN memberships m ON u.id = m.user_id
            JOIN activities a ON m.activity_id = a.id
            WHERE {where}
            ORDER BY m.end_date ASC""",
        tuple(params),
    )
    return {"trial_users": users, "count": len(users)}


@registry.tool(
    name="get_booking_stats",
    description=(
        "Get booking statistics: total bookings, revenue, popular time "
        "slots, and top activities. Accepts optional date range."
    ),
    parameters={
        "type": "object",
        "properties": {
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
    },
    access_level="read",
    category="bookings",
    examples=["Show booking stats", "How many bookings this week?"],
)
async def get_booking_stats(args: dict, db) -> dict:
    start = args.get("start_date", (date.today() - timedelta(days=30)).isoformat())
    end = args.get("end_date", date.today().isoformat())

    summary = await fetch_one(
        db,
        """SELECT COUNT(*) AS total_bookings,
                  COALESCE(SUM(amount), 0) AS total_revenue,
                  COUNT(DISTINCT user_id) AS unique_users
           FROM bookings
           WHERE date BETWEEN ? AND ?
             AND status != 'cancelled'""",
        (start, end),
    )

    popular_slots = await fetch_all(
        db,
        """SELECT time_slot, COUNT(*) AS booking_count
           FROM bookings
           WHERE date BETWEEN ? AND ? AND status != 'cancelled'
           GROUP BY time_slot
           ORDER BY booking_count DESC
           LIMIT 5""",
        (start, end),
    )

    top_activities = await fetch_all(
        db,
        """SELECT a.name, COUNT(*) AS booking_count,
                  SUM(b.amount) AS revenue
           FROM bookings b
           JOIN activities a ON b.activity_id = a.id
           WHERE b.date BETWEEN ? AND ? AND b.status != 'cancelled'
           GROUP BY a.id
           ORDER BY booking_count DESC
           LIMIT 5""",
        (start, end),
    )

    return {
        "summary": summary,
        "popular_time_slots": popular_slots,
        "top_activities": top_activities,
        "period": f"{start} to {end}",
    }


@registry.tool(
    name="get_membership_summary",
    description=(
        "Breakdown of memberships by type and status: how many active, "
        "expired, trial, monthly, quarterly, annual."
    ),
    parameters={
        "type": "object",
        "properties": {},
    },
    access_level="read",
    category="memberships",
    examples=["Membership summary", "How many active members?"],
)
async def get_membership_summary(args: dict, db) -> dict:
    by_type = await fetch_all(
        db,
        """SELECT type, COUNT(*) AS count,
                  SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) AS active,
                  SUM(CASE WHEN status='expired' THEN 1 ELSE 0 END) AS expired
           FROM memberships
           GROUP BY type""",
    )

    by_activity = await fetch_all(
        db,
        """SELECT a.name AS activity, COUNT(*) AS members,
                  SUM(CASE WHEN m.status='active' THEN 1 ELSE 0 END) AS active
           FROM memberships m
           JOIN activities a ON m.activity_id = a.id
           GROUP BY a.id
           ORDER BY members DESC""",
    )

    total = await fetch_one(
        db, "SELECT COUNT(*) AS total, SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) AS active FROM memberships"
    )

    return {
        "by_type": by_type,
        "by_activity": by_activity,
        "total": total,
    }


# ═══════════════════════════════════════════════════════════════════════
#  WRITE TOOLS — require vendor approval
# ═══════════════════════════════════════════════════════════════════════


@registry.tool(
    name="update_membership_date",
    description=(
        "Update a user's membership end date. Requires vendor approval. "
        "Provide user_id or user_name and the new_end_date."
    ),
    parameters={
        "type": "object",
        "properties": {
            "user_id": {"type": "string"},
            "user_name": {"type": "string"},
            "membership_id": {"type": "string"},
            "new_end_date": {
                "type": "string",
                "description": "New end date (YYYY-MM-DD).",
            },
        },
        "required": ["new_end_date"],
    },
    access_level="write",
    category="memberships",
    examples=["Extend Rahul's membership to Aug 15"],
)
async def update_membership_date(args: dict, db) -> dict:
    membership = await _resolve_membership(args, db)
    if "error" in membership:
        return membership

    await db.execute(
        "UPDATE memberships SET end_date = ? WHERE id = ?",
        (args["new_end_date"], membership["id"]),
    )
    await db.commit()

    return {
        "updated": True,
        "membership_id": membership["id"],
        "old_end_date": membership["end_date"],
        "new_end_date": args["new_end_date"],
    }


@registry.tool(
    name="update_trial_period",
    description=(
        "Extend a user's free trial by N extra days. Requires approval."
    ),
    parameters={
        "type": "object",
        "properties": {
            "user_id": {"type": "string"},
            "user_name": {"type": "string"},
            "membership_id": {"type": "string"},
            "extra_days": {
                "type": "integer",
                "description": "Number of extra trial days to add.",
            },
        },
        "required": ["extra_days"],
    },
    access_level="write",
    category="memberships",
    examples=["Add 7 days to Priya's trial"],
)
async def update_trial_period(args: dict, db) -> dict:
    membership = await _resolve_membership(args, db, type_filter="trial")
    if "error" in membership:
        return membership

    old_end = datetime.strptime(membership["end_date"], "%Y-%m-%d")
    new_end = old_end + timedelta(days=int(args["extra_days"]))

    await db.execute(
        "UPDATE memberships SET end_date = ? WHERE id = ?",
        (new_end.strftime("%Y-%m-%d"), membership["id"]),
    )
    await db.commit()

    return {
        "updated": True,
        "membership_id": membership["id"],
        "old_end_date": membership["end_date"],
        "new_end_date": new_end.strftime("%Y-%m-%d"),
        "extra_days": args["extra_days"],
    }


@registry.tool(
    name="update_user_status",
    description="Activate or deactivate a user account. Requires approval.",
    parameters={
        "type": "object",
        "properties": {
            "user_id": {"type": "string"},
            "user_name": {"type": "string"},
            "new_status": {
                "type": "string",
                "enum": ["active", "inactive"],
            },
        },
        "required": ["new_status"],
    },
    access_level="write",
    category="users",
    examples=["Deactivate user Amit"],
)
async def update_user_status(args: dict, db) -> dict:
    user = await _resolve_user(args, db)
    if "error" in user:
        return user

    old_status = user["status"]
    await db.execute(
        "UPDATE users SET status = ? WHERE id = ?",
        (args["new_status"], user["id"]),
    )
    await db.commit()

    return {
        "updated": True,
        "user_id": user["id"],
        "user_name": user["name"],
        "old_status": old_status,
        "new_status": args["new_status"],
    }


@registry.tool(
    name="update_payment_status",
    description="Mark a payment as paid or refunded. Requires approval.",
    parameters={
        "type": "object",
        "properties": {
            "payment_id": {"type": "string", "description": "The payment ID."},
            "new_status": {
                "type": "string",
                "enum": ["paid", "pending", "refunded"],
            },
        },
        "required": ["payment_id", "new_status"],
    },
    access_level="write",
    category="payments",
    examples=["Refund payment PAY-001"],
)
async def update_payment_status(args: dict, db) -> dict:
    payment = await fetch_one(
        db, "SELECT * FROM payments WHERE id = ?", (args["payment_id"],)
    )
    if not payment:
        return {"error": f"Payment '{args['payment_id']}' not found"}

    old_status = payment["status"]
    await db.execute(
        "UPDATE payments SET status = ? WHERE id = ?",
        (args["new_status"], payment["id"]),
    )
    await db.commit()

    return {
        "updated": True,
        "payment_id": payment["id"],
        "old_status": old_status,
        "new_status": args["new_status"],
    }


# ═══════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════


async def _resolve_user(args: dict, db) -> dict:
    """Find a user by id or name search."""
    if args.get("user_id"):
        user = await fetch_one(db, "SELECT * FROM users WHERE id = ?", (args["user_id"],))
    elif args.get("user_name"):
        user = await fetch_one(
            db,
            "SELECT * FROM users WHERE LOWER(name) LIKE LOWER(?)",
            (f"%{args['user_name']}%",),
        )
    else:
        return {"error": "Provide user_id or user_name"}
    if not user:
        return {"error": "User not found"}
    return user


async def _resolve_membership(args: dict, db, type_filter: str | None = None) -> dict:
    """Find a membership by id, or via user + optional type filter."""
    if args.get("membership_id"):
        return await fetch_one(
            db, "SELECT * FROM memberships WHERE id = ?", (args["membership_id"],)
        ) or {"error": "Membership not found"}

    user = await _resolve_user(args, db)
    if "error" in user:
        return user

    extra = " AND m.type = ?" if type_filter else ""
    params: list = [user["id"]]
    if type_filter:
        params.append(type_filter)

    membership = await fetch_one(
        db,
        f"""SELECT m.* FROM memberships m
            WHERE m.user_id = ?{extra}
            ORDER BY m.start_date DESC LIMIT 1""",
        tuple(params),
    )
    if not membership:
        msg = f"No {'trial ' if type_filter else ''}membership found for {user['name']}"
        return {"error": msg}
    return membership
