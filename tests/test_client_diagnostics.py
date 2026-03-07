import types
from typing import Any, cast

from clients.multi_tool_client import (
    GUI_STREAM_MAX_EVENTS,
    GUI_STREAM_TIMEOUT_SECONDS,
    UniversalTextToolsGUI,
    choose_preferred_default_model,
    format_diagnostics_trace,
    is_openai_operation_compatible_model,
    summarize_trace_lines,
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


def test_format_diagnostics_trace_includes_summary_for_trace_lines():
    output = format_diagnostics_trace(
        [
            "[trace] stream_mode -> updates",
            "[trace] tool_call -> read_file args={}",
            "[trace] skill_load -> explain",
        ]
    )
    assert output.startswith("[summary] events=1 tool_calls=1 skill_reads=1")
    assert "tool_breakdown=read_file:1" in output


def test_summarize_trace_lines_ignores_non_trace_lines():
    assert summarize_trace_lines(["plain", "lines"]) == ""


def test_is_openai_operation_compatible_model_prefixes():
    assert is_openai_operation_compatible_model("openai.gpt-5.2") is True
    assert is_openai_operation_compatible_model("xai.grok-4") is True
    assert is_openai_operation_compatible_model("meta.llama-4-scout") is True
    assert is_openai_operation_compatible_model("cohere.command-a-03-2025") is False


def test_choose_preferred_default_model_prefers_compatible_candidates():
    models = [
        "cohere.command-a-03-2025",
        "meta.llama-4-scout-17b-16e-instruct",
        "openai.gpt-5.2",
    ]
    assert (
        choose_preferred_default_model(
            models,
            configured_default="openai.gpt-5.4",
            catalog_default="cohere.command-a-03-2025",
        )
        == "openai.gpt-5.2"
    )


def test_summarize_trace_lines_reports_tool_breakdown_counts():
    summary = summarize_trace_lines(
        [
            "[trace] stream_mode -> updates",
            "[trace] tool_call -> ls args={}",
            "[trace] tool_call -> read_file args={}",
            "[trace] tool_call -> read_file args={}",
            "[trace] skill_load -> explain",
        ]
    )
    assert summary == (
        "[summary] events=1 tool_calls=3 skill_reads=1 "
        "tool_breakdown=ls:1,read_file:2"
    )


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
        kwargs["diagnostics_callback"](["[trace] streamed 3"])
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
    assert diagnostics_calls[2] == ["[trace] streamed 1", "[trace] streamed 2", "[trace] streamed 3"]
    assert display_calls
    assert captured["timeout_seconds"] == GUI_STREAM_TIMEOUT_SECONDS
    assert captured["max_events"] == GUI_STREAM_MAX_EVENTS
    assert getattr(captured.get("request"), "input_text", None) == "prompt"
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
        kwargs["diagnostics_callback"](["[trace] live 1"])
        kwargs["diagnostics_callback"](["[trace] live 2"])
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


def test_client_handles_unsupported_operation_and_switches_model(monkeypatch):
    gui, root = _make_gui()
    _configure_failure_gui(gui)

    status_updates: list[str] = []
    busy_updates: list[bool] = []
    error_calls: list[tuple[str, str]] = []
    model_updates: list[str] = []

    gui.status_var = cast(Any, types.SimpleNamespace(set=lambda value: status_updates.append(value)))
    gui._set_busy = lambda busy: busy_updates.append(busy)
    gui._render_summary = lambda summary: None
    gui._render_diagnostics = lambda trace_lines: None
    gui._display_result = lambda response: None
    gui.available_models = [
        "cohere.command-a-03-2025",
        "meta.llama-4-scout-17b-16e-instruct",
        "openai.gpt-5.2",
    ]
    gui.initial_default_model = "cohere.command-a-03-2025"
    gui.model_var = cast(Any, types.SimpleNamespace(set=lambda value: model_updates.append(value)))

    class _Args:
        log_events = False

    gui.args = cast(Any, _Args())

    def fake_showerror(title: str, message: str):
        error_calls.append((title, message))

    def fake_invoke_streamed(request: Any, schema_model: Any, **kwargs: Any):
        raise SkillExecutionError(
            code="SKILL_EXECUTION_FAILED",
            message="Error code: 400 - {'code': '400', 'message': 'Unsupported OpenAI operation'}",
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

    assert model_updates[-1] == "openai.gpt-5.2"
    assert busy_updates == [True, False]
    assert any("unsupported model" in update.lower() for update in status_updates)
    assert error_calls
    assert "Switched to 'openai.gpt-5.2'" in error_calls[0][1]
