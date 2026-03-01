#!/usr/bin/env bash
set -euo pipefail

# Run the AI Tools universal GUI from command line.
#
# Sample invocations:
#   # Ask / explain default (auto nudge)
#   ./scripts/run_app.sh --text "What is the difference between TCP and UDP?"
#
#   # Slack-proofread nudge
#   ./scripts/run_app.sh --app slack --nudge slack --text "hi team pls review the doc by tomrw"
#
#   # Commands nudge
#   ./scripts/run_app.sh --nudge commands --text "find all .py files modified in last 24 hours"
#
#   # Pipe stdin text
#   echo "pls fix grammar" | ./scripts/run_app.sh --nudge proofread

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

exec /opt/homebrew/bin/uv run clients/multi_tool_client.py "$@"
