#!/usr/bin/env uv run    
"""
Minimal test client for MCP server using the SDK.
Tests basic connection and tool calling.
"""

import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
from ai_tools.utils.config import get_settings


async def test_proofread_server(settings):
    print("\n=== Testing Proofread MCP Server ===")
    server_cfg = settings.servers.proofread
    server_url = f"http://{server_cfg.host}:{server_cfg.port}/{server_cfg.transport}"
    try:
        async with sse_client(server_url) as (read_stream, write_stream):
            print(f"✓ Connected to Proofread server at {server_url}")
            async with ClientSession(read_stream, write_stream) as session:
                print("✓ Client session created")
                result = await session.initialize()
                print(f"✓ Session initialized: {result}")
                tools_result = await session.list_tools()
                print(f"\n✓ Found {len(tools_result.tools)} tools:")
                for tool in tools_result.tools:
                    print(f"  - {tool.name}: {tool.description}")
                print("\n--- Testing proofread_slack tool ---")
                test_text = "this is a test mesage with some typos"
                print(f"Input: '{test_text}'")
                result = await session.call_tool(
                    "proofread_slack",
                    arguments={
                        "text": test_text,
                        "instructions": "",
                        "can_rewrite": False,
                        "model":  "meta.llama-4-scout-17b-16e-instruct",
                    }
                )
                print(f"\nResult: {result}")
                if result.content and len(result.content) > 0:
                    proofread_text = result.content[0].text
                    print(f"\n✓ Proofread result: '{proofread_text}'")
                else:
                    print("✗ No content in result")
    except Exception as e:
        print(f"✗ Error with Proofread server: {e}")
        import traceback
        traceback.print_exc()


async def test_techlookup_server(settings):
    print("\n=== Testing TechLookup MCP Server ===")
    server_cfg = settings.servers.techtool
    server_url = f"http://{server_cfg.host}:{server_cfg.port}/{server_cfg.transport}"
    try:
        async with sse_client(server_url) as (read_stream, write_stream):
            print(f"✓ Connected to TechLookup server at {server_url}")
            async with ClientSession(read_stream, write_stream) as session:
                print("✓ Client session created")
                result = await session.initialize()
                print(f"✓ Session initialized: {result}")
                tools_result = await session.list_tools()
                print(f"\n✓ Found {len(tools_result.tools)} tools:")
                for tool in tools_result.tools:
                    print(f"  - {tool.name}: {tool.description}")

                print("\n--- Testing list_linux_commands tool ---")
                query = "List all files containing 'TODO' recursively"
                print(f"query: {query}")
                result = await session.call_tool(
                    "list_linux_commands",
                    arguments={
                        "query": query,
                        "os": "linux",
                        "model": "meta.llama-4-scout-17b-16e-instruct"
                    }
                )
                print(f"\nResult: {result}")
                if result.content and len(result.content) > 0:
                    print("\n✓ Command alternatives:")
                    for c in result.content[0].value:
                        print("  -", c)
                else:
                    print("✗ No command output in result")

                print("\n--- Testing explain_tech_text tool ---")
                tech_text = "find . -type f -exec grep -l 'TODO' {} +"
                print(f"tech_text: {tech_text}")
                result = await session.call_tool(
                    "explain_tech_text",
                    arguments={
                        "text": tech_text,
                        "model": "meta.llama-4-scout-17b-16e-instruct"
                    }
                )
                print(f"\nResult: {result}")
                if result.content and len(result.content) > 0:
                    print("\n✓ Explanation:", result.content[0].text)
                else:
                    print("✗ No explanation output in result")
    except Exception as e:
        print(f"✗ Error with TechLookup server: {e}")
        import traceback
        traceback.print_exc()

async def test_summarization_server(settings):
    print("\n=== Testing Summarization MCP Server ===")
    server_cfg = settings.servers.summarization
    server_url = f"http://{server_cfg.host}:{server_cfg.port}/{server_cfg.transport}"
    try:
        async with sse_client(server_url) as (read_stream, write_stream):
            print(f"✓ Connected to Summarization server at {server_url}")
            async with ClientSession(read_stream, write_stream) as session:
                print("✓ Client session created")
                result = await session.initialize()
                print(f"✓ Session initialized: {result}")
                tools_result = await session.list_tools()
                print(f"\n✓ Found {len(tools_result.tools)} tools:")
                for tool in tools_result.tools:
                    print(f"  - {tool.name}: {tool.description}")
                # If summarization tool exists, run a sample invocation (if not present, skip)
                found_tool = any(t.name == "summarize_text" for t in tools_result.tools)
                if found_tool:
                    print("\n--- Testing summarize_text tool ---")
                    input_text = "This is a long report that needs to be summarized for easier reading."
                    result = await session.call_tool(
                        "summarize_text",
                        arguments={
                            "text": input_text,
                            "model": "meta.llama-4-scout-17b-16e-instruct"
                        }
                    )
                    print(f"\nResult: {result}")
                    if result.content and len(result.content) > 0:
                        print("\n✓ Summarization:", result.content[0].text)
                    else:
                        print("✗ No summarization output in result")
                else:
                    print("No summarize_text tool available on server.")
    except Exception as e:
        print(f"✗ Error with Summarization server: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Run the test."""
    print("=== MCP Multi-Server Test ===\n")
    settings = get_settings()
    asyncio.run(run_all(settings))

async def run_all(settings):
    await test_proofread_server(settings)
    await test_techlookup_server(settings)
    await test_summarization_server(settings)
    print("\n✓ All tests completed.")

if __name__ == "__main__":
    main()
