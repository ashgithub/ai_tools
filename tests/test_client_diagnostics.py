import types
from typing import Any, cast

from clients.multi_tool_client import (
    GUI_STREAM_MAX_EVENTS,
    GUI_STREAM_TIMEOUT_SECONDS,
    UniversalTextToolsGUI,
    format_diagnostics_trace,
)
from ai_tools.agent_runtime import AgentResponse
from ai_tools.agent_runtime.errors import SkillExecutionError


class _FakeAfterRoot:
    def __init__(self):
        self.calls: list[tuple[int, object]] = []

    def after(self, delay: int, callback: Any):
        self.calls.append((delay, callback))
        callback()


def _make_gui() -> tuple[UniversalTextToolsGUI, _FakeAfterRoot]:
    gui = cast(Any, UniversalTextToolsGUI.__new__(UniversalTextToolsGUI))
    root = _FakeAfterRoot()
    gui.root = cast(Any, root)
    gui.is_busy = False
    return gui, root


def test_format_diagnostics_trace_with_lines():
    output = format_diagnostics_trace(["a", "b"])
    assert output == "a\nb"


def test_format_diagnostics_trace_empty():
    output = format_diagnostics_trace([])
    assert output == "No diagnostics captured for this run."


def test_client_receives_diagnostics(monkeypatch):
    gui, root = _make_gui()
    gui.agent_runtime = cast(Any, types.SimpleNamespace(
        preview_execution_summary=lambda _request: "summary",
        _schema_for_request=lambda _request: (object(), "single_text"),
        _primary_output=lambda _render_kind, structured: structured["text"],
        _last_deep_agent_trace=["[trace] final"],
    ))
    gui.status_var = cast(Any, types.SimpleNamespace(set=lambda value: None))
    gui._set_busy = lambda busy: None
    gui._build_request = lambda text: cast(Any, types.SimpleNamespace(selected_model="demo-model", input_text=text))
    gui.input_text = cast(Any, types.SimpleNamespace(get=lambda *_args: "prompt"))

    summary_calls: list[str] = []
    diagnostics_calls: list[list[str]] = []
    display_calls: list[AgentResponse] = []
    gui._render_summary = lambda summary: summary_calls.append(summary)
    gui._render_diagnostics = lambda trace_lines: diagnostics_calls.append(list(trace_lines or []))
    gui._display_result = lambda response: display_calls.append(response)

    captured: dict[str, object] = {}

    def fake_invoke_streamed(request: Any, schema_model: Any, **kwargs: Any):
        captured["request"] = request
        captured["schema_model"] = schema_model
        captured.update(kwargs)
        kwargs["diagnostics_callback"](["[trace] streamed 1", "[trace] streamed 2"])
        return {"text": "done"}

    gui.agent_runtime.invoke_streamed = fake_invoke_streamed

    class _ImmediateThread:
        def __init__(self, *, target: Any, daemon: Any):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    monkeypatch.setattr("clients.multi_tool_client.threading.Thread", _ImmediateThread)

    gui._run_action()

    assert summary_calls == ["summary"]
    assert diagnostics_calls[0] == ["[trace] request queued"]
    assert diagnostics_calls[1] == ["[trace] streamed 1", "[trace] streamed 2"]
    assert display_calls
    assert captured["timeout_seconds"] == GUI_STREAM_TIMEOUT_SECONDS
    assert captured["max_events"] == GUI_STREAM_MAX_EVENTS
    assert captured["request"].input_text == "prompt"
    assert root.calls
    assert all(delay == 0 for delay, _ in root.calls)


def test_client_final_result_callback(monkeypatch):
    gui, root = _make_gui()
    gui.agent_runtime = cast(Any, types.SimpleNamespace(
        preview_execution_summary=lambda _request: "summary",
        _schema_for_request=lambda _request: (object(), "single_text"),
        _primary_output=lambda _render_kind, structured: structured["text"],
        _last_deep_agent_trace=["[trace] final result"],
    ))
    status_updates: list[str] = []
    busy_updates: list[bool] = []
    display_calls: list[AgentResponse] = []
    gui.status_var = cast(Any, types.SimpleNamespace(set=lambda value: status_updates.append(value)))
    gui._set_busy = lambda busy: busy_updates.append(busy)
    gui._build_request = lambda text: cast(Any, types.SimpleNamespace(selected_model="demo-model", input_text=text))
    gui.input_text = cast(Any, types.SimpleNamespace(get=lambda *_args: "prompt"))
    gui._render_summary = lambda summary: None
    gui._render_diagnostics = lambda trace_lines: None
    gui._display_result = lambda response: display_calls.append(response)

    def fake_invoke_streamed(request: Any, schema_model: Any, **kwargs: Any):
        kwargs["diagnostics_callback"](["[trace] live"])
        return {"text": "final output"}

    gui.agent_runtime.invoke_streamed = fake_invoke_streamed

    class _ImmediateThread:
        def __init__(self, *, target: Any, daemon: Any):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    monkeypatch.setattr("clients.multi_tool_client.threading.Thread", _ImmediateThread)

    gui._run_action()

    assert len(display_calls) == 1
    response = display_calls[0]
    assert response.output_text == "final output"
    assert response.primary_output == "final output"
    assert response.structured_output == {"text": "final output"}
    assert response.render_kind == "single_text"
    assert response.trace == ["[trace] final result"]
    assert any(update.startswith("Response ready (") for update in status_updates)
    assert busy_updates == [True, False]
    assert root.calls
    assert all(delay == 0 for delay, _ in root.calls)


def _configure_failure_gui(gui: UniversalTextToolsGUI):
    gui.agent_runtime = cast(Any, types.SimpleNamespace(
        preview_execution_summary=lambda _request: "summary",
        _schema_for_request=lambda _request: (object(), "single_text"),
        _primary_output=lambda _render_kind, structured: structured["text"],
        _last_deep_agent_trace=["[trace] retained"],
    ))
    gui._build_request = lambda text: cast(Any, types.SimpleNamespace(selected_model="demo-model", input_text=text))
    gui.input_text = cast(Any, types.SimpleNamespace(get=lambda *_args: "prompt"))
    gui.run_button = cast(Any, types.SimpleNamespace(config=lambda **_kwargs: None))
    gui.done_button = cast(Any, types.SimpleNamespace(config=lambda **_kwargs: None))
    gui.refresh_button = cast(Any, types.SimpleNamespace(config=lambda **_kwargs: None))
    gui.model_combo = cast(Any, types.SimpleNamespace(config=lambda **_kwargs: None))
    gui.nudge_combo = cast(Any, types.SimpleNamespace(config=lambda **_kwargs: None))


def test_client_handles_timeout_failure(monkeypatch):
    gui, root = _make_gui()
    _configure_failure_gui(gui)

    status_updates: list[str] = []
    busy_updates: list[bool] = []
    diagnostics_calls: list[list[str]] = []
    error_calls: list[tuple[str, str]] = []

    gui.status_var = cast(Any, types.SimpleNamespace(set=lambda value: status_updates.append(value)))
    gui._set_busy = lambda busy: busy_updates.append(busy)
    gui._render_summary = lambda summary: None
    gui._render_diagnostics = lambda trace_lines: diagnostics_calls.append(list(trace_lines or []))
    gui._display_result = lambda response: None

    def fake_showerror(title: str, message: str):
        error_calls.append((title, message))

    def fake_invoke_streamed(request: Any, schema_model: Any, **kwargs: Any):
        kwargs["diagnostics_callback"](["[trace] partial diagnostics"])
        raise SkillExecutionError(
            code="SKILL_EXECUTION_FAILED",
            message="Stream aborted: timeout exceeded",
        )

    gui.agent_runtime.invoke_streamed = fake_invoke_streamed

    class _ImmediateThread:
        def __init__(self, *, target: Any, daemon: Any):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    monkeypatch.setattr("clients.multi_tool_client.threading.Thread", _ImmediateThread)
    monkeypatch.setattr("clients.multi_tool_client.messagebox.showerror", fake_showerror)

    gui._run_action()

    assert diagnostics_calls == [["[trace] request queued"], ["[trace] partial diagnostics"]]
    assert busy_updates == [True, False]
    assert any("timeout" in update.lower() for update in status_updates)
    assert error_calls == [("Error", "SKILL_EXECUTION_FAILED: Stream aborted: timeout exceeded")]
    assert root.calls
    assert all(delay == 0 for delay, _ in root.calls)


def test_client_handles_max_events_failure(monkeypatch):
    gui, root = _make_gui()
    _configure_failure_gui(gui)

    status_updates: list[str] = []
    busy_updates: list[bool] = []
    diagnostics_calls: list[list[str]] = []
    error_calls: list[tuple[str, str]] = []

    gui.status_var = cast(Any, types.SimpleNamespace(set=lambda value: status_updates.append(value)))
    gui._set_busy = lambda busy: busy_updates.append(busy)
    gui._render_summary = lambda summary: None
    gui._render_diagnostics = lambda trace_lines: diagnostics_calls.append(list(trace_lines or []))
    gui._display_result = lambda response: None

    def fake_showerror(title: str, message: str):
        error_calls.append((title, message))

    def fake_invoke_streamed(request: Any, schema_model: Any, **kwargs: Any):
        kwargs["diagnostics_callback"](["[trace] partial diagnostics"])
        raise SkillExecutionError(
            code="SKILL_EXECUTION_FAILED",
            message="Stream aborted: max-events exceeded",
        )

    gui.agent_runtime.invoke_streamed = fake_invoke_streamed

    class _ImmediateThread:
        def __init__(self, *, target: Any, daemon: Any):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    monkeypatch.setattr("clients.multi_tool_client.threading.Thread", _ImmediateThread)
    monkeypatch.setattr("clients.multi_tool_client.messagebox.showerror", fake_showerror)

    gui._run_action()

    assert diagnostics_calls == [["[trace] request queued"], ["[trace] partial diagnostics"]]
    assert busy_updates == [True, False]
    assert any("max-events" in update.lower() for update in status_updates)
    assert error_calls == [("Error", "SKILL_EXECUTION_FAILED: Stream aborted: max-events exceeded")]
    assert root.calls
    assert all(delay == 0 for delay, _ in root.calls)
