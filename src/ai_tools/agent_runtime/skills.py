"""Skill discovery and validation for skills/*/SKILL.md."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError

from ai_tools.agent_runtime.errors import SkillValidationError
from ai_tools.agent_runtime.types import SkillDefinition


class SkillFrontmatter(BaseModel, extra="forbid"):
    name: str
    description: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    model_policy: dict[str, Any] = Field(default_factory=dict)
    ui_tabs: list[str] = Field(default_factory=list)
    execution_mode: str = Field(default="llm")


def _split_frontmatter(text: str, file_path: Path) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        raise SkillValidationError(
            code="SKILL_INVALID_SCHEMA",
            message=f"{file_path}: missing YAML frontmatter start delimiter",
        )

    end_index = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_index = idx
            break
    if end_index is None:
        raise SkillValidationError(
            code="SKILL_INVALID_SCHEMA",
            message=f"{file_path}: missing YAML frontmatter end delimiter",
        )

    raw_frontmatter = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).strip()

    try:
        parsed = yaml.safe_load(raw_frontmatter) or {}
    except yaml.YAMLError as exc:
        raise SkillValidationError(
            code="SKILL_INVALID_SCHEMA",
            message=f"{file_path}: invalid YAML frontmatter: {exc}",
        ) from exc
    if not isinstance(parsed, dict):
        raise SkillValidationError(
            code="SKILL_INVALID_SCHEMA",
            message=f"{file_path}: frontmatter must be a mapping",
        )
    if not body:
        raise SkillValidationError(
            code="SKILL_INVALID_SCHEMA",
            message=f"{file_path}: instruction body is empty",
        )

    return parsed, body


def load_skill(skill_dir: Path) -> SkillDefinition:
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        raise SkillValidationError(
            code="SKILL_NOT_FOUND",
            message=f"Missing SKILL.md in {skill_dir}",
        )

    text = skill_file.read_text(encoding="utf-8")
    parsed, body = _split_frontmatter(text, skill_file)

    try:
        meta = SkillFrontmatter.model_validate(parsed)
    except ValidationError as exc:
        raise SkillValidationError(
            code="SKILL_INVALID_SCHEMA",
            message=f"{skill_file}: frontmatter validation failed: {exc}",
        ) from exc

    return SkillDefinition(
        skill_id=skill_dir.name,
        path=skill_file,
        name=meta.name,
        description=meta.description,
        inputs=meta.inputs,
        outputs=meta.outputs,
        model_policy=meta.model_policy,
        ui_tabs=meta.ui_tabs,
        execution_mode=meta.execution_mode,
        instruction=body,
    )


def discover_skills(skills_root: Path) -> dict[str, SkillDefinition]:
    if not skills_root.exists() or not skills_root.is_dir():
        raise SkillValidationError(
            code="SKILL_NOT_FOUND",
            message=f"Skills directory not found: {skills_root}",
        )

    registry: dict[str, SkillDefinition] = {}
    for child in sorted(skills_root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        skill = load_skill(child)
        if skill.skill_id in registry:
            raise SkillValidationError(
                code="SKILL_INVALID_SCHEMA",
                message=f"Duplicate skill id discovered: {skill.skill_id}",
            )
        registry[skill.skill_id] = skill

    if not registry:
        raise SkillValidationError(
            code="SKILL_NOT_FOUND",
            message=f"No skills discovered under {skills_root}",
        )

    return registry
