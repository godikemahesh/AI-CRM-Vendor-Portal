# HobbyFi Copilot — AI-CRM Vendor Portal

> **AI-powered assistant** for HobbyFi's vendor portal.  
> Answers CRM queries (revenue, users, bookings, memberships) and executes write operations **only with vendor approval**.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green) ![React](https://img.shields.io/badge/React-19-blue) ![Cerebras](https://img.shields.io/badge/LLM-Cerebras-purple)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    React Vendor Portal (Vite)               │
│  ┌──────────┐ ┌──────────────┐ ┌──────────┐ ┌───────────┐  │
│  │Dashboard │ │ AI Chat Panel│ │ Approval │ │ Audit Log │  │
│  │ (Stats)  │ │  (Copilot)   │ │  Queue   │ │  Viewer   │  │
│  └──────────┘ └──────────────┘ └──────────┘ └───────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │ REST API
┌───────────────────────▼─────────────────────────────────────┐
│                  FastAPI Backend                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Mastra-Style Agent Engine                │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │   │
│  │  │System Prompt│  │Tool Registry │  │  Guardrails │  │   │
│  │  │ + Persona   │  │(Read + Write)│  │  (I/O both) │  │   │
│  │  └─────────────┘  └──────────────┘  └────────────┘  │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │   │
│  │  │Conversation │  │  Approval    │  │  Audit     │  │   │
│  │  │   Memory    │  │  Manager     │  │  Logger    │  │   │
│  │  └─────────────┘  └──────────────┘  └────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                        │                                    │
│              Cerebras LLM (llama-4-scout)                   │
│                        │                                    │
│              SQLite Database (Local)                        │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Set your Cerebras API key
copy .env.example .env
# Edit .env and add your CEREBRAS_API_KEY

# Run the server (auto-seeds mock data on first run)
python main.py
```

Backend runs on **http://localhost:8000**

### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (proxies API to backend)
npm run dev
```

Frontend runs on **http://localhost:5173**

---

## Tools & Frameworks

| Layer | Technology | Why |
|-------|-----------|-----|
| **LLM** | Cerebras (llama-4-scout-17b) | Ultra-fast inference, function calling support |
| **Backend** | Python + FastAPI | Async, modern, perfect for AI workloads |
| **Agent Engine** | Custom (Mastra-style) | Reason→Tool→Observe loop, typed tool registry |
| **Database** | SQLite + aiosqlite | Zero-config, async, perfect for demo |
| **Frontend** | React 19 + Vite | Fast dev cycle, modern React |

---

## Memory Strategy

| Type | Implementation |
|------|---------------|
| **Conversation Memory** | Full message history stored in SQLite (`messages` table) |
| **Sliding Window** | Last 20 messages sent to LLM context per turn |
| **Entity Tracking** | Mentioned users/entities tracked across conversation |
| **Session Persistence** | Conversations persist across page reloads |

**File:** `backend/agent/memory.py`

---

## Guardrails Framework (3 Layers)

| Layer | What it guards | Implementation |
|-------|---------------|----------------|
| **Input Guard** | User message before LLM | Prompt injection detection, off-topic filter |
| **Output Guard** | LLM response before delivery | PII redaction (phone/email masking) |
| **Tool Guard** | Each tool call before execution | Rate limiting, parameter validation, scope enforcement |

**File:** `backend/agent/guardrails.py`

---

## Workflow Orchestration

### Read Flow (Immediate)
```
User Query → Input Guard → LLM → Tool Call → Execute → Result → LLM → Response → Output Guard → User
```

### Write Flow (Approval Required)
```
User Query → Input Guard → LLM → Tool Call → Queue for Approval → Notify User
                                                    ↓
                                    Vendor Reviews (Before/After Diff)
                                                    ↓
                                    Approve → Execute → Audit Log
                                    Reject  → Log → Done
```

**Key Files:**
- `backend/agent/engine.py` — Agent orchestration loop
- `backend/agent/approval.py` — Approval queue + execution
- `backend/agent/audit.py` — Immutable audit trail

---

## Mock Data Schema

```sql
-- Core CRM Tables
vendors     (id, name, email, business_name, city, created_at)
activities  (id, vendor_id, name, category, hourly_rate, created_at)
users       (id, name, email, phone, city, joined_date, status)
memberships (id, user_id, activity_id, type, start_date, end_date, status, amount)
bookings    (id, user_id, activity_id, date, time_slot, amount, status)
payments    (id, booking_id, membership_id, user_id, amount, status, date)

-- AI System Tables
conversations   (id, vendor_id, created_at, summary)
messages        (id, conversation_id, role, content, tool_calls, timestamp)
pending_actions (id, conversation_id, tool_name, params, description, before_state, after_state, status, ...)
audit_logs      (id, action_type, tool_name, params, result, vendor_id, affected_user_id, ...)
```

**Seeded Data:** 1 vendor, 8 activities, 20 users (Indian names), ~35 memberships, ~80 bookings, ~90 payments

---

## Available Tools

### Read Tools (Execute Immediately)
| Tool | Description | Example Query |
|------|-------------|---------------|
| `get_today_revenue` | Revenue for today/date range | "What is today's revenue?" |
| `get_user_list` | Filter users by activity/status | "List all active users" |
| `get_user_details` | Full user profile + history | "Show Rahul's details" |
| `get_trial_users` | Users on free trial | "List trial users of badminton" |
| `get_booking_stats` | Booking analytics | "Show booking stats" |
| `get_membership_summary` | Membership breakdown | "Membership summary" |

### Write Tools (Require Vendor Approval)
| Tool | Description | Example Query |
|------|-------------|---------------|
| `update_membership_date` | Change membership end date | "Extend Rahul's membership to Aug 15" |
| `update_trial_period` | Add trial days | "Add 7 days to Priya's trial" |
| `update_user_status` | Activate/deactivate user | "Deactivate user Amit" |
| `update_payment_status` | Update payment status | "Refund payment PAY-001" |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send message to Copilot |
| GET | `/api/dashboard` | Dashboard KPI stats |
| GET | `/api/approvals` | List approval actions |
| POST | `/api/approvals/:id/approve` | Approve a write action |
| POST | `/api/approvals/:id/reject` | Reject a write action |
| GET | `/api/audit` | Audit log with filters |

---

## Project Structure

```
hobbyfi-assign/
├── backend/
│   ├── main.py              # FastAPI entry point + routes
│   ├── database.py          # SQLite schema + helpers
│   ├── seed_data.py         # Mock data generator
│   ├── requirements.txt     # Python dependencies
│   ├── .env.example         # Environment template
│   └── agent/
│       ├── __init__.py
│       ├── engine.py        # Mastra-style agent loop
│       ├── tools.py         # Read + Write CRM tools
│       ├── registry.py      # Dynamic tool registry
│       ├── memory.py        # Conversation memory
│       ├── guardrails.py    # 3-layer safety framework
│       ├── approval.py      # Human-in-the-loop approvals
│       └── audit.py         # Immutable audit trail
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── index.css         # Design system
        ├── api.js            # API client
        └── components/
            ├── Sidebar.jsx
            ├── Dashboard.jsx
            ├── ChatPanel.jsx
            ├── ApprovalQueue.jsx
            └── AuditLog.jsx
```

---

## Key Design Decisions

1. **Mastra Architecture Parity**: Typed tool registry with decorators (mirrors Mastra's `createTool` + Zod schemas), structured Reason→Tool→Observe loop
2. **Human-in-the-Loop**: All write operations suspended until vendor approval — diff-based review UI
3. **Guardrails at 3 Layers**: Input (injection), Output (PII), Tool-level (rate limit + scope)
4. **Complete Audit Trail**: Every action logged with params, results, vendor, timestamps
5. **Premium UI**: Dark theme, glassmorphism, HobbyFi green branding, micro-animations

---

*Built by Mahesh Kumar for the HobbyFi AI Engineer Assessment*
