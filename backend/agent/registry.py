"""
Dynamic Tool Registry — Mastra / LangGraph-style Architecture
=============================================================

Instead of hard-coding tools inside the agent, every tool *self-registers*
through the ``@registry.tool()`` decorator.  At runtime the agent engine
calls ``registry.list_all()`` and ``registry.generate_tool_prompt()``
to discover capabilities dynamically.

This mirrors:
  • Mastra's ``createTool({ name, description, inputSchema, execute })``
  • LangGraph's ``ToolNode`` + ``tool()`` decorator

Usage
-----
    from agent.registry import registry

    @registry.tool(
        name="get_revenue",
        description="Fetch total revenue for a given date",
        parameters={ ... json-schema ... },
        access_level="read",
    )
    async def get_revenue(args: dict, db) -> dict:
        ...

The registry automatically:
1. Validates tool names are unique
2. Generates human-readable + LLM-readable tool descriptions
3. Routes execute() calls to the correct handler
4. Tags tools with access_level ("read" vs "write") so the approval
   manager knows which calls need vendor confirmation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ToolDefinition:
    """Immutable descriptor for a single registered tool."""

    name: str
    description: str
    parameters: dict  # JSON-Schema dict
    handler: Callable  # async (args, db) -> dict
    access_level: str = "read"  # "read" | "write"
    requires_approval: bool = False
    category: str = "general"
    examples: list[str] = field(default_factory=list)

    # -- helpers --------------------------------------------------------

    def to_prompt_dict(self) -> dict:
        """Schema representation injected into the LLM system prompt."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "access_level": self.access_level,
            "requires_approval": self.requires_approval,
        }


class ToolRegistry:
    """Singleton registry.  Import once, use everywhere."""

    _instance: Optional[ToolRegistry] = None

    def __new__(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools: dict[str, ToolDefinition] = {}
        return cls._instance

    # -- registration ---------------------------------------------------

    def tool(
        self,
        *,
        name: str,
        description: str,
        parameters: dict,
        access_level: str = "read",
        requires_approval: bool | None = None,
        category: str = "general",
        examples: list[str] | None = None,
    ):
        """Decorator that registers the wrapped async function as a tool.

        Write-level tools automatically require approval unless explicitly
        overridden.
        """
        if requires_approval is None:
            requires_approval = access_level == "write"

        def decorator(fn: Callable):
            if name in self._tools:
                raise ValueError(f"Tool '{name}' is already registered")
            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
                handler=fn,
                access_level=access_level,
                requires_approval=requires_approval,
                category=category,
                examples=examples or [],
            )
            return fn

        return decorator

    def register(self, tool_def: ToolDefinition) -> None:
        """Programmatic (non-decorator) registration."""
        self._tools[tool_def.name] = tool_def

    # -- look-ups -------------------------------------------------------

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_all(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def list_read_tools(self) -> list[ToolDefinition]:
        return [t for t in self._tools.values() if t.access_level == "read"]

    def list_write_tools(self) -> list[ToolDefinition]:
        return [t for t in self._tools.values() if t.access_level == "write"]

    # -- execution ------------------------------------------------------

    async def execute(self, name: str, args: dict, db) -> dict:
        """Look up and call the tool.  Returns ``{success, data}``
        or ``{error}``."""
        tool = self.get(name)
        if tool is None:
            return {"error": f"Unknown tool '{name}'"}
        try:
            result = await tool.handler(args, db)
            return {"success": True, "data": result}
        except Exception as exc:
            return {"error": str(exc)}

    # -- prompt generation ----------------------------------------------

    def generate_tool_prompt(self) -> str:
        """Build the TOOLS section that gets injected into the LLM system
        prompt.  Returns a pretty-printed JSON array of tool schemas."""
        schemas = [t.to_prompt_dict() for t in self._tools.values()]
        return json.dumps(schemas, indent=2)

    # -- dunder ---------------------------------------------------------

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __repr__(self) -> str:
        names = ", ".join(self._tools.keys())
        return f"<ToolRegistry [{names}]>"


# Module-level singleton — import this everywhere
registry = ToolRegistry()
