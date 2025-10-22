"""Centralised configuration loader for ai_tools.

This module consolidates:
1. Pydantic data-models representing structured settings.
2. A cached ``get_settings()`` helper that merges *config.yaml* with
   environment variables (via pydantic-settings).
3. A single import location so the rest of the codebase can simply do::

       from ai_tools.utils.config import get_settings, Settings

This decouples configuration from application logic and ensures that
all modules share one in-memory Settings instance.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# --------------------------------------------------------------------------- #
# 1. Low-level typed sections
# --------------------------------------------------------------------------- #


class OCI(BaseModel):
    """OCI-related defaults."""

    service_endpoint: str = Field(
        default="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com"
    )
    compartment_id: str = Field(
        default=(
            "ocid1.compartment.oc1..aaaaaaaac3cxhzoka75zaaysugzmvhm3ni3keqvikawjxvwp"
            "z26mud622owa"
        )
    )
    profile_name: str = Field(default="API-USER")
    default_model: str = Field(default="xai.grok-4-fast-non-reasoning")


class Server(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    transport: str = Field(default="sse")


class Prompts(BaseModel):
    base_proofread: str
    rewrite_allowed: str
    rewrite_forbidden: str
    output_instruction: str
    contexts: Dict[str, str]


class Testing(BaseModel):
    models_file: str = Field(default="docs/llm_models.md")
    results_dir: str = Field(default="results")
    test_prompt: str = Field(
        default="what can you do better than any other llm in one sentence"
    )


# --------------------------------------------------------------------------- #
# 2. Aggregate Settings model
# --------------------------------------------------------------------------- #


class Settings(BaseSettings):
    """Top-level settings object used across the project."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_prefix=""
    )

    oci: OCI = OCI()
    server: Server = Server()
    prompts: Prompts
    testing: Testing = Testing()


# --------------------------------------------------------------------------- #
# 3. Loader helper
# --------------------------------------------------------------------------- #


def _read_yaml_config() -> dict[str, Any]:
    """Locate and load ``config.yaml`` searching upward from this file.

    The utils package lives under ``src/ai_tools/utils`` so the repository
    root is three levels up (``../../..``).  However, to make the function
    resilient to future layout changes we walk up the directory tree until
    we find a *config.yaml* file or exhaust parents.
    """
    path = Path(__file__).resolve()
    for parent in (path, *path.parents):
        candidate = parent / "config.yaml"
        if candidate.exists():
            with candidate.open("r", encoding="utf-8") as fh:
                return yaml.safe_load(fh) or {}
    # Nothing found → return empty dict so Settings falls back to defaults
    return {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a singleton :class:`Settings` instance (cached)."""
    data = _read_yaml_config()
    return Settings(**data)


# convenient re-export
__all__ = ["OCI", "Server", "Prompts", "Testing", "Settings", "get_settings"]
