"""Skill tools — save, list, use, and delete reusable workflows.

Skills capture multi-tool workflows that the doctor does repeatedly.
Instead of re-explaining the workflow each time, the doctor saves it
as a named skill and triggers it with one command.

The skill system is explicit: doctor saves + triggers by name.
No auto-matching RAG for MVP.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from klinika.skills.store import (
    save_skill as db_save_skill,
    get_skill as db_get_skill,
    list_skills as db_list_skills,
    delete_skill as db_delete_skill,
    increment_usage,
)

_conn: sqlite3.Connection | None = None
_agent: Any = None  # Reference to the Agent instance for tool history


def set_connection(conn: sqlite3.Connection) -> None:
    global _conn
    _conn = conn


def set_agent(agent: Any) -> None:
    """Set reference to the Agent instance (for get_tool_history)."""
    global _agent
    _agent = agent


def _get_conn() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("Skills DB not initialized.")
    return _conn


def save_skill(name: str, description: str) -> str:
    """Save the recent tool-call workflow as a named skill."""
    if _agent is None:
        return "Error: agent reference not available."

    history = _agent.get_tool_history(last_n=10)
    if not history:
        return "No tool calls found in the current session. Run a workflow first."

    # Filter out the save_skill call itself
    tool_sequence = [
        {"tool": h["tool"], "arguments": h["arguments"]}
        for h in history
        if h["tool"] != "save_skill"
    ]

    if not tool_sequence:
        return "No relevant tool calls found (only save_skill itself)."

    try:
        skill_id = db_save_skill(_get_conn(), name, description, tool_sequence)
        tools_str = ", ".join(t["tool"] for t in tool_sequence)
        return (
            f"Skill '{name}' saved (ID: {skill_id}).\n"
            f"Description: {description}\n"
            f"Tools: {tools_str}\n"
            f"Steps: {len(tool_sequence)}"
        )
    except sqlite3.IntegrityError:
        return f"Error: A skill named '{name}' already exists."


def list_skills() -> str:
    """List all saved skills."""
    skills = db_list_skills(_get_conn())
    if not skills:
        return "No skills saved."
    lines = ["Saved skills:"]
    for s in skills:
        used = f" (used: {s['usage_count']}x)" if s["usage_count"] else ""
        lines.append(f"  - **{s['name']}**: {s['description'] or 'No description'}{used}")
    return "\n".join(lines)


def use_skill(name: str) -> str:
    """Execute a saved skill by re-running its tool sequence."""
    skill = db_get_skill(_get_conn(), name)
    if not skill:
        return f"Skill '{name}' not found. Use list_skills to see available skills."

    if _agent is None:
        return "Error: agent reference not available."

    # Execute each tool in the sequence
    results = []
    for step in skill["tool_sequence"]:
        tool_name = step["tool"]
        tool_args = step.get("arguments", {})

        if tool_name not in _agent._tool_registry:
            results.append(f"Tool '{tool_name}' not available (skipped).")
            continue

        try:
            fn = _agent._tool_registry[tool_name]
            result = fn(**tool_args) if tool_args else fn()
            results.append(f"[{tool_name}] {str(result)[:200]}")
        except Exception as e:
            results.append(f"[{tool_name}] Error: {e}")

    increment_usage(_get_conn(), name)

    return (
        f"Skill '{name}' executed ({len(skill['tool_sequence'])} steps):\n\n"
        + "\n\n".join(results)
    )


def delete_skill(name: str) -> str:
    """Delete a saved skill."""
    if db_delete_skill(_get_conn(), name):
        return f"Skill '{name}' deleted."
    return f"Skill '{name}' not found."


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_skill",
            "description": (
                "Save the most recent tool-call workflow as a reusable named skill. "
                "The skill can later be re-executed with use_skill."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Skill name (e.g. 'lab-triage', 'morning-round')"},
                    "description": {"type": "string", "description": "What the skill does"},
                },
                "required": ["name", "description"],
            },
        },
        "callable": save_skill,
    },
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "List all saved skills.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        "callable": list_skills,
    },
    {
        "type": "function",
        "function": {
            "name": "use_skill",
            "description": "Execute a saved skill by replaying its recorded tool sequence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Skill name"},
                },
                "required": ["name"],
            },
        },
        "callable": use_skill,
    },
    {
        "type": "function",
        "function": {
            "name": "delete_skill",
            "description": "Delete a saved skill.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Skill name"},
                },
                "required": ["name"],
            },
        },
        "callable": delete_skill,
    },
]
