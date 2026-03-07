from pathlib import Path
import types

import pytest

from ai_tools.agent_runtime.errors import SkillExecutionError, SkillValidationError
from ai_tools.agent_runtime.runtime import DeepAgentRuntime
from ai_tools.agent_runtime.types import AgentRequest
from ai_tools.oci_openai_helper import OCIOpenAIHelper
from ai_tools.utils.config import get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.setattr(DeepAgentRuntime, "_validate_global_memory", lambda self: None)
    return DeepAgentRuntime(get_settings(), project_root=PROJECT_ROOT)


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


def test_no_invoke_fallback(monkeypatch, runtime):
    req = AgentRequest(input_text="hello", ui_tab="universal", options={"nudge": "ask", "nudge_prompt": "Answer directly."})

    class _StreamingAgent:
        def invoke(self, _payload):
            raise AssertionError("invoke() fallback must not be used")

        def stream(self, _payload, stream_mode="values"):
            assert stream_mode == "values"
            while True:
                yield {"messages": [{"type": "ai", "content": "still working"}]}

    def _fake_create_deep_agent(**_kwargs):
        return _StreamingAgent()

    class _FakeFilesystemBackend:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_module = types.SimpleNamespace(create_deep_agent=_fake_create_deep_agent)
    fake_backends_module = types.SimpleNamespace(FilesystemBackend=_FakeFilesystemBackend)
    monkeypatch.setitem(__import__("sys").modules, "deepagents", fake_module)
    monkeypatch.setitem(__import__("sys").modules, "deepagents.backends", fake_backends_module)
    monkeypatch.setattr(OCIOpenAIHelper, "get_client", staticmethod(lambda model_name, config: object()))

    with pytest.raises(SkillExecutionError, match="max-events exceeded") as exc:
        runtime.invoke_streamed(req, runtime._schema_for_request(req)[0], max_events=2)

    assert exc.value.code == "SKILL_EXECUTION_FAILED"


def test_max_events_zero(monkeypatch, runtime):
    req = AgentRequest(input_text="hello", ui_tab="universal", options={"nudge": "ask", "nudge_prompt": "Answer directly."})
    diagnostics_calls: list[list[str]] = []

    class _StreamingAgent:
        def stream(self, _payload, stream_mode="values"):
            assert stream_mode == "values"
            yield {"messages": [{"type": "ai", "content": "first event"}]}

    def _fake_create_deep_agent(**_kwargs):
        return _StreamingAgent()

    class _FakeFilesystemBackend:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_module = types.SimpleNamespace(create_deep_agent=_fake_create_deep_agent)
    fake_backends_module = types.SimpleNamespace(FilesystemBackend=_FakeFilesystemBackend)
    monkeypatch.setitem(__import__("sys").modules, "deepagents", fake_module)
    monkeypatch.setitem(__import__("sys").modules, "deepagents.backends", fake_backends_module)
    monkeypatch.setattr(OCIOpenAIHelper, "get_client", staticmethod(lambda model_name, config: object()))

    with pytest.raises(SkillExecutionError, match="max-events exceeded") as exc:
        runtime.invoke_streamed(
            req,
            runtime._schema_for_request(req)[0],
            max_events=0,
            diagnostics_callback=lambda lines: diagnostics_calls.append(lines),
        )

    assert exc.value.code == "SKILL_EXECUTION_FAILED"
    assert diagnostics_calls == []


def test_max_events_equal_boundary(monkeypatch, runtime):
    req = AgentRequest(input_text="hello", ui_tab="universal", options={"nudge": "ask", "nudge_prompt": "Answer directly."})
    boundary = 3

    class _StreamingAgent:
        def stream(self, _payload, stream_mode="values"):
            assert stream_mode == "values"
            yield {"messages": [{"type": "ai", "content": "step 1"}]}
            yield {"messages": [{"type": "ai", "content": "step 2"}]}
            yield {
                "messages": [{"type": "ai", "content": "done"}],
                "structured_response": {"text": "ok"},
            }

    def _fake_create_deep_agent(**_kwargs):
        return _StreamingAgent()

    class _FakeFilesystemBackend:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_module = types.SimpleNamespace(create_deep_agent=_fake_create_deep_agent)
    fake_backends_module = types.SimpleNamespace(FilesystemBackend=_FakeFilesystemBackend)
    monkeypatch.setitem(__import__("sys").modules, "deepagents", fake_module)
    monkeypatch.setitem(__import__("sys").modules, "deepagents.backends", fake_backends_module)
    monkeypatch.setattr(OCIOpenAIHelper, "get_client", staticmethod(lambda model_name, config: object()))

    success_diagnostics: list[list[str]] = []
    result = runtime.invoke_streamed(
        req,
        runtime._schema_for_request(req)[0],
        max_events=boundary,
        diagnostics_callback=lambda lines: success_diagnostics.append(lines),
    )
    assert result == {"text": "ok"}
    assert len(success_diagnostics) == boundary
    assert any("[trace] ai -> done" in line for lines in success_diagnostics for line in lines)

    failure_diagnostics: list[list[str]] = []
    with pytest.raises(SkillExecutionError, match="max-events exceeded") as exc:
        runtime.invoke_streamed(
            req,
            runtime._schema_for_request(req)[0],
            max_events=boundary - 1,
            diagnostics_callback=lambda lines: failure_diagnostics.append(lines),
        )

    assert exc.value.code == "SKILL_EXECUTION_FAILED"
    assert len(failure_diagnostics) == boundary - 1


def test_timeout_fails(monkeypatch, runtime):
    req = AgentRequest(input_text="hello", ui_tab="universal", options={"nudge": "ask", "nudge_prompt": "Answer directly."})
    clock = iter([0.0, 0.0, 31.0, 31.0])

    class _StreamingAgent:
        def stream(self, _payload, stream_mode="values"):
            assert stream_mode == "values"
            yield {"messages": [{"type": "ai", "content": "slow event"}]}

    def _fake_create_deep_agent(**_kwargs):
        return _StreamingAgent()

    class _FakeFilesystemBackend:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_module = types.SimpleNamespace(create_deep_agent=_fake_create_deep_agent)
    fake_backends_module = types.SimpleNamespace(FilesystemBackend=_FakeFilesystemBackend)
    monkeypatch.setitem(__import__("sys").modules, "deepagents", fake_module)
    monkeypatch.setitem(__import__("sys").modules, "deepagents.backends", fake_backends_module)
    monkeypatch.setattr(OCIOpenAIHelper, "get_client", staticmethod(lambda model_name, config: object()))
    monkeypatch.setattr("ai_tools.agent_runtime.runtime.time.monotonic", lambda: next(clock))

    with pytest.raises(SkillExecutionError, match="(?i)timeout exceeded") as exc:
        runtime.invoke_streamed(req, runtime._schema_for_request(req)[0], timeout_seconds=30)

    assert exc.value.code == "SKILL_EXECUTION_FAILED"
