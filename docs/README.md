# AI Tools - MCP Servers for AI-Powered Tasks

A collection of Model Context Protocol (MCP) servers that provide AI-powered tools for various tasks using Oracle Cloud Infrastructure (OCI) Generative AI.

## Overview

This project provides multiple MCP servers that expose AI capabilities through a standardized protocol:

- **Proofreading Server**: AI-powered text proofreading for different contexts (Slack, Email, General)
- **Tech Lookup Server**: Linux/macOS command assistance and technical explanation
- **Future Servers**: Additional AI tools can be easily added

## Features

### Proofreading Server
- **Multi-context proofreading**: Optimized for Slack, Email, and general text
- **Flexible rewriting**: Choose between suggestions-only or full rewriting
- **Custom instructions**: Add specific guidance for specialized proofreading
- **Native GUI client**: Desktop application built with tkinter

### Tech Lookup Server
- **Command lookup**: Find Linux/macOS commands for specific tasks
- **Technical explanations**: Understand complex commands and concepts
- **Multi-platform support**: Linux and macOS command variants

### General Features
- **OCI Generative AI integration**: Powered by Oracle's enterprise AI models
- **MCP protocol**: Standardized interface for AI tool integration
- **HTTP/SSE transport**: Web-compatible communication
- **Python-native**: No web dependencies required for servers

## Quick Start

### Prerequisites

1. **OCI Account**: Access to Oracle Cloud Infrastructure
2. **Python 3.11+**: Modern Python installation
3. **OCI CLI**: Configured with API keys or instance principals

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd ai_tools

# Install dependencies
uv sync

# Configure OCI credentials
cp .env.example .env
# Edit .env with your OCI credentials
```

### Configuration

Edit `config.yaml` and `.env` files:

```yaml
# config.yaml
oci:
  compartment: "your-compartment-ocid"
  profile: "API-USER"
  default_model: "xai.grok-4-fast-non-reasoning"
```

```bash
# .env
OCI_COMPARTMENT=your-compartment-ocid
OCI_PROFILE=API-USER
```

### Running Servers

```bash
# Start proofreading server
uv run proofread-server

# Start tech lookup server
uv run techlookup-server
```

### Using Clients

```bash
# Hello world example
uv run hello-world

# Benchmark models
uv run benchmark-models

# Test MCP servers
uv run mcp-tester

# GUI proofreading client
uv run proofread-gui
```

## Project Structure

```
ai_tools/
├── examples/           # Demo scripts and utilities
│   ├── hello_world.py      # Basic OCI client demo
│   └── benchmark_models.py # Model performance testing
├── clients/            # Interactive client applications
│   ├── mcp_tester.py       # MCP server testing client
│   └── proofread_gui.py    # Native GUI proofreading client
├── tests/              # Unit tests
│   ├── test_oci_models.py
│   └── test_proofread_server.py
├── output/             # Generated files and reports
│   ├── benchmarks/     # Model benchmarking results
│   └── reports/        # Other outputs
├── src/ai_tools/       # Main package
│   ├── oci_openai_helper.py   # OCI authentication helper
│   ├── proofread_mcp_server.py # Proofreading server
│   ├── techlookup_mcp_server.py # Tech lookup server
│   └── utils/          # Configuration and utilities
├── docs/               # Documentation
│   ├── README.md       # This file
│   ├── llm_models.md   # Available AI models
│   └── example.clinerules.md # Development guidelines
├── config.yaml         # Application configuration
├── .env.example        # Environment variables template
└── pyproject.toml      # Python project configuration
```

## MCP API Usage

### Proofreading Server

```python
import requests

# Slack proofreading
response = requests.post("http://localhost:8000/mcp", json={
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "proofread_slack",
        "arguments": {
            "text": "hey team, lets push the deployement to monday",
            "can_rewrite": True
        }
    }
})

# Email proofreading
response = requests.post("http://localhost:8000/mcp", json={
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "proofread_email",
        "arguments": {
            "text": "Dear john, thanks for your email. the project is going good.",
            "can_rewrite": True
        }
    }
})
```

### Tech Lookup Server

```python
# Command lookup
response = requests.post("http://localhost:8001/mcp", json={
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "list_linux_commands",
        "arguments": {
            "query": "find all Python files recursively",
            "os": "linux"
        }
    }
})

# Technical explanation
response = requests.post("http://localhost:8001/mcp", json={
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "explain_tech_text",
        "arguments": {
            "text": "find . -name '*.py' -type f"
        }
    }
})
```

## Available AI Models

See [docs/llm_models.md](docs/llm_models.md) for the complete list of supported OCI Generative AI models.

## Development

### Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run coverage run -m pytest
uv run coverage report
```

### Code Quality

```bash
# Lint code
uv run ruff check .

# Format code
uv run ruff format .

# Type checking
uv run mypy .
```

### Adding New Servers

1. Create server file in `src/ai_tools/`
2. Use `@mcp.tool()` decorator for tool functions
3. Add proper type hints and docstrings
4. Update `pyproject.toml` with new CLI entry point
5. Add tests in `tests/`

## Dependencies

- **fastmcp**: MCP server framework
- **oci-openai**: OCI authentication for OpenAI client
- **langchain-openai**: LangChain OpenAI integration
- **pydantic**: Data validation and settings
- **httpx**: HTTP client
- **uvicorn**: ASGI server

## License

[Add your license information here]

## Contributing

