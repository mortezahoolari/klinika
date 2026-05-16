"""Tests for the agent tool-calling loop (mocked Ollama)."""

from unittest.mock import MagicMock, patch

from klinika.agent.core import Agent


def _make_tool_response(tool_name: str, args: dict) -> dict:
    """Create a mock Ollama response that requests a tool call."""
    return {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": tool_name, "arguments": args}}
            ],
        }
    }


def _make_text_response(text: str) -> dict:
    """Create a mock Ollama response with final text."""
    return {"message": {"role": "assistant", "content": text}}


def test_agent_calls_tool_and_returns_result():
    """Model requests a tool call, agent executes it, model produces final text."""
    dummy_tool = {
        "type": "function",
        "function": {
            "name": "greet",
            "description": "Returns a greeting.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        "callable": lambda: "Hallo Welt!",
    }

    agent = Agent(model="test", system_prompt="test", tools=[dummy_tool])

    with patch.object(agent.client, "chat") as mock_chat:
        # First call: model requests greet tool. Second call: model uses result.
        mock_chat.side_effect = [
            _make_tool_response("greet", {}),
            _make_text_response("Die Begrüßung lautet: Hallo Welt!"),
        ]
        result = agent.run("Grüße mich")

    assert "Hallo Welt" in result
    assert mock_chat.call_count == 2


def test_agent_handles_no_tool_calls():
    """Model responds directly without tool calls."""
    agent = Agent(model="test", system_prompt="test", tools=[])

    with patch.object(agent.client, "chat") as mock_chat:
        mock_chat.return_value = _make_text_response("Ich bin Klinika.")
        result = agent.run("Wer bist du?")

    assert "Klinika" in result
    assert mock_chat.call_count == 1


def test_agent_handles_unknown_tool():
    """Model requests a tool that doesn't exist — agent returns error and continues."""
    agent = Agent(model="test", system_prompt="test", tools=[])

    with patch.object(agent.client, "chat") as mock_chat:
        mock_chat.side_effect = [
            _make_tool_response("nonexistent_tool", {}),
            _make_text_response("Entschuldigung, das Tool existiert nicht."),
        ]
        result = agent.run("Test")

    assert mock_chat.call_count == 2


def test_agent_passes_tool_args():
    """Tool receives arguments from the model."""
    def add(a: int, b: int) -> str:
        return str(a + b)

    tool = {
        "type": "function",
        "function": {
            "name": "add",
            "description": "Adds two numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
            },
        },
        "callable": add,
    }

    agent = Agent(model="test", system_prompt="test", tools=[tool])

    with patch.object(agent.client, "chat") as mock_chat:
        mock_chat.side_effect = [
            _make_tool_response("add", {"a": 3, "b": 4}),
            _make_text_response("Das Ergebnis ist 7."),
        ]
        result = agent.run("Was ist 3 + 4?")

    assert "7" in result


def test_agent_reset_clears_history():
    """Reset keeps system prompt but clears conversation."""
    agent = Agent(model="test", system_prompt="Ich bin ein Arzt.", tools=[])
    agent.messages.append({"role": "user", "content": "Hallo"})
    agent.messages.append({"role": "assistant", "content": "Hi"})

    agent.reset()

    assert len(agent.messages) == 1
    assert agent.messages[0]["role"] == "system"
