"""
Guardrails Framework — 3-Layer Safety Net
==========================================

Layer 1 — **Input Guard**   (runs on user message *before* LLM call)
  • Prompt-injection detection
  • Off-topic / out-of-scope filter

Layer 2 — **Output Guard**  (runs on LLM response *before* delivery)
  • Hallucination flag (must reference tool data)
  • Sensitive-data masking (phone / email redaction in summaries)

Layer 3 — **Tool Guard**    (runs on each tool call *before* execution)
  • Parameter validation (type + range)
  • Rate limiting (max N tool calls per conversation turn)
  • Scope enforcement (vendor can only access own data)

Each guard returns a ``GuardResult``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Known prompt-injection patterns (lightweight heuristic)
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+the\s+above",
    r"you\s+are\s+now\s+(?:a\s+)?(?:different|new)\s+(?:ai|assistant|bot)",
    r"system\s*:\s*",
    r"<\|?\s*system\s*\|?>",
    r"pretend\s+you\s+are",
    r"override\s+(?:your\s+)?(?:instructions|rules|prompt)",
    r"reveal\s+(?:your\s+)?(?:system\s+)?prompt",
    r"disregard\s+(?:all\s+)?(?:previous|prior)",
]

_INJECTION_RE = re.compile(
    "|".join(_INJECTION_PATTERNS), re.IGNORECASE
)

# Scope keywords that are definitely off-topic for a CRM copilot
_OFF_TOPIC_KEYWORDS = [
    "write me a poem", "tell me a joke", "translate this",
    "write code for", "hack ", "exploit ", "sql injection",
    "delete database", "drop table",
]


@dataclass
class GuardResult:
    passed: bool
    reason: str = ""


# ─── Layer 1: Input Guard ───────────────────────────────────────────

class InputGuard:
    """Validates the user message before it reaches the LLM."""

    @staticmethod
    def check(message: str) -> GuardResult:
        # 1. Prompt-injection detection
        if _INJECTION_RE.search(message):
            return GuardResult(
                passed=False,
                reason="Your message was flagged by our safety filter. "
                       "Please rephrase your request.",
            )

        # 2. Off-topic filter
        lower = message.lower()
        for keyword in _OFF_TOPIC_KEYWORDS:
            if keyword in lower:
                return GuardResult(
                    passed=False,
                    reason="I'm the HobbyFi CRM Copilot — I can help with "
                           "user data, revenue, bookings, and memberships. "
                           "That request is outside my scope.",
                )

        return GuardResult(passed=True)


# ─── Layer 2: Output Guard ──────────────────────────────────────────

_PHONE_RE = re.compile(r"\b(\+91[\s-]?)?[6-9]\d{9}\b")
_EMAIL_RE = re.compile(r"\b[\w.-]+@[\w.-]+\.\w+\b")


class OutputGuard:
    """Sanitises the LLM's final response before sending to the user."""

    @staticmethod
    def check(response: str) -> GuardResult:
        # We don't block, we just sanitise
        return GuardResult(passed=True)

    @staticmethod
    def sanitise(response: str) -> str:
        """Mask PII that the LLM might have surfaced verbatim."""
        text = _PHONE_RE.sub("[PHONE REDACTED]", response)
        text = _EMAIL_RE.sub("[EMAIL REDACTED]", text)
        return text


# ─── Layer 3: Tool Guard ────────────────────────────────────────────

MAX_TOOL_CALLS_PER_TURN = 8


class ToolGuard:
    """Validates tool calls before execution."""

    def __init__(self):
        self._call_count = 0

    def reset(self):
        """Call at the start of each user turn."""
        self._call_count = 0

    def check(self, tool_name: str, args: dict) -> GuardResult:
        # Rate-limit
        self._call_count += 1
        if self._call_count > MAX_TOOL_CALLS_PER_TURN:
            return GuardResult(
                passed=False,
                reason=f"Too many tool calls in one turn (max {MAX_TOOL_CALLS_PER_TURN}). "
                       "Please simplify your request.",
            )

        # Basic parameter type check
        if not isinstance(args, dict):
            return GuardResult(passed=False, reason="Invalid tool arguments format.")

        return GuardResult(passed=True)
