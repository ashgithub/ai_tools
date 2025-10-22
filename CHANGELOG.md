# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of AI Tools proofreading MCP server
- Support for proofreading in Slack, Email, and general text contexts
- OCI Generative AI integration for LLM-powered proofreading
- HTTP API endpoint for MCP protocol
- Flexible rewriting options (can allow or forbid text restructuring)
- Custom instruction support for specialized proofreading needs
- Configuration system using YAML for all constants and prompts
- Environment variable support for OCI credentials
- Project structure updates to comply with development rules
- Scripts directory for developer utilities
- Comprehensive .gitignore with all required exclusions
- CHANGELOG.md for tracking changes

### Changed
- Moved hardcoded configurations to config.yaml
- Moved prompts to external configuration
- Updated directory structure (scripts/, config files)
- Updated README with current usage and structure

### Technical
- Uses fastmcp for MCP server implementation
- OCI OpenAI client for authenticated AI requests
- Pydantic for settings management
- pytest for testing framework
