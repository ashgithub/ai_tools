#!/usr/bin/env python3
"""
MCP Server for proofreading text using LLM models.
Provides tools for proofreading text in different contexts: Slack, Email, and Normal text.
Exposed as HTTP endpoint using FastAPI.
"""

import sys
from typing import Optional

from fastmcp import FastMCP

from ai_tools.oci_client import OciOpenAI, OCIUserPrincipleAuth
from ai_tools.utils.config import get_settings
from ai_tools.utils.prompts import build_proofread_prompt

settings = get_settings()
mcp = FastMCP("proofread-server")
_oci_client: Optional[OciOpenAI] = None

def get_oci_client() -> OciOpenAI:
    global _oci_client
    if _oci_client is None:
        _oci_client = OciOpenAI(
            service_endpoint=settings.oci.service_endpoint,
            auth=OCIUserPrincipleAuth(profile_name=settings.oci.profile_name),
            compartment_id=settings.oci.compartment_id,
        )
    return _oci_client

def _do_proofread(context_key: str, text: str, instructions: str, can_rewrite: bool, max_tokens: int) -> str:
    try:
        client = get_oci_client()
        prompt = build_proofread_prompt(
            text=text,
            context_key=context_key,
            instructions=instructions,
            can_rewrite=can_rewrite,
        )
        response = client.chat.completions.create(
            model=settings.oci.default_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error proofreading ({context_key}) text: {str(e)}"

@mcp.tool()
async def proofread_slack(
    text: str, instructions: str = "", can_rewrite: bool = False
) -> str:
    """
    Proofread text for Slack communication.
    """
    return _do_proofread(
        context_key="slack",
        text=text,
        instructions=instructions,
        can_rewrite=can_rewrite,
        max_tokens=1000,
    )

@mcp.tool()
async def proofread_email(
    text: str, instructions: str = "", can_rewrite: bool = False
) -> str:
    """
    Proofread text for email communication.
    """
    return _do_proofread(
        context_key="email",
        text=text,
        instructions=instructions,
        can_rewrite=can_rewrite,
        max_tokens=2000,
    )

@mcp.tool()
async def proofread_text(
    text: str, instructions: str = "", can_rewrite: bool = False
) -> str:
    """
    Proofread general text.
    """
    return _do_proofread(
        context_key="general",
        text=text,
        instructions=instructions,
        can_rewrite=can_rewrite,
        max_tokens=2000,
    )

def main():
    try:
        get_oci_client()
        print("✓ OCI OpenAI client initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize OCI client: {e}")
        sys.exit(1)

    mcp.run(
        transport=settings.server.transport,
        host=settings.server.host,
        port=settings.server.port,
    )

if __name__ == "__main__":
    main()
