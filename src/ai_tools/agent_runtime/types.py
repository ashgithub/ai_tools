"""Runtime contracts for the Deep Agents execution layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class SingleText(BaseModel):
    text: str


class TextPair(BaseModel):
    corrected: str
    rewritten: str


class Alternative(BaseModel):
    value: str
    explanation: str


class Alternatives(BaseModel):
    alternatives: list[Alternative] = Field(min_length=1, max_length=3)


@dataclass(slots=True)
class AgentRequest:
    input_text: str
    ui_tab: str
    app_context: str | None = None
    options: dict[str, Any] = field(default_factory=dict)
    selected_model: str | None = None


@dataclass(slots=True)
class AgentResponse:
    output_text: str
    skill_id: str
    model_used: str | None
    trace: list[str] = field(default_factory=list)
    error: str | None = None
    execution_summary: str | None = None
    structured_output: dict[str, Any] | None = None
    primary_output: str = ""
    render_kind: Literal["alternatives", "text_pair", "single_text", "refresh"] = "single_text"


@dataclass(slots=True)
class SkillDefinition:
    skill_id: str
    path: Path
    name: str
    description: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    model_policy: dict[str, Any]
    ui_tabs: list[str]
    execution_mode: str
    instruction: str
