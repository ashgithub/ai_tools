#!/usr/bin/env bash
set -euo pipefail

# Validate app integrity quickly.
#
# Usage:
#   ./scripts/test_app.sh
#
# What it runs:
#   1) Ruff lint
#   2) Compile check
#   3) Pytest suite

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"
export UV_CACHE_DIR="${ROOT_DIR}/.cache/uv"

echo "[1/3] Lint (ruff)"
uv run ruff check src clients tests scripts

echo "[2/3] Compile check"
uv run python -m compileall -q src clients tests

echo "[3/3] Tests"
uv run pytest -q

echo "All checks passed."
