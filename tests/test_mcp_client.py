"""Tests for MCPClient and find_plugin tool."""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from klinika.agent.mcp_client import MCPClient
from klinika.tools.plugins import find_plugin, set_mcp_clients, register_plugin_tool, clear_plugins


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(req_id: int, result: dict) -> bytes:
    return (json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}) + "\n").encode()


def _mock_proc(responses: list[bytes]):
    """Build a mock subprocess whose stdout yields the given response lines."""
    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.stdout = MagicMock()
    # readline() returns responses in order, then b"" (EOF)
    proc.stdout.readline.side_effect = responses + [b""]
    return proc


# ---------------------------------------------------------------------------
# MCPClient — tools/list
# ---------------------------------------------------------------------------

def test_tools_list_parsed():
    """connect() parses tools/list and list_tools() returns Ollama-format dicts."""
    tool_def = {
        "name": "analyze_ecg",
        "description": "Analyze ECG for arrhythmias.",
        "inputSchema": {
            "type": "object",
            "properties": {"patient_name": {"type": "string"}},
            "required": ["patient_name"],
        },
    }
    responses = [
        _make_response(1, {"protocolVersion": "2024-11-05", "serverInfo": {"name": "TestServer"}, "capabilities": {}}),
        _make_response(2, {"tools": [tool_def]}),
    ]

    client = MCPClient("fake_server.py")
    with patch("subprocess.Popen", return_value=_mock_proc(responses)):
        client.connect()

    tools = client.list_tools()
    assert len(tools) == 1
    assert tools[0]["function"]["name"] == "analyze_ecg"
    assert tools[0]["function"]["description"] == "Analyze ECG for arrhythmias."
    assert callable(tools[0]["callable"])


def test_tools_list_empty():
    """Server with no tools returns empty list."""
    responses = [
        _make_response(1, {"protocolVersion": "2024-11-05", "serverInfo": {"name": "Empty"}, "capabilities": {}}),
        _make_response(2, {"tools": []}),
    ]
    client = MCPClient("fake.py")
    with patch("subprocess.Popen", return_value=_mock_proc(responses)):
        client.connect()
    assert client.list_tools() == []


# ---------------------------------------------------------------------------
# MCPClient — tools/call
# ---------------------------------------------------------------------------

def test_call_tool_returns_string():
    """call_tool() sends tools/call and extracts text content."""
    connect_responses = [
        _make_response(1, {"protocolVersion": "2024-11-05", "serverInfo": {"name": "S"}, "capabilities": {}}),
        _make_response(2, {"tools": [{"name": "analyze_ecg", "description": "ECG", "inputSchema": {}}]}),
    ]
    call_response = _make_response(3, {
        "content": [{"type": "text", "text": "ECG normal sinus rhythm."}]
    })

    proc = _mock_proc(connect_responses + [call_response])
    client = MCPClient("fake.py")
    with patch("subprocess.Popen", return_value=proc):
        client.connect()
        result = client.call_tool("analyze_ecg", patient_name="Becker")

    assert "ECG" in result
    assert "sinus" in result


def test_call_tool_via_callable():
    """The callable returned by list_tools() delegates to call_tool()."""
    connect_responses = [
        _make_response(1, {"protocolVersion": "2024-11-05", "serverInfo": {"name": "S"}, "capabilities": {}}),
        _make_response(2, {"tools": [{"name": "analyze_ecg", "description": "", "inputSchema": {}}]}),
    ]
    call_response = _make_response(3, {"content": [{"type": "text", "text": "AF detected."}]})

    proc = _mock_proc(connect_responses + [call_response])
    client = MCPClient("fake.py")
    with patch("subprocess.Popen", return_value=proc):
        client.connect()
        fn = client.list_tools()[0]["callable"]
        result = fn(patient_name="Becker")

    assert "AF" in result


# ---------------------------------------------------------------------------
# find_plugin
# ---------------------------------------------------------------------------

def _register_ecg_tool() -> None:
    """Register a mock ECG tool via the new lazy-injection API."""
    schema = {
        "type": "function",
        "function": {
            "name": "analyze_ecg",
            "description": "Analyze ECG for cardiac arrhythmias.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }
    register_plugin_tool("analyze_ecg", schema, lambda **kw: "ECG result")


def test_find_plugin_match():
    """find_plugin returns matching tool name and description."""
    clear_plugins()
    _register_ecg_tool()
    result = find_plugin("ECG analysis")
    assert "analyze_ecg" in result
    assert "arrhythmia" in result.lower() or "analyze_ecg" in result


def test_find_plugin_no_match():
    """find_plugin with unrelated capability falls back to listing all plugins."""
    clear_plugins()
    _register_ecg_tool()
    result = find_plugin("dermatology skin lesion")
    # No specific match — fallback returns all available plugins
    assert "analyze_ecg" in result


def test_find_plugin_no_servers():
    """find_plugin with no plugins registered returns install message."""
    clear_plugins()
    set_mcp_clients([])
    result = find_plugin("anything")
    assert "No MCP plugins" in result
