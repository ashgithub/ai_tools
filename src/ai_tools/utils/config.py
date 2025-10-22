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

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import os
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from yaml import YAMLError

# --------------------------------------------------------------------------- #
# 1. Low-level typed sections
# --------------------------------------------------------------------------- #


class OCI(BaseModel, extra="forbid"):
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


class Server(BaseModel, extra="forbid"):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    transport: str = Field(default="sse")


class Prompts(BaseModel, extra="forbid"):
    base_proofread: str = Field(default="")
    rewrite_allowed: str = Field(default="")
    rewrite_forbidden: str = Field(default="")
    output_instruction: str = Field(default="")
    contexts: Dict[str, str] = Field(default_factory=dict)


class Testing(BaseModel, extra="forbid"):
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
    prompts: Prompts = Prompts()
    testing: Testing = Testing()


# --------------------------------------------------------------------------- #
# 3. Loader helper
# --------------------------------------------------------------------------- #


def _read_yaml_config() -> dict[str, Any]:
    """Locate and load ``config.yaml`` searching upward from this file.
    Supports override via AI_TOOLS_CONFIG environment variable.
    Returns empty dict if config is missing or invalid.
    """
    config_file = os.environ.get("AI_TOOLS_CONFIG", None)
    if config_file:
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file specified by AI_TOOLS_CONFIG not found: {config_file}")
        candidates = [config_path]
    else:
        # Fallback: search upward from this file for config.yaml.
        path = Path(__file__).resolve()
        candidates = [(parent / "config.yaml") for parent in (path, *path.parents)]

    for candidate in candidates:
        if candidate.exists():
            try:
                with candidate.open("r", encoding="utf-8") as fh:
                    return yaml.safe_load(fh) or {}
            except YAMLError as exc:
                raise RuntimeError(f"Error parsing config file {candidate}:\n{exc}")
    return {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a singleton :class:`Settings` instance (cached)."""
    data = _read_yaml_config()
    return Settings(**data)


__all__ = ["OCI", "Server", "Prompts", "Testing", "Settings", "get_settings"]
