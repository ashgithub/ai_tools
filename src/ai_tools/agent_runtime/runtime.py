"""Deep Agents runtime facade for agentic execution with nudge-selected schemas."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import subprocess
from typing import Any

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


class DeepAgentRuntime:
    """Runtime wrapper that executes agentic Deep Agents with shared schemas."""

    def __init__(self, settings, *, project_root: Path | None = None) -> None:
        self.settings = settings
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.skills_root = self.project_root / "skills"
        self.agents_memory_path = self.project_root / "AGENTS.md"
        self.skills = discover_skills(self.skills_root)
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

    def _schema_for_request(self, request: AgentRequest) -> tuple[type[BaseModel], str]:
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
        render_kind: str,
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
    def _primary_output(render_kind: str, structured: dict[str, Any]) -> str:
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

    def _resolve_nudge_prompt(self, request: AgentRequest, render_kind: str) -> tuple[str, str]:
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
                output = self._execute_refresh_models(self._get_refresh_skill())
                trace.append("executor=builtin.refresh_models")
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
            structured = self._execute_deep_agent(request, schema_model)
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

    def _execute_refresh_models(self, skill: SkillDefinition) -> str:
        refresh_script = skill.path.parent / "scripts" / "refresh_llms.sh"
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
        if result.returncode != 0:
            raise SkillExecutionError(
                code="SKILL_EXECUTION_FAILED",
                message=(result.stderr or result.stdout or "Unknown refresh error").strip(),
            )
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

    def _execute_deep_agent(self, request: AgentRequest, schema_model: type[BaseModel]) -> dict[str, Any]:
        try:
            from deepagents import create_deep_agent
            from deepagents.backends import FilesystemBackend
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

        nudge = str(request.options.get("nudge", "")).strip()
        nudge_prompt = str(request.options.get("nudge_prompt", "")).strip()
        app_context = str(request.app_context or "").strip()
        prompt_parts = [request.input_text.strip()]
        if nudge_prompt:
            prompt_parts.append(f"Task nudge: {nudge_prompt}")
        if nudge:
            prompt_parts.append(f"Nudge: {nudge}")
        if app_context:
            prompt_parts.append(f"App context: {app_context}")
        prompt = "\n\n".join(p for p in prompt_parts if p)

        try:
            agent = create_deep_agent(
                model=model,
                backend=FilesystemBackend(root_dir=self.project_root, virtual_mode=False),
                memory=["AGENTS.md"],
                skills=["skills"],
                response_format=schema_model,
            )
            result = agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ]
                }
            )
            return self._extract_structured_response(result, schema_model)
        except AgentRuntimeError:
            raise
        except Exception as exc:
            logger.exception("Deep agent runtime exception")
            raise SkillExecutionError(
                code="SKILL_EXECUTION_FAILED",
                message=f"Deep agent invocation failed: {exc}",
            ) from exc
