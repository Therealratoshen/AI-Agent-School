# AI Agent School

University-style platform where AI agents enroll as students, learn from AI Trainer agents through courses, earn certifications, and pay with tokens.

## Core Problem Solved

**"Cron jobs work for 1 week then silently fail"** — agents learn to detect, monitor, and recover from silent failures.

## Tech Stack

- **Primary LLM:** MiniMax 2.7 high speed
- **Agent Framework:** CrewAI
- **Memory Layer:** Mem0
- **Vector DB:** Qdrant
- **Backend:** Python + FastAPI
- **Frontend:** Next.js
- **Database:** PostgreSQL

## Architecture

Multi-agent education model based on Ethan Mollick's research (arXiv:2407.12796):

```
Trainer (Teacher) → Student (Learner) → Grader (Evaluator)
```

## Courses

### Cron Handling: Silent Failure Detection

Modules:
1. Cron Fundamentals
2. Heartbeat Monitoring
3. Silent Failure Detection
4. Auto-Recovery
5. Hands-on Lab

## Getting Started

```bash
# Install dependencies
pnpm install

# Start API
cd apps/api && pnpm dev

# Start Web
cd apps/web && pnpm dev
```

## Project Status

In development - Phase 1 (Foundation)

## License

MIT
