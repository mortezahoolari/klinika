"""
Thin synchronous MCP client over stdio transport.

Connects to an MCP server subprocess, discovers its tools via tools/list,
and routes tool calls via tools/call — all over stdin/stdout JSON-RPC.

Designed to run inside the agent's synchronous tool-call path (no asyncio).
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MCPClient:
    """Connects to a single MCP server subprocess via stdio JSON-RPC."""

    def __init__(self, server_script: str) -> None:
        self.server_script = str(server_script)
        self._proc: subprocess.Popen | None = None
        self._req_id = 0
        self._tools: list[dict] = []        # raw MCP tool defs from tools/list
        self._lock = threading.Lock()       # serialize stdin/stdout access

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Spawn the server subprocess and complete the MCP handshake."""
        self._proc = subprocess.Popen(
            [sys.executable, self.server_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        # 1. initialize
        resp = self._send({
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "klinika", "version": "0.1.0"},
            },
        })
        server_name = resp.get("result", {}).get("serverInfo", {}).get("name", self.server_script)

        # 2. notifications/initialized (no response expected)
        self._notify("notifications/initialized", {})

        # 3. tools/list
        resp = self._send({"method": "tools/list", "params": {}})
        self._tools = resp.get("result", {}).get("tools", [])

        logger.info(
            "MCP: connected to '%s' — %d tool(s): %s",
            server_name,
            len(self._tools),
            ", ".join(t["name"] for t in self._tools),
        )

    def close(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                self._proc.kill()
            self._proc = None

    # ------------------------------------------------------------------
    # Tool interface
    # ------------------------------------------------------------------

    def list_tools(self) -> list[dict]:
        """Return Ollama-compatible tool dicts (with callable attached)."""
        result = []
        for t in self._tools:
            name = t["name"]
            result.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {
                        "type": "object", "properties": {}, "required": [],
                    }),
                },
                "callable": self._make_callable(name),
            })
        return result

    def call_tool(self, name: str, **kwargs: Any) -> str:
        """Call a tool on the MCP server and return the text result."""
        resp = self._send({
            "method": "tools/call",
            "params": {"name": name, "arguments": kwargs},
        })
        # MCP result: {"content": [{"type": "text", "text": "..."}]}
        content = resp.get("result", {}).get("content", [])
        parts = [c.get("text", "") for c in content if c.get("type") == "text"]
        return "\n".join(parts) if parts else str(resp.get("result", ""))

    def _make_callable(self, name: str):
        return lambda **kwargs: self.call_tool(name, **kwargs)

    # ------------------------------------------------------------------
    # MCP raw tool list (for find_plugin)
    # ------------------------------------------------------------------

    @property
    def raw_tools(self) -> list[dict]:
        """Raw tool defs from tools/list (name + description)."""
        return self._tools

    # ------------------------------------------------------------------
    # JSON-RPC transport
    # ------------------------------------------------------------------

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _send(self, msg: dict) -> dict:
        """Send a JSON-RPC request and return the matching response."""
        req_id = self._next_id()
        payload = {"jsonrpc": "2.0", "id": req_id, **msg}
        line = json.dumps(payload, ensure_ascii=False) + "\n"

        with self._lock:
            assert self._proc and self._proc.stdin
            self._proc.stdin.write(line.encode())
            self._proc.stdin.flush()

            # Read lines until we get a response matching our id
            # (skip notifications which have no "id" field)
            while True:
                raw = self._proc.stdout.readline()
                if not raw:
                    raise RuntimeError("MCP server closed stdout unexpectedly")
                try:
                    resp = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if resp.get("id") == req_id:
                    if "error" in resp:
                        raise RuntimeError(f"MCP error: {resp['error']}")
                    return resp

    def _notify(self, method: str, params: dict) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        with self._lock:
            assert self._proc and self._proc.stdin
            self._proc.stdin.write(line.encode())
            self._proc.stdin.flush()
