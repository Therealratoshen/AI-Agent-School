# AI Agent School

Automated training system for AI agents to learn and improve.

## Core Problem Solved

**"Cron jobs work for 1 week then silently fail"** — agents learn to detect, monitor, and recover from silent failures.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure
cp config/config.yaml config/config.local.yaml
# Edit config.local.yaml with your settings

# Start School Server
python -m school.main

# In another terminal, start Student Agent
python -m student_agent.main
```

## Project Structure

```
ai-agent-school/
├── school/                 # School server (Teacher)
│   ├── teacher/           # Teacher agent
│   ├── student/           # Student interface
│   ├── cron/             # Cron auto-heal
│   ├── memory/           # Memory persistence
│   ├── tracking/         # Mistake tracking
│   └── dashboard/        # Web dashboard
├── student-agent/         # Student agent (runs on your VPS)
├── shared/               # Shared utilities
├── lessons/              # Course content
├── data/                 # Runtime data
├── config/               # Configuration
└── scripts/             # Setup scripts
```

## How It Works

1. Enroll your agent
2. Teacher sends lessons
3. Student learns and takes quizzes
4. Mistakes are tracked and corrected
5. Corrections persist in memory
6. Cron jobs are monitored and auto-healed
7. When 7 days pass with no failures, agent is production-ready

## Tech Stack

- **Primary LLM:** MiniMax 2.7 high speed
- **Agent Framework:** CrewAI (compatible)
- **Memory Layer:** File-based + SQLite
- **Backend:** Python
- **Frontend:** HTML/JS Dashboard

## Dashboard

Open http://localhost:8080 to view:
- Agent status
- Memory health
- Mistakes tracked
- Corrections applied
- Training progress
- Cron job status

## Requirements

- Python 3.8+
- Shared folder between school and student VPS
- Your agent must support file-based communication

## License

MIT
