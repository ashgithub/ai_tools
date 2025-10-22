#!/usr/bin/env uv run    
"""
Minimal, DRY test client for all MCP servers using the SDK.
Connects to all servers from config, lists tools, and runs sample calls.
"""

import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
from ai_tools.utils.config import get_settings

async def exercise_server(
    name, server_cfg, test_calls: list
):
    """
    Generic MCP server tester.
    - name: human readable
    - server_cfg: config object with .host/.port/.transport
    - test_calls: list of dicts: {'tool': ..., 'arguments': ..., 'result_printer': ...}
    """
    print(f"\n=== Testing {name} MCP Server ===")
    server_url = f"http://{server_cfg.host}:{server_cfg.port}/{server_cfg.transport}"
    try:
        async with sse_client(server_url) as (read_stream, write_stream):
            print(f"✓ Connected to {name} server at {server_url}")
            async with ClientSession(read_stream, write_stream) as session:
                print("✓ Client session created")
                result = await session.initialize()
                print(f"✓ Session initialized: {result}")
                tools_result = await session.list_tools()
                print(f"\n✓ Found {len(tools_result.tools)} tools:")
                for tool in tools_result.tools:
                    print(f"  - {tool.name}: {tool.description}")
                for call in test_calls:
                    print(call.get("label", f"\n--- Testing {call['tool']} tool ---"))
                    arguments = call["arguments"]
                    result = await session.call_tool(call["tool"], arguments=arguments)
                    if "result_printer" in call:
                        call["result_printer"](result)
                    else:
                        print(f"Result: {result}")
    except Exception as e:
        print(f"✗ Error with {name} server: {e}")
        import traceback ; traceback.print_exc()

def print_proofread_result(result):
    print(f"\nResult: {result}")
    if result.content and len(result.content) > 0:
        proofread_text = result.content[0].text
        print(f"\n✓ Proofread result: '{proofread_text}'")
    else:
        print("✗ No content in result")

def print_techlookup_commands(result):
    print(f"\nResult: {result}")
    if result.content and len(result.content) > 0:
        print("\n✓ Command alternatives:")
        for c in result.content[0].value:
            print("  -", c)
    else:
        print("✗ No command output in result")

def print_explanation(result):
    print(f"\nResult: {result}")
    if result.content and len(result.content) > 0:
        print("\n✓ Explanation:", result.content[0].text)
    else:
        print("✗ No explanation output in result")

def print_summarization(result):
    print(f"\nResult: {result}")
    if result.content and len(result.content) > 0:
        print("\n✓ Summarization:", result.content[0].text)
    else:
        print("✗ No summarization output in result")

async def run_all(settings):
    await exercise_server(
        "Proofread", settings.servers.proofread, [
            {
                'tool': 'proofread_slack',
                'label': '\n--- Testing proofread_slack tool ---',
                'arguments': {
                    "text": "this is a test mesage with some typos",
                    "instructions": "",
                    "can_rewrite": False,
                    "model":  "meta.llama-4-scout-17b-16e-instruct",
                },
                'result_printer': print_proofread_result
            },
        ]
    )
    await exercise_server(
        "TechLookup", settings.servers.techtool, [
            {
                'tool': 'list_linux_commands',
                'label': '\n--- Testing list_linux_commands tool ---',
                'arguments': {
                    "query": "List all files containing 'TODO' recursively",
                    "os": "linux",
                    "model": "meta.llama-4-scout-17b-16e-instruct"
                },
                'result_printer': print_techlookup_commands
            },
            {
                'tool': 'explain_tech_text',
                'label': '\n--- Testing explain_tech_text tool ---',
                'arguments': {
                    "text": "find . -type f -exec grep -l 'TODO' {} +",
                    "model": "meta.llama-4-scout-17b-16e-instruct"
                },
                'result_printer': print_explanation
            },
        ]
    )
    await exercise_server(
        "Summarization", settings.servers.summarization, [
            {
                'tool': 'summarize_text',
                'label': '\n--- Testing summarize_text tool ---',
                'arguments': {
                    "text": "This is a long report that needs to be summarized for easier reading.",
                    "model": "meta.llama-4-scout-17b-16e-instruct"
                },
                'result_printer': print_summarization
            }
        ]
    )
    print("\n✓ All tests completed.")

def main():
    print("=== MCP Multi-Server Test ===\n")
    settings = get_settings()
    asyncio.run(run_all(settings))

if __name__ == "__main__":
    main()
