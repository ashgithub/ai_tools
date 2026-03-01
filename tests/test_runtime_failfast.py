from pathlib import Path

import pytest

from ai_tools.agent_runtime.errors import SkillExecutionError, SkillValidationError
from ai_tools.agent_runtime.runtime import DeepAgentRuntime
from ai_tools.agent_runtime.types import AgentRequest
from ai_tools.utils.config import get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_missing_agents_md_fails_fast(tmp_path: Path):
    (tmp_path / "skills").mkdir(parents=True)
    with pytest.raises(SkillValidationError) as exc:
        DeepAgentRuntime(get_settings(), project_root=tmp_path)
    assert exc.value.code == "SKILL_NOT_FOUND"


def test_runtime_missing_refresh_skill_fails_fast():
    runtime = DeepAgentRuntime(get_settings(), project_root=PROJECT_ROOT)
    runtime.skills.pop("refresh-llms", None)
    req = AgentRequest(input_text="", ui_tab="universal", options={"action": "refresh_models"})

    with pytest.raises(SkillValidationError) as exc:
        runtime.invoke(req)

    assert exc.value.code == "SKILL_NOT_FOUND"


def test_runtime_missing_primary_from_structured_fails_fast(monkeypatch):
    runtime = DeepAgentRuntime(get_settings(), project_root=PROJECT_ROOT)
    req = AgentRequest(input_text="hello", ui_tab="universal", options={"nudge": "commands"})

    monkeypatch.setattr(runtime, "_execute_deep_agent", lambda request, schema: {"alternatives": []})

    with pytest.raises(SkillExecutionError) as exc:
        runtime.invoke(req)

    assert exc.value.code == "SKILL_EXECUTION_FAILED"
