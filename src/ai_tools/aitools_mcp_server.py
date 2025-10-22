#!/usr/bin/env python3
"""
MCP Server for proofreading text using LLM models.
Provides tools for proofreading text in different contexts: Slack, Email, and Normal text.
Exposed as HTTP endpoint using FastAPI.
"""

import os
import sys
from typing import Optional

import yaml
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .oci_client import OciOpenAI, OCIUserPrincipleAuth


class OCIConfig(BaseModel):
    service_endpoint: str = Field(default="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com")
    compartment_id: str = Field(default="ocid1.compartment.oc1..aaaaaaaac3cxhzoka75zaaysugzmvhm3ni3keqvikawjxvwpz26mud622owa")
    profile_name: str = Field(default="API-USER")
    default_model: str = Field(default="xai.grok-4-fast-non-reasoning")


class ServerConfig(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    transport: str = Field(default="sse")


class PromptsConfig(BaseModel):
    base_proofread: str
    rewrite_allowed: str
    rewrite_forbidden: str
    output_instruction: str
    contexts: dict[str, str]


class TestingConfig(BaseModel):
    models_file: str = Field(default="docs/llm_models.md")
    results_dir: str = Field(default="results")
    test_prompt: str = Field(default="what can you do better than any other llm in one sentence")


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    oci: OCIConfig = Field(default_factory=OCIConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    prompts: PromptsConfig
    testing: TestingConfig = Field(default_factory=TestingConfig)


# Load configuration from yaml and env
def load_config():
    config_data = {}
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        pass  # Use defaults if no config file

    return Config(**config_data)


config = load_config()

# Initialize MCP server with stateless HTTP
mcp = FastMCP("proofread-server")

# Global client instance
oci_client: Optional[OciOpenAI] = None


def get_oci_client() -> OciOpenAI:
    """Get or create OCI OpenAI client."""
    global oci_client
    if oci_client is None:
        oci_client = OciOpenAI(
            service_endpoint=config.oci.service_endpoint,
            auth=OCIUserPrincipleAuth(profile_name=config.oci.profile_name),
            compartment_id=config.oci.compartment_id,
        )
    return oci_client


def create_proofread_prompt(
    text: str, context: str, instructions: str, can_rewrite: bool
) -> str:
    """Create a proofreading prompt based on context and rewrite permissions."""

    base_prompt = config.prompts.base_proofread.format(
        context=context,
        text=text,
        instructions=instructions
    )

    if can_rewrite:
        base_prompt += config.prompts.rewrite_allowed
    else:
        base_prompt += config.prompts.rewrite_forbidden

    base_prompt += config.prompts.output_instruction

    return base_prompt


@mcp.tool()
async def proofread_slack(
    text: str, instructions: str = "", can_rewrite: bool = False
) -> str:
    """
    Proofread text for Slack communication.

    Args:
        text: The original text to proofread
        instructions: Additional instructions for proofreading
        can_rewrite: If true, allow rewriting for better clarity; if false, only fix errors

    Returns:
        Proofread text suitable for Slack
    """
    try:
        client = get_oci_client()

        context = config.prompts.contexts["slack"]
        if instructions:
            context += f" Additional notes: {instructions}"

        prompt = create_proofread_prompt(text, context, instructions, can_rewrite)

        response = client.chat.completions.create(
            model=config.oci.default_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.3,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Error proofreading Slack text: {str(e)}"


@mcp.tool()
async def proofread_email(
    text: str, instructions: str = "", can_rewrite: bool = False
) -> str:
    """
    Proofread text for email communication.

    Args:
        text: The original text to proofread
        instructions: Additional instructions for proofreading
        can_rewrite: If true, allow rewriting for better clarity; if false, only fix errors

    Returns:
        Proofread text suitable for email
    """
    try:
        client = get_oci_client()

        context = config.prompts.contexts["email"]
        if instructions:
            context += f" Additional notes: {instructions}"

        prompt = create_proofread_prompt(text, context, instructions, can_rewrite)

        response = client.chat.completions.create(
            model=config.oci.default_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Error proofreading email text: {str(e)}"


@mcp.tool()
async def proofread_text(
    text: str, instructions: str = "", can_rewrite: bool = False
) -> str:
    """
    Proofread general text.

    Args:
        text: The original text to proofread
        instructions: Additional instructions for proofreading
        can_rewrite: If true, allow rewriting for better clarity; if false, only fix errors

    Returns:
        Proofread general text
    """
    try:
        client = get_oci_client()

        context = config.prompts.contexts["general"]
        if instructions:
            context += f" Additional notes: {instructions}"

        prompt = create_proofread_prompt(text, context, instructions, can_rewrite)

        response = client.chat.completions.create(
            model=config.oci.default_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Error proofreading text: {str(e)}"


def main():
    """Main entry point for running the server."""
    # Initialize OCI client
    try:
        get_oci_client()
        print("✓ OCI OpenAI client initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize OCI client: {e}")
        sys.exit(1)

    # Run the MCP server with SSE transport (for MCP SDK compatibility)
    mcp.run(transport=config.server.transport, host=config.server.host, port=config.server.port)


if __name__ == "__main__":
    main()
