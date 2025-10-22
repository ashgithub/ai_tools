#!/usr/bin/env python3
"""
MCP Server for proofreading text using LLM models.
Exposes HTTP endpoints (via FastAPI) for proofreading in Slack, Email, and General contexts
with configurable LLM, prompt, and rewrite settings.
"""
import sys
from typing import Optional, Callable, Annotated
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


def do_proofread(
    *,
    context_key: str,
    text: str,
    instructions: str = "",
    can_rewrite: bool = False,
    max_tokens: int = 1000,
    model: Optional[str] = None,
) -> str:
    """
    Perform the actual proofreading call.
    Returns result string or error.
    """
    try:
        client = get_oci_client()
        prompt = build_proofread_prompt(
            text=text,
            context_key=context_key,
            instructions=instructions,
            can_rewrite=can_rewrite,
        )
        model_name = model if model is not None else settings.oci.default_model
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error proofreading ({context_key}) text: {str(e)}"


def make_tool(context_key: str, max_tokens: int, description: str) -> Callable:
    """
    Generate an MCP tool for a given proofreading context.
    """
    @mcp.tool(name=f"proofread_{context_key}", description=description)
    async def tool(
        text: Annotated[str, "The text content to proofread and check for errors"],
        instructions: Annotated[str, "Optional specific instructions or focus areas for proofreading (e.g., 'check for passive voice', 'make more concise')"] = "",
        can_rewrite: Annotated[bool, "If True, allows complete rewriting of the text. If False, only provides suggestions and corrections without rewriting"] = False,
        model: Annotated[Optional[str], "LLM model name to use for proofreading. If not specified, uses the default model."] = None,
    ) -> str:
        """
        Proofread and improve text based on the specified context.
        
        Returns:
            The proofread text with corrections applied (if can_rewrite=True) or 
            suggestions for improvements (if can_rewrite=False)
        """
        return do_proofread(
            context_key=context_key,
            text=text,
            instructions=instructions,
            can_rewrite=can_rewrite,
            max_tokens=max_tokens,
            model=model,
        )
    
    return tool


# Register each context as a separate tool
make_tool(
    context_key="slack",
    max_tokens=1000,
    description="Proofread text for Slack communication. Optimized for casual, brief messages with appropriate tone for workplace chat.",
)
make_tool(
    context_key="email",
    max_tokens=2000,
    description="Proofread text for email communication. Checks grammar, tone, clarity, and professional formatting suitable for email correspondence.",
)
make_tool(
    context_key="general",
    max_tokens=2000,
    description="Proofread general text for any purpose. Provides comprehensive grammar, spelling, style, and clarity improvements.",
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
