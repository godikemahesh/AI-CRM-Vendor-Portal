"""
Agent Engine — Mastra-Style Reason → Tool → Observe Loop
=========================================================

Core orchestration:
  1. Receive user message
  2. Run input guardrails
  3. Build context (system prompt + memory + tool schemas)
  4. Send to Cerebras LLM
  5. Parse response for tool calls
  6. Execute read tools / queue write tools for approval
  7. Feed tool results back and repeat until final answer
  8. Run output guardrails and return

Mirrors Mastra's Agent.generate() with structured tool calling,
suspension on write operations, and streaming support.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime

from cerebras.cloud.sdk import Cerebras

from agent.guardrails import InputGuard, OutputGuard, ToolGuard
from agent.memory import ConversationMemory
from agent.approval import ApprovalManager
from agent.audit import AuditLogger
from agent.registry import registry
from database import get_db

# Import tools so they self-register with the registry
import agent.tools  # noqa: F401

# ─── Configuration ──────────────────────────────────────────────────────
MODEL = "zai-glm-4.7"
MAX_AGENT_ITERATIONS = 6  # max tool→reason loops per turn

SYSTEM_PROMPT_TEMPLATE = """\
You are **HobbyFi Copilot**, the AI assistant embedded in the HobbyFi vendor portal.

## Your Role
You help hobby-centre vendors manage their CRM data: users, memberships, bookings, \
revenue, and payments.  You answer questions accurately using ONLY the tools provided.

## Key Rules
1. ALWAYS use the available tools to fetch data — NEVER fabricate numbers.
2. For **read** queries, call the appropriate tool and present the results clearly.
3. For **write** actions (updates), call the tool — it will be queued for vendor approval.
   Tell the vendor: "I've queued this change for your approval."
4. Be concise, professional, and friendly.
5. When listing data, use clean formatting (tables or numbered lists).
6. Today's date is {today}.
7. Format all monetary values and amounts in Indian Rupees (₹) using the Indian numbering system (e.g., ₹1,500 or ₹12,000).

## Available Tools
{tools_json}

## How to Call Tools
When you need to use a tool, respond with EXACTLY this JSON format on a single line:
```
TOOL_CALL: {{"name": "<tool_name>", "arguments": {{...}}}}
```
After receiving the tool result, use it to formulate your answer.
Do NOT wrap tool calls in markdown code blocks or add any other text on the same line.
Only call ONE tool at a time.

## Vendor Context
You are assisting vendor: {vendor_name} ({vendor_id})
"""


class AgentEngine:
    """Stateful agent that handles a single conversation turn."""

    def __init__(self, vendor_id: str = "V001", vendor_name: str = "HobbyFi Sports Hub"):
        self.vendor_id = vendor_id
        self.vendor_name = vendor_name
        self.tool_guard = ToolGuard()
        self._client = Cerebras(api_key=os.getenv("CEREBRAS_API_KEY", ""))

    # ─── Public entry point ─────────────────────────────────────────

    async def chat(
        self,
        user_message: str,
        conversation_id: str | None = None,
    ) -> dict:
        """Process a user message and return the agent's response.

        Returns
        -------
        dict with keys:
            response       : str   — final text answer
            tool_calls     : list  — tools invoked (for transparency)
            pending_actions: list  — write ops queued for approval
            conversation_id: str
        """
        # 1. Input guardrails
        guard = InputGuard.check(user_message)
        if not guard.passed:
            return {
                "response": guard.reason,
                "tool_calls": [],
                "pending_actions": [],
                "conversation_id": conversation_id,
                "blocked": True,
            }

        # 2. Memory — load or create conversation
        memory = ConversationMemory(self.vendor_id, conversation_id)
        conversation_id = await memory.get_or_create_conversation()

        # 3. Store user message
        await memory.add_message("user", user_message)

        # 4. Build system prompt
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            today=date.today().isoformat(),
            tools_json=registry.generate_tool_prompt(),
            vendor_name=self.vendor_name,
            vendor_id=self.vendor_id,
        )

        # 5. Build messages array for LLM
        context_messages = await memory.build_context_messages()
        llm_messages = [
            {"role": "system", "content": system_prompt},
            *context_messages,
        ]

        # 6. Reason → Tool → Observe loop
        self.tool_guard.reset()
        all_tool_calls = []
        pending_actions = []

        for _iteration in range(MAX_AGENT_ITERATIONS):
            # Call LLM
            response = self._call_llm(llm_messages)

            # Check for tool call in response
            tool_call = self._parse_tool_call(response)

            if tool_call is None:
                # No tool call — this is the final answer
                final_response = OutputGuard.sanitise(response)
                await memory.add_message("assistant", final_response)
                return {
                    "response": final_response,
                    "tool_calls": all_tool_calls,
                    "pending_actions": pending_actions,
                    "conversation_id": conversation_id,
                }

            # Execute tool
            tool_name = tool_call["name"]
            tool_args = tool_call.get("arguments", {})

            # Tool guardrail
            tg = self.tool_guard.check(tool_name, tool_args)
            if not tg.passed:
                llm_messages.append({"role": "assistant", "content": response})
                llm_messages.append({
                    "role": "user",
                    "content": f"TOOL_ERROR: {tg.reason}",
                })
                continue

            tool_def = registry.get(tool_name)
            if tool_def is None:
                llm_messages.append({"role": "assistant", "content": response})
                llm_messages.append({
                    "role": "user",
                    "content": f"TOOL_ERROR: Unknown tool '{tool_name}'.",
                })
                continue

            tool_record = {"name": tool_name, "arguments": tool_args, "access_level": tool_def.access_level}

            if tool_def.requires_approval:
                # WRITE tool → queue for approval, don't execute yet
                # Fetch before-state if possible
                before_state = await self._get_before_state(tool_name, tool_args)
                description = self._build_action_description(tool_name, tool_args)
                pending = await ApprovalManager.create_pending_action(
                    tool_name=tool_name,
                    params=tool_args,
                    description=description,
                    before_state=before_state,
                    conversation_id=conversation_id,
                )
                pending_actions.append(pending)
                tool_record["status"] = "pending_approval"
                tool_result = {
                    "status": "pending_approval",
                    "message": f"Action '{description}' has been queued for vendor approval.",
                    "action_id": pending["id"],
                }

                # Audit log
                await AuditLogger.log(
                    action_type="write",
                    tool_name=tool_name,
                    params=tool_args,
                    result={"status": "pending_approval"},
                    vendor_id=self.vendor_id,
                )
            else:
                # READ tool → execute immediately
                db = await get_db()
                try:
                    tool_result = await registry.execute(tool_name, tool_args, db)
                finally:
                    await db.close()

                tool_record["status"] = "executed"

                # Audit log
                await AuditLogger.log(
                    action_type="read",
                    tool_name=tool_name,
                    params=tool_args,
                    result=tool_result,
                    vendor_id=self.vendor_id,
                )

            all_tool_calls.append(tool_record)

            # Feed tool result back to LLM
            llm_messages.append({"role": "assistant", "content": response})
            llm_messages.append({
                "role": "user",
                "content": f"TOOL_RESULT: {json.dumps(tool_result, default=str)}",
            })

        # Exhausted iterations — return what we have
        final_response = "I've completed the analysis. Please let me know if you need anything else."
        await memory.add_message("assistant", final_response)
        return {
            "response": final_response,
            "tool_calls": all_tool_calls,
            "pending_actions": pending_actions,
            "conversation_id": conversation_id,
        }

    # ─── LLM call ────────────────────────────────────────────────────

    def _call_llm(self, messages: list[dict]) -> str:
        """Synchronous Cerebras chat-completion call."""
        try:
            completion = self._client.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=1024,
                temperature=0.3,
            )
            return completion.choices[0].message.content or ""
        except Exception as exc:
            return f"I encountered an error communicating with the AI service: {str(exc)}"

    # ─── Tool call parser ────────────────────────────────────────────

    @staticmethod
    def _parse_tool_call(response: str) -> dict | None:
        """Extract TOOL_CALL JSON from the LLM response.

        Looks for the pattern:  TOOL_CALL: {"name": "...", "arguments": {...}}
        """
        # Try the explicit TOOL_CALL: prefix
        match = re.search(r'TOOL_CALL:\s*(\{.*\})', response, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
                if "name" in parsed:
                    return parsed
            except json.JSONDecodeError:
                pass

        # Fallback: look for JSON with "name" and "arguments" keys in code blocks
        code_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if code_block:
            try:
                parsed = json.loads(code_block.group(1))
                if "name" in parsed and "arguments" in parsed:
                    return parsed
            except json.JSONDecodeError:
                pass

        return None

    # ─── Helpers for approval workflow ────────────────────────────────

    async def _get_before_state(self, tool_name: str, args: dict) -> dict | None:
        """Fetch the current state before a write operation."""
        db = await get_db()
        try:
            if tool_name in ("update_membership_date", "update_trial_period"):
                from agent.tools import _resolve_membership
                m = await _resolve_membership(args, db)
                if "error" not in m:
                    return {"membership_id": m["id"], "end_date": m["end_date"], "type": m["type"]}
            elif tool_name == "update_user_status":
                from agent.tools import _resolve_user
                u = await _resolve_user(args, db)
                if "error" not in u:
                    return {"user_id": u["id"], "name": u["name"], "status": u["status"]}
            elif tool_name == "update_payment_status":
                from database import fetch_one
                p = await fetch_one(db, "SELECT * FROM payments WHERE id = ?", (args.get("payment_id"),))
                if p:
                    return {"payment_id": p["id"], "status": p["status"], "amount": p["amount"]}
        except Exception:
            pass
        finally:
            await db.close()
        return None

    @staticmethod
    def _build_action_description(tool_name: str, args: dict) -> str:
        """Human-readable summary of the write action."""
        descriptions = {
            "update_membership_date": lambda a: f"Change membership end date to {a.get('new_end_date', '?')}",
            "update_trial_period": lambda a: f"Extend trial by {a.get('extra_days', '?')} days",
            "update_user_status": lambda a: f"Set user status to '{a.get('new_status', '?')}'",
            "update_payment_status": lambda a: f"Change payment {a.get('payment_id', '?')} status to '{a.get('new_status', '?')}'",
        }
        builder = descriptions.get(tool_name)
        if builder:
            target = a.get("user_name") or a.get("user_id") or "" if (a := args) else ""
            prefix = f"For {target}: " if target else ""
            return prefix + builder(args)
        return f"{tool_name}({json.dumps(args)})"
