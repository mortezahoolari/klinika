"""Plugin tools — find_plugin searches connected MCP servers for matching tools.

Tools are registered at startup but NOT loaded into the agent's context.
find_plugin injects matching schemas on demand, keeping context lean regardless
of how many MCP servers are connected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from klinika.agent.mcp_client import MCPClient
    from klinika.agent.core import Agent

_mcp_clients: list["MCPClient"] = []
_plugin_schemas: dict[str, dict] = {}   # name -> {type, function} schema (no callable)
_plugin_callables: dict[str, Any] = {}  # name -> callable
_agent_ref: "Agent | None" = None


def set_mcp_clients(clients: list["MCPClient"]) -> None:
    global _mcp_clients
    _mcp_clients = clients


def register_plugin_tool(name: str, schema: dict, callable_fn: Any) -> None:
    """Register an MCP plugin tool for lazy injection via find_plugin."""
    _plugin_schemas[name] = schema
    _plugin_callables[name] = callable_fn


def clear_plugins() -> None:
    """Reset plugin registry — for testing only."""
    _plugin_schemas.clear()
    _plugin_callables.clear()


def set_agent(agent: "Agent") -> None:
    """Provide agent reference so find_plugin can inject schemas on demand."""
    global _agent_ref
    _agent_ref = agent


def _inject_tool(name: str) -> None:
    """Inject a plugin tool into the agent's live tool list if not already there."""
    if _agent_ref is None or name not in _plugin_schemas:
        return
    if name not in _agent_ref._tool_registry:
        _agent_ref._tool_schemas.append(_plugin_schemas[name])
        _agent_ref._tool_registry[name] = _plugin_callables[name]


def eject_plugins() -> None:
    """Remove all injected plugin tools from the agent — called on conversation reset."""
    if _agent_ref is None:
        return
    names = set(_plugin_schemas.keys())
    _agent_ref._tool_schemas[:] = [s for s in _agent_ref._tool_schemas
                                    if s.get("function", {}).get("name") not in names]
    for name in names:
        _agent_ref._tool_registry.pop(name, None)


def find_plugin(capability: str) -> str:
    """Search installed MCP plugins for tools matching a capability description."""
    if not _plugin_schemas:
        return "No MCP plugins are currently installed."

    terms = capability.lower().split()
    matches: list[tuple[str, str]] = []

    for name, schema in _plugin_schemas.items():
        desc = schema.get("function", {}).get("description", "")
        combined = (name + " " + desc).lower()
        if not terms or any(term in combined for term in terms):
            matches.append((name, desc))

    # No specific match — return all (user is exploring what's available)
    if not matches:
        matches = [
            (name, schema.get("function", {}).get("description", ""))
            for name, schema in _plugin_schemas.items()
        ]

    # Inject discovered schemas so the model can call them on the next loop iteration
    for name, _ in matches:
        _inject_tool(name)

    lines = [f"- {name}: {desc}" for name, desc in matches]
    header = (
        "Available specialist plugins:"
        if not terms
        else f"Plugins matching '{capability}':"
    )
    return header + "\n" + "\n".join(lines) + "\n\nCall these tools by name."


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "find_plugin",
            "description": (
                "Search installed MCP plugins for tools matching a clinical capability. "
                "Use this when you need specialist analysis — ECG interpretation, "
                "dermatology AI, spirometry analysis, drug interaction checking — "
                "that may be provided by a third-party plugin. "
                "Returns tool names you can then call directly."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "capability": {
                        "type": "string",
                        "description": (
                            "What you need, e.g. 'ECG analysis', 'skin lesion AI', "
                            "'drug interactions', or 'all' to list everything installed"
                        ),
                    }
                },
                "required": ["capability"],
            },
        },
        "callable": find_plugin,
    }
]
