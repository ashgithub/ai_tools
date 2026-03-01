from pathlib import Path
import types

import pytest
from pydantic import ValidationError

from ai_tools.agent_runtime.errors import SkillExecutionError
from ai_tools.agent_runtime.runtime import DeepAgentRuntime
from ai_tools.agent_runtime.types import AgentRequest, CommandsOutput
from ai_tools.oci_openai_helper import OCIOpenAIHelper
from ai_tools.utils.config import get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_commands_schema_enforces_range():
    CommandsOutput.model_validate(
        {
            "alternatives": [
                {"command": "ls", "explanation": "List files."},
                {"command": "find . -name '*.py'", "explanation": "Find python files."},
                {"command": "fd .", "explanation": "Fast file search."},
            ]
        }
    )
    with pytest.raises(ValidationError):
        CommandsOutput.model_validate({"alternatives": []})


def test_schema_registry_and_primary_selector():
    runtime = DeepAgentRuntime(get_settings(), project_root=PROJECT_ROOT)
    schema, render = runtime._schema_for_skill("commands")
    assert schema.__name__ == "CommandsOutput"
    assert render == "commands"

    primary = runtime._primary_output_from_structured(
        "proofread-general",
        {"original": "x", "rewritten": "y"},
    )
    assert primary == "y"


class _FakeAgent:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def invoke(self, _payload):
        out = self.results[self.calls]
        self.calls += 1
        return out


def test_retry_once_then_success(monkeypatch):
    runtime = DeepAgentRuntime(get_settings(), project_root=PROJECT_ROOT)
    request = AgentRequest(input_text="hi", ui_tab="Q&A", options={})

    fake_agent = _FakeAgent(
        [
            {"structured_response": {"wrong": "shape"}},
            {"structured_response": {"answer": "final"}},
        ]
    )

    fake_module = types.SimpleNamespace(create_deep_agent=lambda **kwargs: fake_agent)
    monkeypatch.setitem(__import__("sys").modules, "deepagents", fake_module)
    monkeypatch.setattr(OCIOpenAIHelper, "get_client", staticmethod(lambda model_name, config: object()))

    response = runtime.invoke(request)
    assert response.primary_output == "final"
    assert fake_agent.calls == 2


def test_retry_once_then_fail(monkeypatch):
    runtime = DeepAgentRuntime(get_settings(), project_root=PROJECT_ROOT)
    request = AgentRequest(input_text="hi", ui_tab="Q&A", options={})

    fake_agent = _FakeAgent(
        [
            {"structured_response": {"wrong": "shape"}},
            {"structured_response": {"still_wrong": "shape"}},
        ]
    )

    fake_module = types.SimpleNamespace(create_deep_agent=lambda **kwargs: fake_agent)
    monkeypatch.setitem(__import__("sys").modules, "deepagents", fake_module)
    monkeypatch.setattr(OCIOpenAIHelper, "get_client", staticmethod(lambda model_name, config: object()))

    with pytest.raises(SkillExecutionError) as exc:
        runtime.invoke(request)

    assert exc.value.code == "SKILL_EXECUTION_FAILED"
    assert fake_agent.calls == 2
