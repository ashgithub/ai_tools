# AI Tools - Proofreading MCP Server

A Model Context Protocol (MCP) server that provides AI-powered proofreading tools for different communication contexts using Oracle Cloud Infrastructure (OCI) Generative AI.

## Features

- **Slack Proofreading**: Professional yet casual proofreading for team communication
- **Email Proofreading**: Formal proofreading for business correspondence
- **General Text Proofreading**: Standard proofreading for any text content
- **Flexible Rewriting**: Option to allow AI to rewrite content or just fix errors
- **Custom Instructions**: Add specific guidance for proofreading tasks
- **HTTP API**: RESTful HTTP endpoint for easy integration

## Installation

1. Install dependencies:
```bash
uv sync
```

2. Set up OCI configuration:
   - Configure your OCI credentials in `~/.oci/config`
   - Copy `.env.example` to `.env` and fill in your values
   - Or set environment variables:
     ```bash
     export GENAI_ENDPOINT_BASE="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com"
     export OCI_COMPARTMENT_ID="your-compartment-ocid"
     export OCI_PROFILE="API-USER"
     export GENAI_MODEL="xai.grok-4-fast-non-reasoning"
     ```

## Usage

### Starting the Server

Run the proofreading MCP server:

```bash
uv run python -m src.ai_tools.aitools_mcp_server
```

The server will start on `http://localhost:8000` with:
- MCP endpoint: `POST /mcp`
- Health check: `GET /health`

### Testing the Server

Run the test script to verify functionality:

```bash
uv run python -m pytest tests/test_proofread_server.py
```

Or run the model testing script:

```bash
uv run python scripts/test_oci_models.py
```

## API Usage

### Slack Proofreading

```python
import requests

response = requests.post("http://localhost:8000/mcp", json={
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "proofread_slack",
        "arguments": {
            "text": "hey team, lets push the deployement to monday",
            "instructions": "Make it more professional but keep it casual",
            "can_rewrite": True
        }
    }
})
```

### Email Proofreading

```python
response = requests.post("http://localhost:8000/mcp", json={
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "proofread_email",
        "arguments": {
            "text": "Dear john, thanks for your email. the project is going good.",
            "instructions": "Make it more formal",
            "can_rewrite": True
        }
    }
})
```

### General Text Proofreading

```python
response = requests.post("http://localhost:8000/mcp", json={
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "proofread_text",
        "arguments": {
            "text": "The quick brown fox jump over the lazy dog",
            "instructions": "",
            "can_rewrite": False
        }
    }
})
```

## Tool Parameters

All proofreading tools accept these parameters:

- `text` (string, required): The original text to proofread
- `instructions` (string, optional): Additional instructions for the AI
- `can_rewrite` (boolean, optional, default: False):
  - `True`: AI can rewrite the text to improve clarity and structure
  - `False`: AI only fixes typos, grammar, punctuation, and spelling

## Response Format

```json
{
  "jsonrpc": "2.0",
  "result": "Proofread text here",
  "id": 1
}
```

## Context-Specific Behavior

### Slack
- Maintains casual, friendly tone
- Suitable for emojis when appropriate
- Concise and conversational

### Email
- Professional and formal tone
- Includes proper greeting/closing structure when applicable
- Business-appropriate language

### General Text
- Improves clarity and readability
- Maintains original intent
- Fixes grammatical errors

## Development

### Project Structure

```
ai-tools/
├── src/ai_tools/              # Main package
│   ├── __init__.py
│   ├── aitools_mcp_server.py # Main MCP server
│   └── oci_client.py          # OCI OpenAI client wrapper
├── scripts/                   # Developer scripts
│   ├── main.py               # Hello world demo
│   ├── min_mcp_client.py     # Minimal MCP client
│   └── proofread_client.py   # Proofreading client
├── tests/                    # Test modules
│   ├── __init__.py
│   ├── test_oci_models.py    # Model testing
│   └── test_proofread_server.py # Server tests
├── docs/                     # Documentation
│   ├── README.md
│   └── llm_models.md
├── config.yaml               # Configuration file
├── .env.example              # Environment variables template
├── pyproject.toml            # Project configuration
├── CHANGELOG.md              # Change log
└── .gitignore               # Git ignore rules
```

### Adding New Tools

1. Define the tool function with `@app.tool()` decorator
2. Add appropriate type hints and docstrings
3. Handle errors gracefully
4. Return only the proofread text

## Dependencies

- `fastmcp`: Model Context Protocol framework
- `fastapi`: Web framework for HTTP API
- `uvicorn`: ASGI server
- `oci`: Oracle Cloud Infrastructure SDK
- `openai`: OpenAI client (configured for OCI)
- `httpx`: HTTP client

## License

[Add your license here]
