from ai_tools.agent_runtime.routing import resolve_schema_family
from ai_tools.agent_runtime.types import AgentRequest


def test_schema_from_explicit_nudge_text_pair():
    req = AgentRequest(input_text="hello", ui_tab="universal", options={"nudge": "slack"})
    assert resolve_schema_family(req) == "text_pair"


def test_schema_from_explicit_nudge_alternatives():
    req = AgentRequest(input_text="hello", ui_tab="universal", options={"nudge": "commands"})
    assert resolve_schema_family(req) == "alternatives"


def test_schema_from_app_context_fallback():
    req = AgentRequest(input_text="hello", ui_tab="universal", app_context="slack", options={})
    assert resolve_schema_family(req) == "text_pair"


def test_refresh_action_schema():
    req = AgentRequest(input_text="", ui_tab="universal", options={"action": "refresh_models"})
    assert resolve_schema_family(req) == "refresh"
