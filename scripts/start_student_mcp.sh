#!/bin/bash
# Start Student Agent in MCP mode (local or cloud)

cd "$(dirname "$0")/.."

MODE="${1:-mcp}"
MCP_URL="${AI_SCHOOL_MCP_URL:-http://localhost:8080/api/mcp}"

echo "Starting Student Agent (mode=$MODE, url=$MCP_URL)..."

mkdir -p data/student_memory logs

python3 -m student_agent.main \
  --mode "$MODE" \
  --mcp-url "$MCP_URL" \
  --auto-submit-quiz \
  "${@:2}"
