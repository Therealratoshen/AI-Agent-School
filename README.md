# AI Agent School - README

Automated training system for AI agents to learn and improve.

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
├── lessons/              # Course content
├── data/                 # Runtime data
├── config/               # Configuration
└── scripts/              # Setup scripts
```

## Configuration

Edit `config/config.local.yaml`:

```yaml
communication:
  base_dir: "/shared/ai-school"  # Shared folder between school and student

memory:
  student_memory_path: "/home/user/openclaw/memory"  # Your agent's memory

student:
  api_endpoint: "http://localhost:8081"  # Your agent's API
```

## How It Works

1. Enroll your agent
2. Teacher sends lessons
3. Student learns and takes quizzes
4. Mistakes are tracked and corrected
5. When 7 days pass with no failures, agent is production-ready

## Dashboard

Open http://localhost:8080 to view:
- Agent status
- Memory health
- Mistakes tracked
- Corrections applied
- Training progress

## Requirements

- Python 3.8+
- Shared folder between school and student VPS
- Your agent must support file-based communication

## License

MIT
