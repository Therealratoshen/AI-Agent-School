#!/bin/bash
# Stop all services

echo "🛑 Stopping AI Agent School..."

# Kill Python processes related to this project
pkill -f "school.main" || true
pkill -f "student_agent.main" || true

echo "✅ Stopped"
