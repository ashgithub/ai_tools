#!/usr/bin/env python3
"""
Tech Lookup MCP Server: Exposes tools to look up Linux/macOS commands and explain technical content.
"""
import sys
from typing import Optional, Callable, Annotated, List
from fastmcp import FastMCP
from ai_tools.oci_openai_helper import OCIOpenAIHelper
from ai_tools.utils.config import get_settings
from envyaml import EnvYAML

settings = get_settings()
mcp = FastMCP("techlookup-server")
_oci_client = None


def get_oci_client():
    global _oci_client
    if _oci_client is None:
        # Load config with EnvYAML for the helper
        config = EnvYAML("config.yaml")
        _oci_client = OCIOpenAIHelper.get_client(
            model_name=settings.oci.default_model,
            config=config,
        )
    return _oci_client


def llm_ask(prompt: str, max_tokens: int = 512, model: Optional[str] = None) -> str:
    try:
        client = get_oci_client()
        model_name = model if model else settings.oci.default_model
        messages = [{"role": "user", "content": prompt}]
        response = client.invoke(
            messages,
            max_tokens=max_tokens,
            temperature=0.2,
        )
        return response.content.strip()
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool(
    name="list_linux_commands", 
    description="Return 1-3 Linux or macOS command-line alternatives to accomplish a given task from a query string. Parameter 'os' may be 'linux' or 'macos'."
)
async def list_linux_commands(
    query: Annotated[str, "The task to accomplish or plain language query"],
    os: Annotated[str, "'macos' (default) or 'linux'"] = "macos",
    model: Annotated[Optional[str], "LLM model name to use. If not specified, uses the default model."] = None,
) -> List[str]:
    """
    Look up 1-3 shell command alternatives for a task, based on OS.
    Returns a list of string commands.
    """
    os_str = os.lower()
    if os_str not in ("linux", "macos"):
        os_str = "macos"
    prompt = (
        f"List 1 to 3 alternative command-line commands to accomplish the following task on {os_str}:\n"
        f"Task: {query}\n"
        "For each alternative, return only the shell command (no explanation, no comments). List as bullet points."
    )
    result = llm_ask(prompt, max_tokens=256, model=model)
    # Try to convert bullet points or newlines to list:
    lines = []
    for line in result.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('- '):
            line = line[2:]
        elif line[0:1] in ('1', '2', '3') and line[1] in ('.',')'):
            line = line[2:].strip()
        lines.append(line)
    if not lines and result:
        lines = [result]
    return lines


@mcp.tool(
    name="explain_tech_text",
    description="Explain technical or command-line content in an easy to understand paragraph."
)
async def explain_tech_text(
    text: Annotated[str, "The technical or shell command text to explain"],
    model: Annotated[Optional[str], "LLM model name to use. If not specified, uses the default model."] = None,
) -> str:
    """
    Explain content in an easy to understand paragraph.
    """
    prompt = (
        "Explain the following technical content in an easy to understand paragraph, for a general audience with some computer experience but not an expert.\n\n"
        f"Content:\n{text}\n"
    )
    return llm_ask(prompt, max_tokens=400, model=model)


def main():
    try:
        get_oci_client()
        print("✓ OCI OpenAI client initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize OCI client: {e}")
        sys.exit(1)
    server_cfg = settings.servers.techtool
    mcp.run(
        transport=server_cfg.transport,
        host=server_cfg.host,
        port=server_cfg.port,
    )


if __name__ == "__main__":
    main()
