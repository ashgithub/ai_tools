"""Deep Agents runtime facade with deterministic routing and fail-fast errors."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import subprocess
from typing import Any

from pydantic import BaseModel, ValidationError

from ai_tools.agent_runtime.errors import (
    AgentRuntimeError,
    SkillExecutionError,
    SkillValidationError,
)
from ai_tools.agent_runtime.routing import resolve_skill_id
from ai_tools.agent_runtime.skills import discover_skills
from ai_tools.agent_runtime.types import (
    AgentRequest,
    AgentResponse,
    AskOutput,
    CommandsOutput,
    ExplainOutput,
    GenericTextOutput,
    ProofreadOutput,
    SkillDefinition,
)
from ai_tools.oci_openai_helper import OCIOpenAIHelper


class DeepAgentRuntime:
    """Runtime wrapper that routes UI requests to skill-driven execution."""

    def __init__(self, settings, *, project_root: Path | None = None) -> None:
        self.settings = settings
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.skills_root = self.project_root / "skills"
        self.agents_memory_path = self.project_root / "AGENTS.md"
        self.skills = discover_skills(self.skills_root)
        self.global_memory = self._load_global_memory()

    def reload(self) -> None:
        self.skills = discover_skills(self.skills_root)
        self.global_memory = self._load_global_memory()

    def _schema_for_skill(self, skill_id: str) -> tuple[type[BaseModel], str]:
        if skill_id == "commands":
            return CommandsOutput, "commands"
        if skill_id in {"proofread-general", "proofread-slack", "proofread-email"}:
            return ProofreadOutput, "proofread"
        if skill_id == "ask":
            return AskOutput, "single_line"
        if skill_id == "explain":
            return ExplainOutput, "single_line"
        return GenericTextOutput, "single_line"

    def _primary_output_from_structured(self, skill_id: str, structured: dict[str, Any]) -> str:
        if skill_id == "commands":
            alternatives = structured.get("alternatives") or []
            if not alternatives:
                return ""
            first = alternatives[0] if isinstance(alternatives[0], dict) else {}
            return str(first.get("command", "")).strip()
        if skill_id in {"proofread-general", "proofread-slack", "proofread-email"}:
            return str(structured.get("rewritten", "")).strip()
        if skill_id == "ask":
            return str(structured.get("answer", "")).strip()
        if skill_id == "explain":
            return str(structured.get("explanation", "")).strip()
        return str(structured.get("output_text", "")).strip()

    def _load_global_memory(self) -> str:
        if not self.agents_memory_path.exists():
            raise SkillValidationError(
                code="SKILL_NOT_FOUND",
                message=f"Missing AGENTS.md at {self.agents_memory_path}",
            )
        return self.agents_memory_path.read_text(encoding="utf-8").strip()

    def _get_skill(self, skill_id: str) -> SkillDefinition:
        skill = self.skills.get(skill_id)
        if not skill:
            raise SkillValidationError(
                code="SKILL_NOT_FOUND",
                message=f"Resolved skill not found: {skill_id}",
            )
        return skill

    def resolve_skill(self, request: AgentRequest) -> str:
        skill_id = resolve_skill_id(request)
        self._get_skill(skill_id)
        return skill_id

    def preview_instruction(self, request: AgentRequest) -> tuple[str, str]:
        skill_id = self.resolve_skill(request)
        skill = self._get_skill(skill_id)
        return skill_id, skill.instruction

    def preview_resolved_payload(self, request: AgentRequest, *, instruction_override: str | None = None) -> str:
        skill_id = self.resolve_skill(request)
        skill = self._get_skill(skill_id)
        return self._build_resolved_payload(
            request=request,
            skill=skill,
            instruction_override=instruction_override,
        )

    def _build_resolved_payload(
        self,
        request: AgentRequest,
        skill: SkillDefinition,
        instruction_override: str | None,
    ) -> str:
        instruction = instruction_override if instruction_override and instruction_override.strip() else skill.instruction
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "skill_id": skill.skill_id,
            "skill_name": skill.name,
            "skill_instruction": instruction,
            "global_memory": self.global_memory,
            "input_text": request.input_text,
            "options": request.options,
            "selected_model": request.selected_model,
        }
        return json.dumps(payload, indent=2)

    def invoke(self, request: AgentRequest) -> AgentResponse:
        trace: list[str] = []
        try:
            skill_id = self.resolve_skill(request)
            trace.append(f"resolved_skill={skill_id}")
            skill = self._get_skill(skill_id)

            override = request.options.get("instruction_override")
            resolved_payload = self._build_resolved_payload(
                request=request,
                skill=skill,
                instruction_override=str(override) if override is not None else None,
            )

            if skill.execution_mode == "builtin.refresh_models":
                output = self._execute_refresh_models(skill)
                trace.append("executor=builtin.refresh_models")
                return AgentResponse(
                    output_text=output,
                    skill_id=skill_id,
                    model_used=request.selected_model,
                    trace=trace,
                    resolved_payload=resolved_payload,
                    structured_output={"output_text": output},
                    primary_output=output,
                    render_kind="refresh",
                )

            schema_model, render_kind = self._schema_for_skill(skill_id)
            structured = self._execute_deep_agent(request, skill, resolved_payload, schema_model)
            primary = self._primary_output_from_structured(skill_id, structured)
            if not primary:
                raise SkillExecutionError(
                    code="SKILL_EXECUTION_FAILED",
                    message=f"Structured output missing primary value for skill={skill_id}",
                )
            trace.append("executor=deepagents")
            return AgentResponse(
                output_text=primary,
                skill_id=skill_id,
                model_used=request.selected_model,
                trace=trace,
                resolved_payload=resolved_payload,
                structured_output=structured,
                primary_output=primary,
                render_kind=render_kind,
            )
        except AgentRuntimeError:
            raise
        except Exception as exc:
            raise SkillExecutionError(
                code="SKILL_EXECUTION_FAILED",
                message=f"Unhandled skill execution failure: {exc}",
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

    def _extract_message_content(self, msg: Any) -> str:
        if isinstance(msg, dict):
            content = msg.get("content")
        else:
            content = getattr(msg, "content", None)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(p.strip() for p in parts if p and p.strip()).strip()
        return ""

    def _coerce_structured_output(
        self, result: Any, schema_model: type[BaseModel], skill_id: str
    ) -> dict[str, Any]:
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
        if isinstance(structured_raw, dict):
            try:
                return schema_model.model_validate(structured_raw).model_dump()
            except ValidationError as exc:
                raise SkillExecutionError(
                    code="SKILL_EXECUTION_FAILED",
                    message=f"Invalid structured_response for skill={skill_id}: {exc}",
                ) from exc
        if structured_raw is not None:
            try:
                return schema_model.model_validate(structured_raw).model_dump()
            except ValidationError as exc:
                raise SkillExecutionError(
                    code="SKILL_EXECUTION_FAILED",
                    message=f"Invalid structured_response for skill={skill_id}: {exc}",
                ) from exc

        # Fallback to latest message content and parse as JSON/object for a repair attempt path.
        messages = result.get("messages") if isinstance(result, dict) else None
        if isinstance(messages, list):
            for msg in reversed(messages):
                content = self._extract_message_content(msg)
                if not content:
                    continue
                try:
                    maybe_json = json.loads(content)
                    return schema_model.model_validate(maybe_json).model_dump()
                except Exception:
                    continue

        raise SkillExecutionError(
            code="SKILL_EXECUTION_FAILED",
            message=f"Missing structured_response for skill={skill_id}",
        )

    def _build_repair_prompt(self, skill_id: str, resolved_payload: str) -> str:
        return (
            f"Return ONLY valid JSON for skill '{skill_id}' that matches the configured response schema. "
            "No prose, no markdown, no code fences.\n\n"
            f"{resolved_payload}"
        )

    def _execute_deep_agent(
        self,
        request: AgentRequest,
        skill: SkillDefinition,
        resolved_payload: str,
        schema_model: type[BaseModel],
    ) -> dict[str, Any]:
        try:
            from deepagents import create_deep_agent
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

        try:
            agent = create_deep_agent(
                model=model,
                system_prompt=self.global_memory,
                memory=[str(self.agents_memory_path)],
                skills=[str(self.skills_root)],
                response_format=schema_model,
            )
            prompt = (
                f"Execute skill '{skill.skill_id}' using the following payload. "
                "Do not mention internal payload structure in the final answer.\n\n"
                f"{resolved_payload}"
            )
            last_error: Exception | None = None
            for attempt in range(2):
                current_prompt = prompt if attempt == 0 else self._build_repair_prompt(
                    skill.skill_id, resolved_payload
                )
                result = agent.invoke(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": current_prompt,
                            }
                        ]
                    }
                )
                try:
                    return self._coerce_structured_output(result, schema_model, skill.skill_id)
                except SkillExecutionError as exc:
                    last_error = exc
            raise SkillExecutionError(
                code="SKILL_EXECUTION_FAILED",
                message=f"Structured output validation failed after retry: {last_error}",
            )
        except AgentRuntimeError:
            raise
        except Exception as exc:
            raise SkillExecutionError(
                code="SKILL_EXECUTION_FAILED",
                message=f"Deep agent invocation failed: {exc}",
            ) from exc
