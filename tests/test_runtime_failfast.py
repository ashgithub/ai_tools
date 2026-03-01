from pathlib import Path

import pytest

from ai_tools.agent_runtime.errors import RouteError, SkillValidationError
from ai_tools.agent_runtime.runtime import DeepAgentRuntime
from ai_tools.agent_runtime.types import AgentRequest
from ai_tools.utils.config import get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_unsupported_tab_fails_fast():
    runtime = DeepAgentRuntime(get_settings(), project_root=PROJECT_ROOT)
    req = AgentRequest(input_text="hello", ui_tab="Unknown", options={})

    with pytest.raises(RouteError) as exc:
        runtime.resolve_skill(req)

    assert exc.value.code == "ROUTE_UNSUPPORTED_TAB"


def test_runtime_missing_skill_fails_fast():
    runtime = DeepAgentRuntime(get_settings(), project_root=PROJECT_ROOT)
    runtime.skills.pop("ask", None)
    req = AgentRequest(input_text="hello", ui_tab="Q&A", options={})

    with pytest.raises(SkillValidationError) as exc:
        runtime.resolve_skill(req)

    assert exc.value.code == "SKILL_NOT_FOUND"
