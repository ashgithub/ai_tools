from ai_tools.agent_runtime.routing import resolve_skill_id
from ai_tools.agent_runtime.types import AgentRequest


def test_proofread_explicit_context_wins():
    req = AgentRequest(
        input_text="hello",
        ui_tab="Proofread",
        app_context="slack",
        options={"proofread_context": "email"},
    )
    assert resolve_skill_id(req) == "proofread-email"


def test_proofread_app_fallback_slack():
    req = AgentRequest(
        input_text="hello",
        ui_tab="Proofread",
        app_context="slack",
        options={},
    )
    assert resolve_skill_id(req) == "proofread-slack"


def test_commands_routes_to_commands():
    req = AgentRequest(input_text="list files", ui_tab="Commands", options={})
    assert resolve_skill_id(req) == "commands"


def test_refresh_action_routes_to_refresh():
    req = AgentRequest(input_text="", ui_tab="Q&A", options={"action": "refresh_models"})
    assert resolve_skill_id(req) == "refresh-llms"


def test_refresh_tab_routes_to_refresh():
    req = AgentRequest(input_text="", ui_tab="Refresh", options={})
    assert resolve_skill_id(req) == "refresh-llms"
