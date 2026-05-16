"""Tests for the skill learning system."""

import sqlite3

from klinika.skills.store import (
    init_skills_db,
    save_skill,
    get_skill,
    list_skills,
    delete_skill,
    increment_usage,
)
from klinika.agent.core import Agent


def _setup_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    init_skills_db(conn)
    return conn


class TestSkillsDB:
    def setup_method(self):
        self.conn = _setup_db()

    def test_save_and_get(self):
        skill_id = save_skill(self.conn, "Labor-Check", "Laborwerte pruefen",
                              [{"tool": "flag_abnormals", "arguments": {}}])
        assert skill_id
        skill = get_skill(self.conn, "Labor-Check")
        assert skill is not None
        assert skill["name"] == "Labor-Check"
        assert skill["description"] == "Laborwerte pruefen"
        assert len(skill["tool_sequence"]) == 1
        assert skill["tool_sequence"][0]["tool"] == "flag_abnormals"
        assert skill["usage_count"] == 0

    def test_list_skills(self):
        save_skill(self.conn, "Skill-A", "desc A", [{"tool": "a", "arguments": {}}])
        save_skill(self.conn, "Skill-B", "desc B", [{"tool": "b", "arguments": {}}])
        skills = list_skills(self.conn)
        assert len(skills) == 2
        names = {s["name"] for s in skills}
        assert names == {"Skill-A", "Skill-B"}

    def test_delete_skill(self):
        save_skill(self.conn, "ToDelete", "will be deleted", [{"tool": "x", "arguments": {}}])
        assert delete_skill(self.conn, "ToDelete") is True
        assert get_skill(self.conn, "ToDelete") is None

    def test_delete_nonexistent(self):
        assert delete_skill(self.conn, "Nope") is False

    def test_unique_name(self):
        save_skill(self.conn, "Unique", "first", [{"tool": "a", "arguments": {}}])
        try:
            save_skill(self.conn, "Unique", "duplicate", [{"tool": "b", "arguments": {}}])
            assert False, "Should raise IntegrityError"
        except Exception:
            pass

    def test_increment_usage(self):
        save_skill(self.conn, "Counter", "count test", [{"tool": "x", "arguments": {}}])
        increment_usage(self.conn, "Counter")
        increment_usage(self.conn, "Counter")
        skill = get_skill(self.conn, "Counter")
        assert skill["usage_count"] == 2
        assert skill["last_used"] is not None

    def test_multi_step_sequence(self):
        sequence = [
            {"tool": "find_patient", "arguments": {"name": "Schmidt"}},
            {"tool": "get_medications", "arguments": {"patient_id": "00042"}},
            {"tool": "flag_abnormals", "arguments": {"patient_id": "00042"}},
        ]
        save_skill(self.conn, "Schmidt-Check", "Check Schmidt", sequence)
        skill = get_skill(self.conn, "Schmidt-Check")
        assert len(skill["tool_sequence"]) == 3
        assert skill["tool_sequence"][0]["tool"] == "find_patient"
        assert skill["tool_sequence"][2]["tool"] == "flag_abnormals"


class TestAgentToolHistory:
    def test_empty_history(self):
        agent = Agent(model="test", system_prompt="test", tools=[])
        history = agent.get_tool_history()
        assert history == []

    def test_history_extraction(self):
        agent = Agent(model="test", system_prompt="test", tools=[])
        # Simulate tool call messages in history
        agent.messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "get_current_time", "arguments": {}}}
            ],
        })
        agent.messages.append({"role": "tool", "content": "14:30"})
        agent.messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "find_patient", "arguments": {"name": "Schmidt"}}}
            ],
        })
        agent.messages.append({"role": "tool", "content": "Found: Karl Schmidt (00042)"})

        history = agent.get_tool_history()
        assert len(history) == 2
        assert history[0]["tool"] == "get_current_time"
        assert history[1]["tool"] == "find_patient"
        assert history[1]["arguments"] == {"name": "Schmidt"}
        assert "Schmidt" in history[1]["result_preview"]
