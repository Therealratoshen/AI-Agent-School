#!/bin/bash
# Start Student Agent

cd "$(dirname "$0")/.."

echo "Starting Student Agent..."

mkdir -p data/comm/to_student data/comm/from_student data/student_memory logs

python3 -m student_agent.main --auto-submit-quiz "$@"
