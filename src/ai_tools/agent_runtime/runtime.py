"""Deep Agents runtime facade for agentic execution with nudge-selected schemas."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Callable, Literal

from pydantic import BaseModel, ValidationError

from ai_tools.agent_runtime.errors import AgentRuntimeError, SkillExecutionError, SkillValidationError
from ai_tools.agent_runtime.routing import (
    COMMAND_APPS,
    EMAIL_APPS,
    SLACK_APPS,
    normalize_app_name,
    resolve_schema_family,
)
from ai_tools.agent_runtime.skills import discover_skills
from ai_tools.agent_runtime.types import (
    AgentRequest,
    AgentResponse,
    Alternatives,
    SingleText,
    SkillDefinition,
    TextPair,
)
from ai_tools.oci_openai_helper import OCIOpenAIHelper

logger = logging.getLogger(__name__)
SKILL_FILE_PATTERN = re.compile(r"skills/([^/]+)/SKILL\.md$")
RenderKind = Literal["alternatives", "text_pair", "single_text", "refresh"]


def _extract_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts).strip()
    return str(value)


def _extract_skill_name_from_path(file_path: str) -> str | None:
    skill_match = SKILL_FILE_PATTERN.search(file_path)
    return skill_match.group(1) if skill_match else None


def _shorten(value: Any, *, limit: int = 220) -> str:
    text = _extract_text(value)
    return text[:limit]


def _trace_message_lines(message: Any) -> list[str]:
    lines: list[str] = []

    def message_type(msg: Any) -> str:
        if isinstance(msg, dict):
            return str(msg.get("type", "")).lower()
        return msg.__class__.__name__.lower()

    def message_content(msg: Any) -> str:
        if isinstance(msg, dict):
            return _extract_text(msg.get("content", ""))
        return _extract_text(getattr(msg, "content", ""))

    def message_name(msg: Any) -> str:
        if isinstance(msg, dict):
            return str(msg.get("name", "unknown"))
        return str(getattr(msg, "name", "unknown"))

    def message_tool_calls(msg: Any) -> list[Any]:
        if isinstance(msg, dict):
            direct_calls = msg.get("tool_calls")
            if isinstance(direct_calls, list):
                return [tc for tc in direct_calls if isinstance(tc, dict)]

            additional_kwargs = msg.get("additional_kwargs")
            if isinstance(additional_kwargs, dict):
                nested_calls = additional_kwargs.get("tool_calls")
                if isinstance(nested_calls, list):
                    return [tc for tc in nested_calls if isinstance(tc, dict)]

        dynamic_calls = getattr(msg, "tool_calls", None)
        if isinstance(dynamic_calls, list):
            return [tc for tc in dynamic_calls if isinstance(tc, dict)]
        return []

    def tool_args(msg: Any) -> dict[str, Any]:
        if isinstance(msg, dict):
            args = msg.get("args")
            if isinstance(args, dict):
                return args

            artifact = msg.get("artifact")
            if isinstance(artifact, dict):
                return artifact

            additional_kwargs = msg.get("additional_kwargs")
            if isinstance(additional_kwargs, dict):
                nested_args = additional_kwargs.get("args")
                if isinstance(nested_args, dict):
                    return nested_args

            return {}

        dynamic_args = getattr(msg, "args", None)
        if isinstance(dynamic_args, dict):
            return dynamic_args

        artifact = getattr(msg, "artifact", None)
        if isinstance(artifact, dict):
            return artifact

        additional_kwargs = getattr(msg, "additional_kwargs", None)
        if isinstance(additional_kwargs, dict):
            nested_args = additional_kwargs.get("args")
            if isinstance(nested_args, dict):
                return nested_args

        return {}

    kind = message_type(message)
    content = message_content(message)

    if kind in {"human", "humanmessage"} and content:
        lines.append(f"[trace] human -> {_shorten(content, limit=180)}")
    if kind in {"ai", "aimessage"} and content:
        lines.append(f"[trace] ai -> {_shorten(content, limit=180)}")

    for tool_call in message_tool_calls(message):
        raw_function = tool_call.get("function")
        function_obj = raw_function if isinstance(raw_function, dict) else {}
        name = str(tool_call.get("name") or function_obj.get("name") or "unknown")
        args = tool_call.get("args", function_obj.get("arguments", {}))
        lines.append(f"[trace] tool_call -> {name} args={_shorten(args)}")

        if name == "read_file" and isinstance(args, dict):
            file_path = str(args.get("file_path") or "")
            skill_name = _extract_skill_name_from_path(file_path)
            if skill_name:
                lines.append(f"[trace] skill_load -> {skill_name}")

        if name == "task":
            lines.append("[trace] subagent_call -> task")

    if kind in {"tool", "toolmessage"}:
        tool_name = message_name(message)
        args = tool_args(message)
        file_path = str(args.get("file_path") or "")
        skill_name = _extract_skill_name_from_path(file_path)
        if tool_name == "read_file" and skill_name:
            lines.append(f"[trace] skill_load -> {skill_name}")
        lines.append(f"[trace] tool_result <- {tool_name}: {_shorten(content)}")

    return lines


def _trace_lines_for_result(result: Any) -> list[str]:
    messages: list[Any] = []
    if isinstance(result, dict):
        raw_messages = result.get("messages")
        if isinstance(raw_messages, list):
            messages = raw_messages
    elif hasattr(result, "get"):
        try:
            raw_messages = result.get("messages")
            if isinstance(raw_messages, list):
                messages = raw_messages
        except Exception:
            messages = []

    lines: list[str] = []
    if not messages:
        lines.append("[trace] messages -> none")
        return lines

    lines.append(f"[trace] message_count -> {len(messages)}")
    for message in messages:
        lines.extend(_trace_message_lines(message))
    return lines


def build_agent_prompt(request: AgentRequest) -> str:
    nudge = str(request.options.get("nudge", "")).strip().lower()
    nudge_prompt = str(request.options.get("nudge_prompt", "")).strip()
    app_context = normalize_app_name(request.app_context)

    prompt_parts = [request.input_text.strip()]
    if nudge_prompt:
        prompt_parts.append(f"Task nudge: {nudge_prompt}")
    if nudge:
        prompt_parts.append(f"Nudge: {nudge}")
    if app_context:
        prompt_parts.append(f"App context: {app_context}")
    return "\n\n".join(part for part in prompt_parts if part)


def build_agent_payload(prompt: str) -> dict[str, Any]:
    return {
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ]
    }


class DeepAgentRuntime:
    """Runtime wrapper that executes agentic Deep Agents with shared schemas."""

    def __init__(self, settings, *, project_root: Path | None = None) -> None:
        self.settings = settings
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.skills_root = self.project_root / "skills"
        self.agents_memory_path = self.skills_root/ "AGENTS.md"
        self.skills = discover_skills(self.skills_root)
        self._last_deep_agent_trace: list[str] = []
        self._validate_global_memory()

    def reload(self) -> None:
        self.skills = discover_skills(self.skills_root)
        self._validate_global_memory()

    def _validate_global_memory(self) -> None:
        if not self.agents_memory_path.exists():
            raise SkillValidationError(
                code="SKILL_NOT_FOUND",
                message=f"Missing AGENTS.md at {self.agents_memory_path}",
            )

    def _relative_project_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.project_root.resolve()))
        except ValueError:
            return str(path)

    def create_agent(self, request: AgentRequest, schema_model: type[BaseModel], *, debug: bool = False) -> Any:
        try:
            from deepagents import create_deep_agent  # pyright: ignore[reportMissingImports]
            from deepagents.backends import FilesystemBackend  # pyright: ignore[reportMissingImports]
        except Exception as exc:
            raise SkillExecutionError(
                code="SKILL_EXECUTION_FAILED",
                message=(
                    "deepagents is not installed or import failed. "
                    "Install deepagents to execute skill runtime. "
                    f"Import error: {exc}"
                ),
            ) from exc

        model_name = request.selected_model or self.settings.oci.default_model
        model = OCIOpenAIHelper.get_client(
            model_name=model_name,
            config=self.settings.model_dump(),
        )

        memory_paths = [self._relative_project_path(self.agents_memory_path)]
        skill_paths = [self._relative_project_path(self.skills_root)]
        create_kwargs: dict[str, Any] = {
            "model": model,
            "backend": FilesystemBackend(root_dir=self.project_root, virtual_mode=False),
            "memory": memory_paths,
            "skills": skill_paths,
            "response_format": schema_model,
        }
        if debug:
            create_kwargs["debug"] = True
        return create_deep_agent(**create_kwargs)

    def _schema_for_request(self, request: AgentRequest) -> tuple[type[BaseModel], RenderKind]:
        family = resolve_schema_family(request)
        if family == "alternatives":
            return Alternatives, "alternatives"
        if family == "text_pair":
            return TextPair, "text_pair"
        if family == "refresh":
            return SingleText, "refresh"
        return SingleText, "single_text"

    @staticmethod
    def _build_execution_summary(
        request: AgentRequest,
        schema_model: type[BaseModel],
        render_kind: RenderKind,
        skills_path: Path,
        memory_path: Path,
    ) -> str:
        payload = {
            "model": request.selected_model,
            "nudge": request.options.get("nudge"),
            "nudge_prompt": request.options.get("nudge_prompt"),
            "app_context": request.app_context,
            "schema": schema_model.__name__,
            "render_kind": render_kind,
            "backend": "FilesystemBackend",
            "skills_source": str(skills_path),
            "memory_source": str(memory_path),
        }
        return json.dumps(payload, indent=2)

    @staticmethod
    def _primary_output(render_kind: RenderKind, structured: dict[str, Any]) -> str:
        if render_kind == "alternatives":
            alternatives = structured.get("alternatives")
            if isinstance(alternatives, list) and alternatives:
                first = alternatives[0]
                if isinstance(first, dict):
                    return str(first.get("value", "")).strip()
            return ""
        if render_kind == "text_pair":
            return str(structured.get("rewritten", "")).strip()
        return str(structured.get("text", "")).strip()

    def _get_refresh_skill(self) -> SkillDefinition:
        skill = self.skills.get("refresh-llms")
        if not skill:
            raise SkillValidationError(
                code="SKILL_NOT_FOUND",
                message="Missing refresh-llms skill",
            )
        return skill

    def _resolve_nudge_prompt(self, request: AgentRequest, render_kind: RenderKind) -> tuple[str, str]:
        nudge_prompts = self.settings.agentic_routing.nudge_prompts
        nudge = str(request.options.get("nudge", "")).strip().lower()
        if nudge and nudge in nudge_prompts:
            return nudge_prompts[nudge], nudge

        app = normalize_app_name(request.app_context)
        if app in SLACK_APPS and "slack" in nudge_prompts:
            return nudge_prompts["slack"], "slack"
        if app in EMAIL_APPS and "email" in nudge_prompts:
            return nudge_prompts["email"], "email"
        if app in COMMAND_APPS and "commands" in nudge_prompts:
            return nudge_prompts["commands"], "commands"

        if render_kind == "text_pair" and "proofread" in nudge_prompts:
            return nudge_prompts["proofread"], "proofread"
        if render_kind == "alternatives" and "commands" in nudge_prompts:
            return nudge_prompts["commands"], "commands"
        if render_kind == "single_text" and "ask" in nudge_prompts:
            return nudge_prompts["ask"], "ask"

        return nudge_prompts.get("auto", ""), "auto"

    def preview_execution_summary(self, request: AgentRequest) -> str:
        schema_model, render_kind = self._schema_for_request(request)
        return self._build_execution_summary(
            request,
            schema_model,
            render_kind,
            self.skills_root,
            self.agents_memory_path,
        )

    def invoke(self, request: AgentRequest) -> AgentResponse:
        trace: list[str] = []
        try:
            action = str(request.options.get("action", "")).strip().lower()
            if action == "refresh_models":
                trace.append("executor=builtin.refresh_models")
                output = self._execute_refresh_models(self._get_refresh_skill(), trace=trace)
                return AgentResponse(
                    output_text=output,
                    skill_id="refresh-llms",
                    model_used=request.selected_model,
                    trace=trace,
                    execution_summary=self.preview_execution_summary(request),
                    structured_output={"text": output},
                    primary_output=output,
                    render_kind="refresh",
                )

            schema_model, render_kind = self._schema_for_request(request)
            nudge_prompt, nudge_prompt_key = self._resolve_nudge_prompt(request, render_kind)
            request.options["nudge_prompt"] = nudge_prompt
            request.options["nudge_prompt_key"] = nudge_prompt_key
            trace.append(f"schema={schema_model.__name__}")
            trace.append(f"render_kind={render_kind}")
            trace.append(f"nudge_prompt_key={nudge_prompt_key}")
            trace.append(f"model={request.selected_model or self.settings.oci.default_model}")

            structured = self._execute_deep_agent(request, schema_model)
            trace.extend(self._last_deep_agent_trace)

            primary = self._primary_output(render_kind, structured)
            if not primary:
                raise SkillExecutionError(
                    code="SKILL_EXECUTION_FAILED",
                    message=f"Structured output missing primary value for render_kind={render_kind}",
                )

            return AgentResponse(
                output_text=primary,
                skill_id="agentic",
                model_used=request.selected_model,
                trace=trace,
                execution_summary=self._build_execution_summary(
                    request,
                    schema_model,
                    render_kind,
                    self.skills_root,
                    self.agents_memory_path,
                ),
                structured_output=structured,
                primary_output=primary,
                render_kind=render_kind,
            )
        except AgentRuntimeError:
            raise
        except Exception as exc:
            logger.exception("Deep agent invocation failed")
            raise SkillExecutionError(
                code="SKILL_EXECUTION_FAILED",
                message=f"Deep agent invocation failed: {exc}",
            ) from exc

    def _execute_refresh_models(self, skill: SkillDefinition, *, trace: list[str] | None = None) -> str:
        refresh_script = skill.path.parent / "scripts" / "refresh_llms.sh"
        if trace is not None:
            trace.append(f"refresh_script={refresh_script}")

        if not refresh_script.exists():
            raise SkillExecutionError(
                code="SKILL_EXECUTION_FAILED",
                message=f"Refresh script missing: {refresh_script}",
            )

        result = subprocess.run(
            ["/bin/bash", str(refresh_script)],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )
        if trace is not None:
            trace.append(f"refresh_exit_code={result.returncode}")

        if result.returncode != 0:
            raise SkillExecutionError(
                code="SKILL_EXECUTION_FAILED",
                message=(result.stderr or result.stdout or "Unknown refresh error").strip(),
            )

        if trace is not None:
            trace.append("refresh_status=success")
        return (result.stdout or "Model cache refreshed.").strip()

    @staticmethod
    def _extract_structured_response(result: Any, schema_model: type[BaseModel]) -> dict[str, Any]:
        structured_raw: Any = None
        if isinstance(result, dict):
            structured_raw = result.get("structured_response")
        elif hasattr(result, "get"):
            try:
                structured_raw = result.get("structured_response")
            except Exception:
                structured_raw = None

        if isinstance(structured_raw, BaseModel):
            return structured_raw.model_dump()

        if structured_raw is None:
            raise SkillExecutionError(
                code="SKILL_EXECUTION_FAILED",
                message="Deep agent result missing structured_response",
            )

        try:
            return schema_model.model_validate(structured_raw).model_dump()
        except ValidationError as exc:
            raise SkillExecutionError(
                code="SKILL_EXECUTION_FAILED",
                message=f"Structured response validation failed: {exc}",
            ) from exc

    @staticmethod
    def _event_payload(event: Any) -> Any:
        if isinstance(event, tuple) and len(event) >= 2:
            return event[1]
        return event

    @classmethod
    def normalize_stream_event(cls, event: Any) -> tuple[str, Any]:
        if isinstance(event, tuple) and len(event) >= 2:
            return str(event[0]), cls._event_payload(event)
        return "values", cls._event_payload(event)

    @classmethod
    def stream_event_to_trace_lines(cls, event: Any) -> list[str]:
        mode, payload = cls.normalize_stream_event(event)
        lines = _trace_lines_for_result(payload)
        if lines == ["[trace] messages -> none"]:
            lines = _trace_message_lines(payload)
        if not lines:
            lines = ["[trace] messages -> none"]
        return [f"[trace] stream_mode -> {mode}", *lines]

    @classmethod
    def normalize_and_trace_event(cls, event: Any) -> tuple[str, Any, list[str]]:
        mode, payload = cls.normalize_stream_event(event)
        return mode, payload, cls.stream_event_to_trace_lines((mode, payload))

    def invoke_streamed(
        self,
        request: AgentRequest,
        schema_model: type[BaseModel],
        *,
        timeout_seconds: int = 30,
        max_events: int = 200,
        diagnostics_callback: Callable[[list[str]], None] | None = None,
    ) -> dict[str, Any]:
        self._last_deep_agent_trace = []
        prompt = build_agent_prompt(request)
        payload = build_agent_payload(prompt)
        started_at = time.monotonic()
        events_seen = 0

        try:
            self._last_deep_agent_trace.append("[trace] deep_agent_create -> create_deep_agent")
            agent = self.create_agent(request, schema_model, debug=True)
            try:
                stream_iter = agent.stream(payload, stream_mode="values")
            except TypeError:
                stream_iter = agent.stream(payload)

            for event in stream_iter:
                if time.monotonic() - started_at > timeout_seconds:
                    raise SkillExecutionError(
                        code="SKILL_EXECUTION_FAILED",
                        message="Stream aborted: timeout exceeded",
                    )

                events_seen += 1
                if events_seen > max_events:
                    raise SkillExecutionError(
                        code="SKILL_EXECUTION_FAILED",
                        message="Stream aborted: max-events exceeded",
                    )

                _mode, normalized_payload, event_trace_lines = self.normalize_and_trace_event(event)
                self._last_deep_agent_trace.extend(event_trace_lines)
                if diagnostics_callback is not None:
                    diagnostics_callback(list(event_trace_lines))

                try:
                    structured = self._extract_structured_response(normalized_payload, schema_model)
                except SkillExecutionError as exc:
                    if "missing structured_response" in exc.message:
                        if time.monotonic() - started_at > timeout_seconds:
                            raise SkillExecutionError(
                                code="SKILL_EXECUTION_FAILED",
                                message="Stream aborted: timeout exceeded",
                            ) from exc
                        continue
                    raise
                return structured

            raise SkillExecutionError(
                code="SKILL_EXECUTION_FAILED",
                message="Stream aborted: max-events exceeded",
            )
        except AgentRuntimeError:
            raise
        except Exception as exc:
            logger.exception("Deep agent streamed runtime exception")
            raise SkillExecutionError(
                code="SKILL_EXECUTION_FAILED",
                message=f"Deep agent streamed invocation failed: {exc}",
            ) from exc

    def _execute_deep_agent(self, request: AgentRequest, schema_model: type[BaseModel]) -> dict[str, Any]:
        self._last_deep_agent_trace = []
        prompt = build_agent_prompt(request)
        payload = build_agent_payload(prompt)

        try:
            self._last_deep_agent_trace.append("[trace] deep_agent_create -> create_deep_agent")
            agent = self.create_agent(request, schema_model)
            result = agent.invoke(payload)

            self._last_deep_agent_trace.extend(_trace_lines_for_result(result))
            return self._extract_structured_response(result, schema_model)
        except AgentRuntimeError:
            raise
        except Exception as exc:
            logger.exception("Deep agent runtime exception")
            raise SkillExecutionError(
                code="SKILL_EXECUTION_FAILED",
                message=f"Deep agent invocation failed: {exc}",
            ) from exc
