# AI Tools Usage Guide

This guide provides detailed usage instructions for all components of the AI Tools project.

## Table of Contents

- [Server Management](#server-management)
- [Client Applications](#client-applications)
- [API Integration](#api-integration)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Server Management

### Starting Individual Servers

```bash
# Proofreading server (port 8000)
uv run proofread-server

# Tech lookup server (port 8001)
uv run techlookup-server
```

### Server Endpoints

Each server exposes:
- **MCP endpoint**: `POST /mcp` - Main JSON-RPC API
- **Health check**: `GET /health` - Server status
- **SSE endpoint**: `GET /mcp` - Server-sent events for streaming

### Checking Server Status

```bash
# Test proofreading server
curl http://localhost:8000/health

# Test tech lookup server
curl http://localhost:8001/health
```

## Client Applications

### Hello World Demo

Simple demonstration of OCI client connectivity:

```bash
uv run hello-world
```

**Output:**
```
Response from OCI Generative AI:
Hello there, world! 😊
```

### Model Benchmarking

Test and compare multiple AI models:

```bash
uv run benchmark-models
```

This will:
- Test all models listed in `docs/llm_models.md`
- Measure response times
- Generate performance reports in `output/benchmarks/`
- Display results in terminal

### MCP Server Tester

Test all MCP servers with sample requests:

```bash
uv run mcp-tester
```

Tests include:
- Proofreading different text types
- Command lookup for various tasks
- Technical explanations

### GUI Proofreading Client

Native desktop application for proofreading:

```bash
uv run proofread-gui
```

**Features:**
- Text input area
- Context selection (Slack/Email/General)
- Rewrite options
- Custom instructions
- Copy results to clipboard
- Iterative refinement

## API Integration

### Connecting to MCP Servers

All servers use the Model Context Protocol over HTTP with JSON-RPC 2.0.

#### Basic Connection Pattern

```python
import requests

def call_mcp_tool(server_url, tool_name, arguments):
    response = requests.post(server_url, json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    })
    return response.json()
```

### Proofreading API Examples

#### Slack Proofreading

```python
result = call_mcp_tool(
    "http://localhost:8000/mcp",
    "proofread_slack",
    {
        "text": "hey team, lets push the deployement to monday",
        "instructions": "Make it more professional but keep it casual",
        "can_rewrite": True
    }
)
print(result["result"])  # Proofread text
```

#### Email Proofreading

```python
result = call_mcp_tool(
    "http://localhost:8000/mcp",
    "proofread_email",
    {
        "text": "Dear john, thanks for your email. the project is going good.",
        "instructions": "Make it more formal",
        "can_rewrite": True
    }
)
```

#### General Text Proofreading

```python
result = call_mcp_tool(
    "http://localhost:8000/mcp",
    "proofread_general",
    {
        "text": "The quick brown fox jump over the lazy dog",
        "can_rewrite": False  # Only suggestions, no rewriting
    }
)
```

### Tech Lookup API Examples

#### Command Lookup

```python
result = call_mcp_tool(
    "http://localhost:8001/mcp",
    "list_linux_commands",
    {
        "query": "find all Python files recursively",
        "os": "linux"
    }
)
# Returns: ["find . -name '*.py' -type f", "find . -name '*.py'", ...]
```

#### Technical Explanation

```python
result = call_mcp_tool(
    "http://localhost:8001/mcp",
    "explain_tech_text",
    {
        "text": "find . -name '*.py' -type f"
    }
)
# Returns: Explanation of the find command
```

## Configuration

### Environment Variables

Create a `.env` file from `.env.example`:

```bash
cp .env.example .env
```

Required variables:
```bash
OCI_COMPARTMENT=your-compartment-ocid
OCI_PROFILE=API-USER
```

### Application Configuration

Edit `config.yaml` for application settings:

```yaml
oci:
  compartment: "your-compartment-ocid"
  profile: "API-USER"
  default_model: "xai.grok-4-fast-non-reasoning"

servers:
  proofread:
    host: "0.0.0.0"
    port: 8000
    transport: "sse"
  techtool:
    host: "0.0.0.0"
    port: 8001
    transport: "sse"

testing:
  models_file: "docs/llm_models.md"
  results_dir: "output/benchmarks"
  test_prompt: "what can you do better than any other llm in one sentence"
```

### OCI Setup

1. **Install OCI CLI**:
   ```bash
   pip install oci-cli
   ```

2. **Configure credentials**:
   ```bash
   oci setup config
   ```

3. **Verify configuration**:
   ```bash
   oci iam compartment list
   ```

## Troubleshooting

### Common Issues

#### Server Won't Start
- Check OCI credentials: `oci iam compartment list`
- Verify compartment OCID in config
- Check port availability

#### Client Connection Errors
- Ensure servers are running
- Check firewall settings
- Verify URLs in client code

#### API Errors
- Check JSON-RPC request format
- Verify tool names and parameters
- Review server logs

### Debugging

#### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### Test Server Health

```bash
# Check if server is responding
curl -X POST http://localhost:8000/health

# Test MCP endpoint
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}'
```

#### View Available Tools

```python
import requests

response = requests.post("http://localhost:8000/mcp", json={
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
})

print("Available tools:")
for tool in response.json()["result"]["tools"]:
    print(f"- {tool['name']}: {tool['description']}")
```

### Performance Optimization

- Use faster models for simple tasks
- Implement caching for repeated requests
- Run servers on dedicated hardware
- Monitor response times with benchmarking tools

### Support

For issues not covered here:
1. Check server logs for error messages
2. Verify OCI service quotas and limits
3. Test with minimal examples to isolate issues
4. Review MCP protocol documentation
