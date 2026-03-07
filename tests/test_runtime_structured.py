from pathlib import Path
import types

import pytest
from pydantic import ValidationError

from ai_tools.agent_runtime.errors import SkillExecutionError
from ai_tools.agent_runtime.runtime import DeepAgentRuntime
from ai_tools.agent_runtime.types import AgentRequest, Alternatives
from ai_tools.oci_openai_helper import OCIOpenAIHelper
from ai_tools.utils.config import get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_alternatives_schema_enforces_range():
    Alternatives.model_validate(
        {
            "alternatives": [
                {"value": "ls", "explanation": "List files."},
                {"value": "find . -name '*.py'", "explanation": "Find Python files."},
                {"value": "fd .", "explanation": "Fast file search."},
            ]
        }
    )
    with pytest.raises(ValidationError):
        Alternatives.model_validate({"alternatives": []})


def test_schema_registry_and_primary_selector():
    runtime = DeepAgentRuntime(get_settings(), project_root=PROJECT_ROOT)
    req = AgentRequest(input_text="hi", ui_tab="universal", options={"nudge": "commands"})
    schema, render = runtime._schema_for_request(req)
    assert schema.__name__ == "Alternatives"
    assert render == "alternatives"

    primary = runtime._primary_output("text_pair", {"corrected": "x", "rewritten": "y"})
    assert primary == "y"


class _FakeAgent:
    def __init__(self, result):
        self.result = result

    def invoke(self, _payload):
        return self.result


def test_runtime_invokes_with_all_skills_and_memory(monkeypatch):
    runtime = DeepAgentRuntime(get_settings(), project_root=PROJECT_ROOT)
    req = AgentRequest(input_text="hello", ui_tab="universal", options={"nudge": "ask"})

    captured: dict[str, object] = {}
    invoked: dict[str, object] = {}

    def _fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        class _CapturingAgent(_FakeAgent):
            def invoke(self, payload):
                invoked["payload"] = payload
                return self.result
        return _CapturingAgent({"structured_response": {"text": "ok"}})

    class _FakeFilesystemBackend:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_module = types.SimpleNamespace(create_deep_agent=_fake_create_deep_agent)
    fake_backends_module = types.SimpleNamespace(FilesystemBackend=_FakeFilesystemBackend)
    monkeypatch.setitem(__import__("sys").modules, "deepagents", fake_module)
    monkeypatch.setitem(__import__("sys").modules, "deepagents.backends", fake_backends_module)
    monkeypatch.setattr(OCIOpenAIHelper, "get_client", staticmethod(lambda model_name, config: object()))

    response = runtime.invoke(req)

    assert response.primary_output == "ok"
    assert captured.get("skills") == ["skills"]
    assert captured.get("memory") == ["AGENTS.md"]
    backend = captured.get("backend")
    assert backend is not None
    assert "FilesystemBackend" in backend.__class__.__name__
    response_format = captured.get("response_format")
    assert getattr(response_format, "__name__", "") == "SingleText"
    payload = invoked.get("payload")
    assert isinstance(payload, dict)
    messages = payload.get("messages")
    assert isinstance(messages, list) and messages
    content = str(messages[0].get("content", ""))
    assert "Task nudge:" in content
    assert "Answer the given question directly and concisely." in content


def test_schema_validation_failure_is_fail_fast(monkeypatch):
    runtime = DeepAgentRuntime(get_settings(), project_root=PROJECT_ROOT)
    req = AgentRequest(input_text="hello", ui_tab="universal", options={"nudge": "ask"})

    def _fake_create_deep_agent(**_kwargs):
        return _FakeAgent({"structured_response": {"wrong": "shape"}})

    class _FakeFilesystemBackend:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_module = types.SimpleNamespace(create_deep_agent=_fake_create_deep_agent)
    fake_backends_module = types.SimpleNamespace(FilesystemBackend=_FakeFilesystemBackend)
    monkeypatch.setitem(__import__("sys").modules, "deepagents", fake_module)
    monkeypatch.setitem(__import__("sys").modules, "deepagents.backends", fake_backends_module)
    monkeypatch.setattr(OCIOpenAIHelper, "get_client", staticmethod(lambda model_name, config: object()))

    with pytest.raises(SkillExecutionError) as exc:
        runtime.invoke(req)

    assert exc.value.code == "SKILL_EXECUTION_FAILED"


def test_runtime_collects_trace_lines_from_agent_messages(monkeypatch):
    runtime = DeepAgentRuntime(get_settings(), project_root=PROJECT_ROOT)
    req = AgentRequest(input_text="hello", ui_tab="universal", options={"nudge": "ask"})

    def _fake_create_deep_agent(**_kwargs):
        return _FakeAgent(
            {
                "structured_response": {"text": "ok"},
                "messages": [
                    {"type": "human", "content": "hello"},
                    {
                        "type": "ai",
                        "content": "I will use tools.",
                        "tool_calls": [
                            {
                                "name": "read_file",
                                "args": {"file_path": "/tmp/skills/ask/SKILL.md"},
                            },
                            {
                                "name": "task",
                                "args": {"description": "delegate"},
                            },
                        ],
                    },
                    {
                        "type": "tool",
                        "name": "read_file",
                        "args": {"file_path": "/tmp/skills/ask/SKILL.md"},
                        "content": "name: ask",
                    },
                ],
            }
        )

    class _FakeFilesystemBackend:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_module = types.SimpleNamespace(create_deep_agent=_fake_create_deep_agent)
    fake_backends_module = types.SimpleNamespace(FilesystemBackend=_FakeFilesystemBackend)
    monkeypatch.setitem(__import__("sys").modules, "deepagents", fake_module)
    monkeypatch.setitem(__import__("sys").modules, "deepagents.backends", fake_backends_module)
    monkeypatch.setattr(OCIOpenAIHelper, "get_client", staticmethod(lambda model_name, config: object()))

    response = runtime.invoke(req)

    assert response.primary_output == "ok"
    assert any(line == "schema=SingleText" for line in response.trace)
    assert any("[trace] tool_call -> read_file" in line for line in response.trace)
    assert any("[trace] skill_load -> ask" in line for line in response.trace)
    assert any("[trace] subagent_call -> task" in line for line in response.trace)
