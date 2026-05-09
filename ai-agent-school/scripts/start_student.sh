#!/bin/bash
# Start Student Agent

cd "$(dirname "$0")/.."

echo "🤖 Starting Student Agent..."

# Create memory directory if not exists
mkdir -p memory

# Run student agent
python3 -m student_agent.main
