"""
Seed Data — Realistic Mock CRM Data for HobbyFi
=================================================

Populates the database with:
  • 1 vendor (HobbyFi Sports Hub)
  • 8 activities (Badminton, Cricket, Swimming, Yoga, Football, Tennis, Gym, Dance)
  • 20 users with Indian names
  • ~35 memberships across activities
  • ~80 bookings over the last 30 days
  • ~90 payments with mixed statuses
"""

from __future__ import annotations

import random
import uuid
from datetime import date, datetime, timedelta

from database import get_db


async def seed_if_empty():
    """Only seed when the database is blank."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) AS cnt FROM vendors")
        row = await cursor.fetchone()
        if row and row[0] > 0:
            return  # already seeded
    finally:
        await db.close()

    await _run_seed()


async def _run_seed():
    db = await get_db()
    try:
        # ─── Vendor ──────────────────────────────────────────────
        vendor_id = "V001"
        await db.execute(
            "INSERT INTO vendors (id, name, email, business_name, city) VALUES (?, ?, ?, ?, ?)",
            (vendor_id, "Mahesh Kumar", "mahesh@hobbyfi.in", "HobbyFi Sports Hub", "Bangalore"),
        )

        # ─── Activities ──────────────────────────────────────────
        activities = [
            ("A001", "Badminton", "Racquet Sports", 500),
            ("A002", "Cricket", "Team Sports", 600),
            ("A003", "Swimming", "Aquatics", 800),
            ("A004", "Yoga", "Wellness", 400),
            ("A005", "Football", "Team Sports", 550),
            ("A006", "Tennis", "Racquet Sports", 700),
            ("A007", "Gym", "Fitness", 900),
            ("A008", "Dance", "Performing Arts", 450),
        ]
        for aid, name, cat, rate in activities:
            await db.execute(
                "INSERT INTO activities (id, vendor_id, name, category, hourly_rate) VALUES (?, ?, ?, ?, ?)",
                (aid, vendor_id, name, cat, rate),
            )

        # ─── Users ────────────────────────────────────────────────
        users = [
            ("U001", "Rahul Sharma", "rahul.sharma@gmail.com", "+91-9876543210", "Bangalore"),
            ("U002", "Priya Patel", "priya.patel@gmail.com", "+91-9876543211", "Mumbai"),
            ("U003", "Amit Singh", "amit.singh@yahoo.com", "+91-9876543212", "Delhi"),
            ("U004", "Sneha Reddy", "sneha.reddy@gmail.com", "+91-9876543213", "Hyderabad"),
            ("U005", "Vikram Joshi", "vikram.j@outlook.com", "+91-9876543214", "Pune"),
            ("U006", "Ananya Gupta", "ananya.g@gmail.com", "+91-9876543215", "Bangalore"),
            ("U007", "Rohan Mehta", "rohan.mehta@gmail.com", "+91-9876543216", "Mumbai"),
            ("U008", "Kavita Nair", "kavita.nair@yahoo.com", "+91-9876543217", "Chennai"),
            ("U009", "Arjun Desai", "arjun.d@gmail.com", "+91-9876543218", "Pune"),
            ("U010", "Meera Iyer", "meera.iyer@gmail.com", "+91-9876543219", "Bangalore"),
            ("U011", "Sanjay Kulkarni", "sanjay.k@gmail.com", "+91-9876543220", "Mumbai"),
            ("U012", "Deepika Rao", "deepika.rao@outlook.com", "+91-9876543221", "Hyderabad"),
            ("U013", "Karthik Bhat", "karthik.b@gmail.com", "+91-9876543222", "Bangalore"),
            ("U014", "Nisha Agarwal", "nisha.a@yahoo.com", "+91-9876543223", "Delhi"),
            ("U015", "Rajesh Pillai", "rajesh.p@gmail.com", "+91-9876543224", "Chennai"),
            ("U016", "Swati Mishra", "swati.m@gmail.com", "+91-9876543225", "Bangalore"),
            ("U017", "Aditya Verma", "aditya.v@outlook.com", "+91-9876543226", "Pune"),
            ("U018", "Lakshmi Menon", "lakshmi.m@gmail.com", "+91-9876543227", "Mumbai"),
            ("U019", "Harish Pandey", "harish.p@gmail.com", "+91-9876543228", "Delhi"),
            ("U020", "Divya Chakraborty", "divya.c@yahoo.com", "+91-9876543229", "Kolkata"),
        ]

        today = date.today()

        for uid, name, email, phone, city in users:
            joined = today - timedelta(days=random.randint(10, 180))
            status = "active" if random.random() > 0.1 else "inactive"
            await db.execute(
                "INSERT INTO users (id, name, email, phone, city, joined_date, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (uid, name, email, phone, city, joined.isoformat(), status),
            )

        # ─── Memberships ─────────────────────────────────────────
        membership_types = [
            ("trial", 0, 7),
            ("monthly", 1500, 30),
            ("quarterly", 4000, 90),
            ("annual", 12000, 365),
        ]

        memberships = []

        # Give each user 1-2 memberships
        random.seed(42)  # reproducible
        for uid, name, *_ in users:
            num_memberships = random.choice([1, 1, 1, 2])
            chosen_activities = random.sample(activities, num_memberships)
            for act_id, act_name, _, _ in chosen_activities:
                mtype, amount, duration = random.choice(membership_types)
                start = today - timedelta(days=random.randint(0, 60))
                end = start + timedelta(days=duration)
                status = "active" if end >= today else "expired"
                mid = f"M{len(memberships)+1:03d}"
                memberships.append((mid, uid, act_id, mtype, start, end, status, amount))

        for mid, uid, aid, mtype, start, end, status, amount in memberships:
            await db.execute(
                """INSERT INTO memberships
                   (id, user_id, activity_id, type, start_date, end_date, status, amount)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (mid, uid, aid, mtype, start.isoformat(), end.isoformat(), status, amount),
            )

        # ─── Bookings ────────────────────────────────────────────
        time_slots = [
            "06:00-07:00", "07:00-08:00", "08:00-09:00",
            "09:00-10:00", "10:00-11:00", "16:00-17:00",
            "17:00-18:00", "18:00-19:00", "19:00-20:00",
            "20:00-21:00",
        ]

        bookings = []
        for i in range(80):
            uid, uname, *_ = random.choice(users)
            act_id, act_name, _, rate = random.choice(activities)
            bdate = today - timedelta(days=random.randint(0, 30))
            slot = random.choice(time_slots)
            amount = rate + random.randint(-100, 200)
            status = random.choice(["confirmed", "confirmed", "completed", "completed", "cancelled"])
            bid = f"B{i+1:03d}"
            bookings.append((bid, uid, act_id, bdate, slot, amount, status))

        for bid, uid, aid, bdate, slot, amount, status in bookings:
            await db.execute(
                """INSERT INTO bookings (id, user_id, activity_id, date, time_slot, amount, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (bid, uid, aid, bdate.isoformat(), slot, amount, status),
            )

        # ─── Payments ────────────────────────────────────────────
        payments = []
        pay_idx = 0

        # Payments from memberships
        for mid, uid, aid, mtype, start, end, status, amount in memberships:
            if amount > 0:
                pay_idx += 1
                pid = f"PAY{pay_idx:03d}"
                pstatus = random.choice(["paid", "paid", "paid", "pending"])
                pdate = start + timedelta(days=random.randint(0, 3))
                payments.append((pid, None, mid, uid, amount, pstatus, pdate))

        # Payments from bookings
        for bid, uid, aid, bdate, slot, amount, bstatus in bookings:
            if bstatus != "cancelled":
                pay_idx += 1
                pid = f"PAY{pay_idx:03d}"
                pstatus = "paid" if bstatus == "completed" else random.choice(["paid", "pending"])
                payments.append((pid, bid, None, uid, amount, pstatus, bdate))

        for pid, bid, mid, uid, amount, pstatus, pdate in payments:
            await db.execute(
                """INSERT INTO payments (id, booking_id, membership_id, user_id, amount, status, date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (pid, bid, mid, uid, amount, pstatus, pdate.isoformat()),
            )

        await db.commit()
        print(f"[OK] Seeded: 1 vendor, {len(activities)} activities, {len(users)} users, "
              f"{len(memberships)} memberships, {len(bookings)} bookings, {len(payments)} payments")
    finally:
        await db.close()
