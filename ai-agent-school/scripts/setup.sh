#!/bin/bash
# Setup script for AI Agent School

set -e

echo "🎓 AI Agent School - Setup"

# Create directories
echo "Creating directories..."
mkdir -p data/backups
mkdir -p logs
mkdir -p /shared/ai-school/to_student
mkdir -p /shared/ai-school/from_student
mkdir -p memory

# Create Python virtual environment (optional)
echo "Installing Python dependencies..."
if command -v pip3 &> /dev/null; then
    pip3 install -r requirements.txt
else
    echo "pip3 not found, skipping dependency installation"
fi

# Make scripts executable
echo "Setting permissions..."
chmod +x scripts/*.sh

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit config/config.yaml with your settings"
echo "2. Run: ./scripts/start_school.sh"
echo "3. In another terminal: python -m student_agent.main"
echo ""
echo "Dashboard will be available at: http://localhost:8080"
