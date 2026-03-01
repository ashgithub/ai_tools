"""Custom runtime errors for deterministic agent execution."""

from __future__ import annotations


class AgentRuntimeError(RuntimeError):
    """Typed runtime error used for fail-fast behavior."""

    def __init__(self, *, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{self.code}] {self.message}")


class SkillValidationError(AgentRuntimeError):
    """Skill schema/discovery failure."""


class SkillExecutionError(AgentRuntimeError):
    """Execution failure for resolved skill."""
