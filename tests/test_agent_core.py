"""Tests for Agent.update_system_prompt() — non-destructive system prompt replacement."""

from klinika.agent.core import Agent


def _minimal_agent() -> Agent:
    return Agent(model="test", system_prompt="initial prompt", tools=[])


def test_update_system_prompt_replaces_content():
    agent = _minimal_agent()
    agent.update_system_prompt("updated prompt")
    assert agent.messages[0]["content"] == "updated prompt"


def test_update_system_prompt_preserves_history():
    agent = _minimal_agent()
    agent.messages.append({"role": "user", "content": "hello"})
    agent.messages.append({"role": "assistant", "content": "hi"})

    agent.update_system_prompt("new system prompt")

    assert len(agent.messages) == 3
    assert agent.messages[0] == {"role": "system", "content": "new system prompt"}
    assert agent.messages[1] == {"role": "user", "content": "hello"}
    assert agent.messages[2] == {"role": "assistant", "content": "hi"}


def test_update_system_prompt_empty_messages():
    agent = Agent(model="test", system_prompt="", tools=[])
    # No system message was added (empty prompt)
    agent.messages = []

    agent.update_system_prompt("injected")

    assert len(agent.messages) == 1
    assert agent.messages[0] == {"role": "system", "content": "injected"}


def test_set_system_prompt_clears_history():
    """Confirm set_system_prompt() (original method) still wipes history."""
    agent = _minimal_agent()
    agent.messages.append({"role": "user", "content": "hello"})

    agent.set_system_prompt("reset prompt")

    assert len(agent.messages) == 1
    assert agent.messages[0]["content"] == "reset prompt"
