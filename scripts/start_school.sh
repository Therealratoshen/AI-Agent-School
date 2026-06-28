#!/bin/bash
# Start School Server

cd "$(dirname "$0")/.."

echo "Starting AI Agent School Server..."

mkdir -p data/comm/to_student data/comm/from_student data/student_memory logs

python3 -m school.main "$@"
