"""
Klinika Agent — thin tool-calling loop over Ollama.

The agent sends messages to the model with available tool schemas.
When the model returns tool_calls, the agent executes them, feeds
results back, and re-calls until the model produces a final text response.
"""

from __future__ import annotations

import json
from typing import Any

import ollama

from klinika.config import CHAT_MODEL, OLLAMA_HOST


class Agent:
    """Stateful agent with tool-calling loop."""

    def __init__(
        self,
        model: str = CHAT_MODEL,
        system_prompt: str = "",
        tools: list[dict] | None = None,
    ) -> None:
        self.model = model
        self.client = ollama.Client(host=OLLAMA_HOST)
        self.messages: list[dict] = []
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})

        # Separate tool schemas (sent to model) from callables (executed locally)
        self._tool_schemas: list[dict] = []
        self._tool_registry: dict[str, Any] = {}
        for tool in tools or []:
            tool = dict(tool)  # shallow copy — don't mutate caller's list
            fn = tool.pop("callable")
            name = tool["function"]["name"]
            self._tool_schemas.append(tool)
            self._tool_registry[name] = fn

    def run(self, user_message: str) -> str:
        """Process a user message through the tool-calling loop. Returns final text."""
        self.messages.append({"role": "user", "content": user_message})

        max_iterations = 10
        for _ in range(max_iterations):
            response = self.client.chat(
                model=self.model,
                messages=self.messages,
                tools=self._tool_schemas if self._tool_schemas else None,
            )

            msg = response.get("message", {})
            tool_calls = msg.get("tool_calls")

            if not tool_calls:
                # Final text response — no more tool calls
                content = msg.get("content", "")
                self.messages.append({"role": "assistant", "content": content})
                return content

            # Model wants to call tools — execute each one
            self.messages.append(msg)

            for call in tool_calls:
                fn_name = call["function"]["name"]
                fn_args = call["function"].get("arguments", {})

                if fn_name not in self._tool_registry:
                    result = f"Error: unknown tool '{fn_name}'"
                else:
                    try:
                        fn = self._tool_registry[fn_name]
                        result = fn(**fn_args) if fn_args else fn()
                        result = str(result)
                    except Exception as e:
                        result = f"Error calling {fn_name}: {e}"

                self.messages.append({"role": "tool", "content": result})

        return "(max tool iterations reached)"

    def run_stream(self, user_message: str):
        """Like run() but yields progress events during the tool-calling loop.

        Yields:
            {"type": "tool",  "name": str, "status": "calling" | "done"}
            {"type": "text",  "content": str}   — final response
        """
        self.messages.append({"role": "user", "content": user_message})

        for _ in range(10):
            response = self.client.chat(
                model=self.model,
                messages=self.messages,
                tools=self._tool_schemas if self._tool_schemas else None,
            )

            msg = response.get("message", {})
            tool_calls = msg.get("tool_calls")

            if not tool_calls:
                content = msg.get("content", "")
                self.messages.append({"role": "assistant", "content": content})
                yield {"type": "text", "content": content}
                return

            self.messages.append(msg)

            for call in tool_calls:
                fn_name = call["function"]["name"]
                fn_args = call["function"].get("arguments", {})

                yield {"type": "tool", "name": fn_name, "status": "calling"}

                if fn_name not in self._tool_registry:
                    result = f"Error: unknown tool '{fn_name}'"
                else:
                    try:
                        fn = self._tool_registry[fn_name]
                        result = fn(**fn_args) if fn_args else fn()
                        result = str(result)
                    except Exception as e:
                        result = f"Error calling {fn_name}: {e}"

                yield {"type": "tool", "name": fn_name, "status": "done"}
                self.messages.append({"role": "tool", "content": result})

        yield {"type": "text", "content": "(max tool iterations reached)"}

    def get_tool_history(self, last_n: int = 10) -> list[dict]:
        """Extract recent tool calls from conversation history.

        Returns list of {tool: str, arguments: dict, result_preview: str}.
        Used by the skill system to capture workflows.
        """
        history = []
        for i, msg in enumerate(self.messages):
            if not isinstance(msg, dict):
                continue
            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                continue
            for call in tool_calls:
                fn = call.get("function", {})
                tool_name = fn.get("name", "")
                tool_args = fn.get("arguments", {})
                # Find the corresponding tool result
                result_preview = ""
                for j in range(i + 1, min(i + len(tool_calls) + 2, len(self.messages))):
                    next_msg = self.messages[j]
                    if isinstance(next_msg, dict) and next_msg.get("role") == "tool":
                        result_preview = next_msg.get("content", "")[:100]
                        break
                history.append({
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result_preview": result_preview,
                })
        return history[-last_n:]

    def set_system_prompt(self, prompt: str) -> None:
        """Replace the system prompt and reset conversation history."""
        self.messages = [{"role": "system", "content": prompt}]

    def update_system_prompt(self, prompt: str) -> None:
        """Replace the system prompt text without clearing conversation history."""
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = prompt
        else:
            self.messages.insert(0, {"role": "system", "content": prompt})

    def reset(self) -> None:
        """Clear conversation history (keep system prompt)."""
        system = [m for m in self.messages if m["role"] == "system"]
        self.messages = system
