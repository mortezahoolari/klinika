"""Tests for the core/admin tool split and system prompt builder in app.py."""
from datetime import date


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _names(tools: list) -> set:
    return {t["function"]["name"] for t in tools}


# ---------------------------------------------------------------------------
# Core tools
# ---------------------------------------------------------------------------

def test_core_tools_count():
    """Exactly 6 tools in core mode (5 clinical + find_plugin)."""
    from klinika.web.app import _core_tools
    assert len(_core_tools()) == 6


def test_core_tools_expected_names():
    """Core tools contain the 5 clinical tools plus find_plugin."""
    from klinika.web.app import _core_tools
    expected = {
        "get_patient", "search_patients", "add_observation",
        "query_device_results", "todays_schedule", "find_plugin",
    }
    assert _names(_core_tools()) == expected


def test_core_tools_exclude_admin_ops():
    """Core tools must not contain any import, skill, memory, clock, or legacy tools."""
    from klinika.web.app import _core_tools
    forbidden = {
        # admin / import
        "bootstrap", "read_incremental", "patient_count",
        "import_lab_results", "import_device_result", "sync_doctolib",
        # skills / memory / clock
        "save_skill", "list_skills", "use_skill", "delete_skill",
        "remember", "recall",
        "get_current_time", "get_current_date",
        # removed in smart tooling redesign
        "find_patient", "get_medications", "get_diagnoses",
        "get_allergies", "get_encounters", "query_lab_values", "flag_abnormals",
        # drafting tools removed (agent uses get_patient + writes directly)
        "create_draft", "save_draft", "list_drafts", "get_draft",
        # other excluded
        "current_patient", "list_device_results",
    }
    overlap = _names(_core_tools()) & forbidden
    assert overlap == set(), f"Core contains forbidden tools: {overlap}"


def test_core_tools_all_have_callable():
    """Every core tool must have a callable attached."""
    from klinika.web.app import _core_tools
    for t in _core_tools():
        assert callable(t.get("callable")), f"No callable on tool: {t['function']['name']}"


# ---------------------------------------------------------------------------
# Admin tools
# ---------------------------------------------------------------------------

def test_admin_tools_contain_import_ops():
    """Admin tools include all data import operations."""
    from klinika.web.app import _admin_tools
    names = _names(_admin_tools())
    for expected in ("bootstrap", "read_incremental", "import_lab_results",
                     "import_device_result", "sync_doctolib"):
        assert expected in names, f"Missing admin tool: {expected}"


def test_admin_tools_contain_skills():
    """Admin tools include the full skill suite."""
    from klinika.web.app import _admin_tools
    names = _names(_admin_tools())
    for expected in ("save_skill", "list_skills", "use_skill", "delete_skill"):
        assert expected in names, f"Missing skill tool: {expected}"


def test_admin_tools_contain_memory():
    """Admin tools include memory tools."""
    from klinika.web.app import _admin_tools
    names = _names(_admin_tools())
    assert "remember" in names
    assert "recall" in names


def test_admin_tools_contain_clock():
    """Admin tools include clock tools (removed from core, available in admin)."""
    from klinika.web.app import _admin_tools
    names = _names(_admin_tools())
    assert "get_current_time" in names
    assert "get_current_date" in names


def test_no_overlap_between_core_and_admin():
    """Core and admin tool sets are disjoint."""
    from klinika.web.app import _core_tools, _admin_tools
    overlap = _names(_core_tools()) & _names(_admin_tools())
    assert overlap == set(), f"Tools in both core and admin: {overlap}"


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

def test_system_prompt_en_contains_date():
    """English prompt includes today's date."""
    from klinika.web.app import _build_system_prompt
    prompt = _build_system_prompt("en")
    assert str(date.today().year) in prompt
    assert "Today's date" in prompt


def test_system_prompt_de_contains_date():
    """German prompt includes today's date."""
    from klinika.web.app import _build_system_prompt
    prompt = _build_system_prompt("de")
    assert str(date.today().year) in prompt
    assert "Datum" in prompt


def test_system_prompt_no_clock_tool_names():
    """System prompts do not reference clock tools (date is injected directly)."""
    from klinika.web.app import _build_system_prompt
    for lang in ("en", "de"):
        prompt = _build_system_prompt(lang)
        assert "get_current_time" not in prompt
        assert "get_current_date" not in prompt


def test_system_prompt_no_skill_instructions():
    """System prompts do not contain skill tool instructions (removed from core)."""
    from klinika.web.app import _build_system_prompt
    for lang in ("en", "de"):
        prompt = _build_system_prompt(lang)
        assert "save_skill" not in prompt
        assert "list_skills" not in prompt
        assert "use_skill" not in prompt


def test_system_prompt_no_find_patient():
    """System prompts no longer reference find_patient (collapsed into get_patient)."""
    from klinika.web.app import _build_system_prompt
    for lang in ("en", "de"):
        prompt = _build_system_prompt(lang)
        assert "find_patient" not in prompt


def test_system_prompt_mentions_core_tools():
    """System prompts reference the key core tools."""
    from klinika.web.app import _build_system_prompt
    for lang in ("en", "de"):
        prompt = _build_system_prompt(lang)
        assert "get_patient" in prompt
        assert "todays_schedule" in prompt


def test_system_prompt_no_create_draft():
    """System prompts no longer reference create_draft (removed from tool set)."""
    from klinika.web.app import _build_system_prompt
    for lang in ("en", "de"):
        prompt = _build_system_prompt(lang)
        assert "create_draft" not in prompt


def test_system_prompt_en_german_drafts_note():
    """English prompt reminds agent that clinical documents are drafted in German."""
    from klinika.web.app import _build_system_prompt
    prompt = _build_system_prompt("en")
    assert "German" in prompt
