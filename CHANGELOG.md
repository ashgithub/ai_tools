# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of AI Tools proofreading MCP server
- Support for proofreading in Slack, Email, and general text contexts
- Tech lookup MCP server for Linux/macOS command assistance
- OCI Generative AI integration for LLM-powered tools
- HTTP API endpoints for MCP protocol
- Flexible rewriting options (can allow or forbid text restructuring)
- Custom instruction support for specialized proofreading needs
- Native Python GUI client for proofreading (tkinter-based)
- MCP client for testing multiple servers
- Model benchmarking utilities
- Configuration system using YAML for all constants and prompts
- Environment variable support for OCI credentials
- Comprehensive .gitignore with all required exclusions
- CHANGELOG.md for tracking changes

### Changed
- **Major project restructuring** for better organization:
  - Renamed `scripts/` → `examples/` for demo scripts
  - Created `clients/` for interactive client applications
  - Created `output/` for consolidated generated files
  - Updated all import paths and CLI commands
- Moved hardcoded configurations to config.yaml
- Moved prompts to external configuration
- Updated config structure to use `profile`/`compartment` instead of `profile_name`/`compartment_id`
- Refactored OCI client to use `oci_openai` library helper
- Updated pyproject.toml with new CLI entry points
- Renamed development rules file to `example.clinerules.md`

### Technical
- Uses fastmcp for MCP server implementation
- OCI OpenAI client with `oci_openai` library for authenticated AI requests
- Pydantic for settings management
- pytest for testing framework
- Tkinter for native desktop GUI client
- uv for dependency management

### Removed
- Old custom `oci_client.py` (replaced with `oci_openai_helper.py`)
- AI assistant artifacts and cache files
- Old server logs and irrelevant files
