from pathlib import Path

import pytest

from ai_tools.agent_runtime.runtime import DeepAgentRuntime
from ai_tools.utils.config import get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def runtime(monkeypatch) -> DeepAgentRuntime:
    monkeypatch.setattr(DeepAgentRuntime, "_validate_global_memory", lambda self: None)
    return DeepAgentRuntime(get_settings(), project_root=PROJECT_ROOT)


def test_normalize_stream_event(runtime):
    mode, payload = runtime.normalize_stream_event(("messages", {"messages": [{"type": "human", "content": "hi"}]}))
    assert mode == "messages"
    assert payload == {"messages": [{"type": "human", "content": "hi"}]}

    mode, payload = runtime.normalize_stream_event({"messages": [{"type": "ai", "content": "done"}]})
    assert mode == "values"
    assert payload == {"messages": [{"type": "ai", "content": "done"}]}


def test_stream_event_to_trace_lines_converts_tuple_and_plain_events(runtime):
    tuple_lines = runtime.stream_event_to_trace_lines(
        ("messages", {"messages": [{"type": "human", "content": "hello"}]})
    )
    assert tuple_lines[0] == "[trace] stream_mode -> messages"
    assert "[trace] human -> hello" in tuple_lines

    plain_lines = runtime.stream_event_to_trace_lines({"messages": []})
    assert plain_lines[0] == "[trace] stream_mode -> values"
    assert "[trace] messages -> none" in plain_lines
