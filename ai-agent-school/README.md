# AI Agent School

Production-grade automated training system for AI agents. Trains AI agents to handle cron jobs with self-correction and automatic graduation.

## The Problem This Solves

```
You deploy an AI agent on VPS
     ↓
Agent makes same mistakes daily
     ↓
You fix manually - no time
     ↓
Agent keeps failing silently
```

**Solution:** Agent trains itself via AI Teacher, corrections persist, graduation automatic.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI AGENT SCHOOL (VPS)                        │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Teacher Agent (AI with MiniMax)                     │   │
│  │  - Delivers lessons                                  │   │
│  │  - Grades quizzes with LLM feedback                  │   │
│  │  - Generates corrections via MiniMax                 │   │
│  │  - Triggers auto-graduation                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  PostgreSQL (Message Queue + Storage)                │   │
│  │  - Messages queue (LISTEN/NOTIFY)                     │   │
│  │  - Students, lessons, corrections                     │   │
│  │  - Daily status tracking                             │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Self-Correction Engine                               │   │
│  │  - Detects mistakes                                   │   │
│  │  - Analyzes via MiniMax                              │   │
│  │  - Generates corrections                              │   │
│  │  - Injects to Student Agent (hot reload)             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Graduation Monitor                                   │   │
│  │  - Tracks 7-day failure-free streak                 │   │
│  │  - Auto-graduates when streak reaches 7             │   │
│  │  - Issues certificate                                │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Messages (lesson, correction, quiz)
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    STUDENT AGENT (VPS)                          │
│                                                              │
│  - Receives lessons and corrections via PostgreSQL            │
│  - Hot-reloads corrections into system prompt                 │
│  - Submits quizzes                                          │
│  - Reports mistakes for correction                            │
│  - Persists memory to disk                                    │
└─────────────────────────────────────────────────────────────┘
```

## How It Works

### Self-Correction Loop

```
1. Student Agent makes mistake
        ↓
2. Mistake detected and logged
        ↓
3. MiniMax analyzes WHY it happened
        ↓
4. MiniMax generates correction + explanation
        ↓
5. Correction injected into Student Agent (HOT RELOAD - no restart!)
        ↓
6. Student Agent immediately applies correction
        ↓
7. System verifies correction was learned
        ↓
8. If same mistake repeats → escalate
```

### 7-Day Graduation

```
Day 0: Student enrolled
Day 1-7: Zero failures → streak increments
        ↓
If failure occurs: streak resets to 0
        ↓
Day 7: Streak reaches 7 → GRADUATION
        ↓
Automatic handover:
- Student Agent notified
- Certificate issued
- Student runs in production mode
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- PostgreSQL 15+ (or use the included docker-compose)
- MiniMax API key

### 1. Clone and Setup

```bash
cd ai-agent-school
cp .env.example .env
# Edit .env and add your MINIMAX_API_KEY
```

### 2. Start Services

```bash
docker-compose up -d
```

### 3. Check Health

```bash
curl http://localhost:8080/health
curl http://localhost:8080/health/ready
```

### 4. Enroll a Student

```bash
curl -X POST http://localhost:8080/api/enroll \
  -H "Content-Type: application/json" \
  -d '{"name": "my-agent", "topic": "cron_handling"}'
```

### 5. Access Dashboard

Open http://localhost:8081 in your browser.

## API Endpoints

### Student Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/enroll` | Enroll new student |
| GET | `/api/students` | List all students |
| GET | `/api/students/{id}` | Get student details |
| POST | `/api/students/{id}/lessons/next` | Deliver next lesson |

### Quiz & Mistakes

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/quiz/submit` | Submit quiz answers |
| POST | `/api/mistakes/report` | Report a mistake |
| GET | `/api/students/{id}/corrections` | Get active corrections |

### Graduation

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/students/{id}/graduation` | Get graduation status |
| POST | `/api/graduation/check` | Run daily graduation check |

### Cron Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/cron/register` | Register cron job |
| POST | `/api/cron/heartbeat` | Receive heartbeat |
| GET | `/api/cron/jobs` | List all jobs |
| POST | `/api/cron/jobs/{id}/heal` | Heal a failed job |

### Health & Metrics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic health check |
| GET | `/health/ready` | Readiness check |
| GET | `/health/live` | Liveness check |
| GET | `/api/metrics` | System metrics |
| GET | `/api/dashboard/overview` | Dashboard data |

## Configuration

Configuration is via environment variables:

```bash
# MiniMax LLM
MINIMAX_API_KEY=your_api_key

# Database
AI_SCHOOL_DB_URL=postgresql://postgres:postgres@localhost:5432/ai_school

# Application
AI_SCHOOL_DEBUG=false
AI_SCHOOL_PORT=8080
AI_SCHOOL_WORKERS=4

# Graduation (7 days default)
AI_SCHOOL_GRADUATION_STREAK_DAYS=7

# Cron Monitoring
AI_SCHOOL_HEARTBEAT_INTERVAL=300
AI_SCHOOL_GRACE_PERIODS=2
AI_SCHOOL_MAX_RETRIES=3
```

## Project Structure

```
ai-agent-school/
├── src/
│   ├── api/              # FastAPI REST API
│   ├── core/             # Database, config, message queue
│   ├── cron/              # Cron monitoring & auto-healer
│   ├── dashboard/         # Web dashboard HTML
│   ├── llm/              # MiniMax client
│   ├── student/          # Student agent with hot reload
│   ├── teacher/          # Teacher agent, self-correction, graduation
│   └── sql/              # PostgreSQL schema & migrations
├── tests/                # Unit and integration tests
├── docker-compose.yml    # Docker orchestration
├── Dockerfile            # Container definition
└── nginx.conf            # Dashboard reverse proxy
```

## Development

### Run Tests

```bash
pytest tests/ -v
```

### Run with Debug

```bash
docker-compose up -d api
docker-compose logs -f api
```

### Database Migrations

```bash
# Schema is auto-applied via docker-compose init
# Manual migration:
psql $DATABASE_URL -f src/sql/migrations/001_initial_schema.sql
```

## Monitoring

### Dashboard

The dashboard (http://localhost:8081) shows:
- Student count and status
- Graduation progress (streak days)
- Recent mistakes and corrections
- System health

### API Health Checks

```bash
# Is the service alive?
curl http://localhost:8080/health/live

# Is it ready to serve?
curl http://localhost:8080/health/ready

# Database connectivity?
curl http://localhost:8080/health/ready | jq '.database'
```

## Troubleshooting

### Student not receiving lessons

1. Check database has messages: `psql $DB -c "SELECT * FROM messages"`
2. Check message status: `SELECT status, COUNT(*) FROM messages GROUP BY status`
3. Check API logs: `docker-compose logs api`

### Graduation not triggering

1. Check daily_status table: `psql $DB -c "SELECT * FROM daily_status"`
2. Check failure_streak: `psql $DB -c "SELECT id, failure_streak FROM students"`
3. Verify cron is running graduation check

### Corrections not applying

1. Check corrections table: `psql $DB -c "SELECT * FROM corrections WHERE student_id = '?'"`
2. Check Student Agent logs for received messages
3. Verify hot-reload is working (system_prompt_additions.txt updated)

## License

MIT
