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

## Testing

### Local Development (Unit Tests)

```bash
# Run all unit tests (132 tests)
cd ai-agent-school
pytest tests/ -v --tb=short

# Run with coverage
pytest tests/ --cov=. --cov-report=term-missing
```

**Coverage:** 132 tests run locally without external dependencies.

### Full Test Suite (VPS)

The full integration test suite (176 tests) requires PostgreSQL running on VPS:

```bash
# Start PostgreSQL via docker-compose
docker-compose up -d postgres

# Run full test suite
pytest tests/ -v --tb=short

# With coverage
pytest tests/ --cov=. --cov-report=term-missing
```

**Coverage:** 176 tests (132 unit + 44 integration requiring PostgreSQL)

### Test Structure

```
tests/
├── unit/               # Unit tests (run locally)
│   ├── test_config.py
│   ├── test_minimax_client.py
│   ├── test_message_queue.py
│   ├── test_self_correction.py
│   ├── test_graduation.py
│   └── test_database.py
├── conftest.py         # Shared fixtures (mocks DB, MiniMax, MessageQueue)
├── test_teacher.py     # Integration tests (require PostgreSQL)
├── test_student.py     # Integration tests (require PostgreSQL)
└── test_cron.py        # Integration tests (require PostgreSQL)
```

### Why 44 Tests Require VPS

These tests interact with PostgreSQL for:
- Student enrollment and progress tracking
- Teacher-agent conversation history
- Graduation status management
- Cron job monitoring state

The mocking layer (conftest.py autouse fixtures) cannot patch Python's module-level import caching for `get_db()` calls. For local iteration, these tests are skipped.

## Project Status

In development - Phase 1 (Foundation) - 99% test coverage target

## License

MIT