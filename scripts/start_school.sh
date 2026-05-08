#!/bin/bash
# Start School Server

cd "$(dirname "$0")/.."

echo "🎓 Starting AI Agent School Server..."

# Check if config exists
if [ ! -f config/config.yaml ]; then
    echo "Config not found. Copying from example..."
    cp config/config.example.yaml config/config.yaml
fi

# Run school server
python3 -m school.main
