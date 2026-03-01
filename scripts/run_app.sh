#!/usr/bin/env bash
set -euo pipefail

# Run the AI Tools GUI from command line.
#
# Sample invocations:
#   # Q&A tab with direct text
#   ./scripts/run_app.sh --tab "Q&A" --text "What is the difference between TCP and UDP?"
#
#   # Proofread in Slack context (tab chosen by app mapping)
#   ./scripts/run_app.sh --app slack --text "hi team pls review the doc by tomrw"
#
#   # Proofread email explicitly
#   ./scripts/run_app.sh --tab Proofread --app gmail --text "hey can u send me update"
#
#   # Commands tab
#   ./scripts/run_app.sh --tab Commands --text "find all .py files modified in last 24 hours"
#
#   # Pipe stdin text (if --text is omitted)
#   echo "pls fix grammar" | ./scripts/run_app.sh --tab Proofread

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

exec /opt/homebrew/bin/uv run clients/multi_tool_client.py "$@"
