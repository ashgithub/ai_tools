# Cline Rules for This Project

Authoritative, human-readable operating rules for assistants working in this repository. Follow these rules for all tasks unless a task-specific spec overrides them.

---

## 1) Scope and Objectives

- Goal: Implement high-quality Python tooling/features quickly, safely, and reproducibly.
- Constraints: Keep changes minimal, reversible, and well-tested. Do not introduce breaking changes without an explicit migration plan.
- Audience: AI assistants and contributors modifying code, docs, tooling, CI, or infra related to this repo.

---

## 2) Tech Stack Expectations

This is a Python-focused project. Prefer modern tooling and standards:

- Python: 3.10+ (prefer 3.11+ when possible)
- Packaging/config: pyproject.toml (PEP 621)
- Lint/Format: ruff, black (or ruff format)
- Type checking: mypy (strict on new/changed code)
- Testing: pytest, pytest-cov
- Env/Deps: uv (project standard)
- Initialize .gitignore (Python, macOS, VSCode, uv artifacts, OCI credentials)
  - Include at minimum: .venv/, .python-version, .idea/, .vscode/, __pycache__/, *.pyc, .pytest_cache/, .ruff_cache/, .mypy_cache/, .coverage*, .DS_Store, .env, .env.*, dist/, build/
  - Commit uv.lock to ensure reproducible installs; do not commit credentials (store keys/config in ~/.oci)


- uv: the project uses uv
   - Install/sync: uv sync
   - Run commands: uv run <command>

- Oracle OCI libraries for all AI tasks.  the default model to use is xai.grok-4-fast-non-reasoning
- OpenAI client is used against OCI Generative AI endpoints with OCI authentication via the oci Python SDK. All AI calls must route through OCI; do not call public OpenAI endpoints directly.
-  use fastmcp librray for mcp 
---

## 3) Repository Conventions

- Source layout:
  - src/<package_name>/... for library/application code
  - tests/ for test modules mirroring src layout
  - scripts/ for developer utilities or CLIs
  - docs/ for user and developer documentation
- Naming:
  - Modules/packages: snake_case
  - Classes: PascalCase
  - Functions/vars: snake_case
  - Constants: UPPER_SNAKE_CASE
- Docs:
  - Public functions/classes: Python docstrings (Google or NumPy style)
  - README must reflect current usage and setup
  - Update CHANGELOG.md for user-visible changes (Keep a Changelog format)
- Versioning: SemVer (MAJOR.MINOR.PATCH)
- Logging: Use standard library logging; no print for production paths
- Configuration: Prefer environment variables via pydantic-settings or python-dotenv; avoid hard-coding paths/secrets

---

## 4) Quality Gates

- Lint: ruff check must pass
- Format: black . (or ruff format . if black is not used)
- Type-check: mypy must pass on changed code (use strict for new modules)
- Tests: pytest must pass locally; aim for meaningful coverage (default fail-under 80% unless repo sets a different threshold)
- Security: no secrets committed; add .env.example and document required variables

Standard quality command sets (auto-adapt to env tool per Section 2):
- Lint: ruff check .
- Format: black . (or ruff format .)
- Type: mypy .
- Tests: pytest -q
- Coverage: coverage run -m pytest -q && coverage report --fail-under=80

---

## 5) Git and PR Workflow

- Branch names: feat/..., fix/..., chore/..., docs/..., refactor/..., test/...
- Conventional Commits:
  - feat: add feature
  - fix: bug fix
  - docs: docs only
  - style: formatting (no code change)
  - refactor: non-feature/non-bug structural change
  - test: add/adjust tests
  - chore: tooling/infra/deps
- Commit messages: concise subject (max ~72 chars), optional body with context and rationale
- PR checklist:
  - [ ] Lint/format/type-check/test pass locally
  - [ ] Tests added/updated for new behavior
  - [ ] Docs updated (README/CHANGELOG)
  - [ ] No secrets/keys in diffs
  - [ ] Breaking changes clearly called out with migration notes

---

## 6) Assistant Tool-Use Policy (Cline)

- One tool per step/message; wait for confirmation after each tool use.
- Always read file(s) before editing them.
- Prefer targeted edits:
  - Use replace_in_file for small, localized changes.
  - Use write_to_file to create new files or when replacing an entire file’s contents.
- When using replace_in_file:
  - SEARCH blocks must match complete lines exactly (whitespace included).
  - Keep SEARCH minimal but unique; include surrounding lines if needed for uniqueness.
  - Order multiple SEARCH/REPLACE blocks as they appear in the file.
  - Use separate blocks to move or delete sections (delete with empty REPLACE).
- Commands execution:
  - Explain what a command does before running it.
  - Require approval for destructive operations (install/uninstall, delete, network ops, system changes).
  - If tests/linters fail, fix and rerun until green.
- Cross-file consistency:
  - After refactors/renames, use search_files to update imports, references, and docs.
- Do not modify binary files directly; for assets, add new versions and update references.
- Keep changes minimal and reversible; prefer many small diffs over one massive change.

---

## 7) Testing Strategy

- Use pytest with clear, focused unit tests; supplement with integration tests where behavior crosses modules or I/O.
- Mirror src layout under tests/. Example:
  - src/ai_tools/core/foo.py &rarr; tests/core/test_foo.py
- Write tests first for bug fixes (regressions) and for new public APIs.
- Use pytest parametrize to cover edge cases; consider hypothesis for property-based tests.
- Make tests deterministic; mock external services and time as needed.

Example pytest commands:
- pytest -q
- coverage run -m pytest -q && coverage report --fail-under=80

---

## 8) Typing and API Contracts

- New/changed code must be typed. Avoid Any; use Protocols and TypedDict/dataclasses where helpful.
- Public functions/classes: complete type hints and docstrings describing behavior, parameters, return values, and errors.
- Validate inputs early; raise clear, specific exceptions.

---

## 9) Documentation Requirements

- Update README for new features or setup changes.
- Maintain CHANGELOG entries for user-visible changes.
- Add/maintain docstrings for all public APIs.
- If a significant architectural decision is made, add an ADR (docs/adr/NNN-title.md) with context, options, decision, and consequences.

---

## 10) Security and Secrets

- Never commit secrets, tokens, or credentials.
- Use .env for local dev, and provide .env.example with placeholder values.
- Document required env vars in README.
- Sanitize logs; avoid logging PII/secrets.
- If secrets accidentally appear in history, rotate them and purge via standard secret removal procedures.

---

## 11) Performance and Reliability

- Avoid global state; prefer dependency injection for testability.
- Fail fast with clear error messages; surface actionable context.
- Use lazy imports and efficient algorithms/data structures for hot paths.
- Add basic benchmarks if optimizing; include rationale and before/after metrics in PR.

---

## 12) Automation and Hooks

- Pre-commit (recommended):
  - ruff check
  - black
  - mypy (optional pre-commit hook; always run in CI)
- CI (expected steps, adapt to platform):
  1) Install deps (uv)
  2) Lint/format check
  3) Type check
  4) Tests with coverage and fail-under policy
  5) Build packaging sanity check (python -m build) if packaging a library

---

## 13) When to Ask for Input

Ask the user via a follow-up question if:
- A change is potentially destructive or ambiguous (e.g., deleting files, changing public APIs).
- The repo lacks clear dependency tooling (Poetry/uv/pip); propose an initialization plan with options.
- Requirements conflict (e.g., formatting vs. existing style) or missing context (e.g., production secrets or infra endpoints).

Keep questions specific and provide 2–4 options to accelerate decisions.

---

## 14) Non-Goals and Boundaries

- Do not introduce unrelated features or dependencies without rationale.
- Do not add third-party services or network calls without explicit user approval.
- Do not lower quality gates (lint/type/tests) to “make it pass”; fix underlying issues.

---

## 15) Quick Command Cheat Sheet (uv)

uv:
- Sync: uv sync
- Lint: uv run ruff check .
- Format: uv run black .   (or uv run ruff format .)
- Type: uv run mypy .
- Test: uv run pytest -q
- Coverage: uv run coverage run -m pytest -q && uv run coverage report --fail-under=80

---

## 16) Minimal Task Flow Checklist (for every change)

1) Understand the task and verify scope
2) Inspect related files and tests (read before editing)
3) Plan edits; prefer smallest viable change
4) Implement with targeted edits (replace_in_file or write_to_file)
5) Lint/format/type-check locally
6) Add/update tests; run pytest/coverage
7) Update docs (README/CHANGELOG)
8) Prepare conventional commit message and PR checklist

---

## 17) Repository Initialization (if empty)

If the repo is empty and initialization is requested, propose:
- pyproject.toml (PEP 621)
- src/<package_name>/__init__.py
- tests/
- .gitignore, .editorconfig
- ruff + black + mypy configs
- pytest + coverage config
- pre-commit config
- README.md and CHANGELOG.md
Use uv.

---

## 18) Enforcement

These rules define the default operating standard. Deviations require explicit mention in the PR description including the reasoning and trade-offs.

---

## 19) OCI and Generative AI Integration

- Libraries:
  - oci (OCI Python SDK) for authentication and request signing
  - openai (Python client) configured to use OCI Generative AI endpoints
- Configuration and credentials:
  - Prefer ~/.oci/config with a named profile; alternatively use instance/resource principals in CI
  - Required env vars for local development (reflect in .env.example):
    - OCI_CONFIG_FILE, OCI_PROFILE, OCI_REGION
    - OCI_TENANCY_OCID, OCI_USER_OCID, OCI_FINGERPRINT, OCI_KEY_FILE, OCI_KEY_PASS_PHRASE (for API key auth)
    - GENAI_ENDPOINT_BASE (e.g., https://inference.generativeai.{region}.oci.oraclecloud.com)
    - GENAI_MODEL (default model identifier)
- Client policy:
  - Route all OpenAI client calls through OCI by setting base_url to the OCI Generative AI endpoint and using OCI auth
  - Do not call public OpenAI endpoints directly
  - Redact sensitive data; prefer retrieval augmentation for private context
- Testing:
  - Provide mock/fake clients for unit tests; guard live integration tests behind a flag (e.g., ENABLE_GENAI_IT=1)
- Logging:
  - Log metadata only (latency, token counts if available); never log raw prompts or completions containing sensitive data
