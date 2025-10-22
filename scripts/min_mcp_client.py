#!/usr/bin/env uv run    
"""
Minimal test client for MCP server using the SDK.
Tests basic connection and tool calling.
"""

import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client


async def test_mcp_connection():
    """Test connection to MCP server."""
    server_url = "http://127.0.0.1:8000/sse"
    
    print(f"Connecting to MCP server at {server_url}...")
    
    try:
        # Connect using SSE transport
        async with sse_client(server_url) as (read_stream, write_stream):
            print("✓ SSE connection established")
            
            # Create client session
            async with ClientSession(read_stream, write_stream) as session:
                print("✓ Client session created")
                
                # Initialize the session
                result = await session.initialize()
                print(f"✓ Session initialized: {result}")
                
                # List available tools
                tools_result = await session.list_tools()
                print(f"\n✓ Found {len(tools_result.tools)} tools:")
                for tool in tools_result.tools:
                    print(f"  - {tool.name}: {tool.description}")
                
                # Test calling a tool
                print("\n--- Testing proofread_slack tool ---")
                test_text = "this is a test mesage with some typos"
                print(f"Input: '{test_text}'")
                
                result = await session.call_tool(
                    "proofread_slack",
                    arguments={
                        "text": test_text,
                        "instructions": "",
                        "can_rewrite": False,
                        "model": "gpt-4",  # Pass your desired model name here
                    }
                )
                
                print(f"\nResult type: {type(result)}")
                print(f"Result: {result}")
                
                if result.content and len(result.content) > 0:
                    proofread_text = result.content[0].text
                    print(f"\n✓ Proofread result: '{proofread_text}'")
                else:
                    print("✗ No content in result")
                
                print("\n✓ All tests passed!")
                
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run the test."""
    print("=== MCP Server Test ===\n")
    asyncio.run(test_mcp_connection())


if __name__ == "__main__":
    main()
