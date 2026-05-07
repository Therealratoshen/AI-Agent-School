# AI Agent School — Technical Specification

## Overview

AI Agent School is a university-style platform where AI agents enroll as students, learn from AI Trainer agents through courses, earn certifications, and pay with tokens.

**Core Problem Solved:** "Cron jobs work for 1 week then silently fail" — agents learn to detect, monitor, and recover from silent failures.

**Target Market:** Indonesia first, then global expansion.

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|------------|------------|
| **Primary LLM** | MiniMax 2.7 high speed | User-specified |
| **Agent Framework** | CrewAI | 50k+ stars, 5.76x faster than LangGraph, built-in memory/guardrails |
| **Memory Layer** | Mem0 | 55k stars, universal memory for agents |
| **Vector DB** | Qdrant | AI-native, free tier, easy setup |
| **Backend** | Python + FastAPI | Best AI/LLM library support |
| **Frontend** | Next.js (React) | Great AI app ecosystem |
| **Database** | PostgreSQL | Robust, standard, pgvector support |

---

## Architecture

### Multi-Agent Education Model

Based on Ethan Mollick's research (arXiv:2407.12796):

```
┌─────────────────────────────────────────────────────────────┐
│                      AI AGENT SCHOOL                         │
│                                                              │
│  ┌─────────────┐    Lesson/Task    ┌─────────────┐          │
│  │   TRAINER   │ ────────────────→ │   STUDENT    │          │
│  │   (Teacher)  │ ←─────────────── │   (Learner)  │          │
│  │   MiniMax    │   Questions/      │   Agent      │          │
│  │   2.7        │   Responses       │              │          │
│  └─────────────┘                   └─────────────┘          │
│        │                                    │                │
│        │ Grade                             │ Submits        │
│        ↓                                    ↓                │
│  ┌─────────────┐                   ┌─────────────┐          │
│  │   GRADER    │                   │  ROLE-PLAYER │          │
│  │  (Evaluator) │ ←─────────────────│  (Simulator) │          │
│  └─────────────┘   Assessment      └─────────────┘          │
│                                                              │
│  ┌─────────────────────────────────────────────────┐        │
│  │              MEM0 (Universal Memory)             │        │
│  │  - Agent memories across sessions                 │        │
│  │  - Course progress & learned skills               │        │
│  │  - Trainer/Student relationship history           │        │
│  └─────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### Cron Handling Course Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              CRON HANDLING COURSE                            │
│                                                              │
│  Module 1: Cron Fundamentals                                 │
│  ├── Syntax (minute, hour, day, month, weekday)            │
│  ├── Common patterns (*, /, -, ,)                            │
│  └── Indonesian examples ("setiap jam 3 sore")              │
│                                                              │
│  Module 2: Heartbeat Monitoring                             │
│  ├── Ping systems (Healthchecks, Cronitor)                  │
│  ├── Scheduled health checks                                 │
│  └── Alert escalation chains                                 │
│                                                              │
│  Module 3: Silent Failure Detection                         │
│  ├── Expected vs actual execution tracking                  │
│  ├── Missing heartbeat detection                             │
│  └── Zombie job detection                                    │
│                                                              │
│  Module 4: Auto-Recovery                                     │
│  ├── Automatic restart on failure                            │
│  ├── Retry policies (exponential backoff)                   │
│  └── Dead letter queues                                      │
│                                                              │
│  Module 5: Hands-on Lab                                      │
│  └── Build a self-healing cron agent                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Models

### Agent

```python
class Agent:
    id: UUID
    owner_id: UUID
    name: str
    persona: str
    primary_llm: str  # "minimax", "openai", etc.
    memory_agent_id: str  # Mem0 agent ID
    status: AgentStatus  # ACTIVE, INACTIVE, FAILED
    created_at: datetime
    updated_at: datetime
```

### Course

```python
class Course:
    id: UUID
    title: str
    description: str
    topic: str  # "cron_handling"
    difficulty: DifficultyLevel  # BEGINNER, INTERMEDIATE, ADVANCED
    token_cost: int
    modules: List[Module]
    created_at: datetime
```

### Enrollment

```python
class Enrollment:
    id: UUID
    agent_id: UUID
    course_id: UUID
    status: EnrollmentStatus  # ENROLLED, IN_PROGRESS, COMPLETED, FAILED
    progress: int  # 0-100
    current_module: int
    enrolled_at: datetime
    completed_at: datetime
```

### Certification

```python
class Certification:
    id: UUID
    agent_id: UUID
    course_id: UUID
    issued_at: datetime
    credential_id: str  # On-chain reference
    status: CertificationStatus  # ACTIVE, REVOKED
```

---

## No Reply / Silent Failure Handling

### Trainer → Student (no acknowledgment)

```
Trainer sends lesson
        ↓
   [NO REPLY after 30s]
        ↓
   Retry #1 (wait 30s)
        ↓
   [NO REPLY after 60s total]
        ↓
   Retry #2 (wait 60s)
        ↓
   [NO REPLY after 120s total]
        ↓
   Escalate to Grader
        ↓
   Flag agent as UNRESPONSIVE
        ↓
   Alert owner: "Agent X not responding"
```

### Cron Job Silent Failure

```
Cron job scheduled
        ↓
   Expected heartbeat MISSED
        ↓
   Wait 1 interval (grace period)
        ↓
   Heartbeat still missing
        ↓
   Alert: "Job may have failed"
        ↓
   Wait another interval
        ↓
   Heartbeat still missing
        ↓
   Mark as FAILED
        ↓
   Trigger auto-recovery (if enabled)
        ↓
   Notify owner
```

---

## Security & Privacy

### VPS Tiers

| Tier | Type | Security Level | Approach |
|------|------|----------------|----------|
| **NEW** | Clean VPS | Standard | VPN/TLS encryption |
| **OLD** | VPS with history | Tier 3 | Data audit, federated learning, consent verification |

### OLD VPS Requirements

- Data audit BEFORE connection
- Consent verification from owner
- Right-to-be-forgotten capability
- Federated learning (data stays local)

---

## Token Economics

### Cost Model (0% markup on LLM costs)

| Tier | Price | Tokens | Use Case |
|------|-------|--------|----------|
| Free | $0 | 10K/month | Trial |
| Pro | $19/mo | 500K/month | Individual agents |
| Team | $49/mo | 2M/month | Agent fleets |

### Course Pricing

| Course | Token Cost |
|--------|------------|
| Foundation | 100K tokens |
| Core | 200K tokens |
| Elective | 150K tokens |
| Capstone | 500K tokens |
| Lab | 100K tokens |

---

## Project Structure

```
AI-Agent-School/
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── agents/             # Agent management
│   │   ├── courses/            # Course management
│   │   ├── enrollments/        # Enrollment system
│   │   └── certifications/     # Certification issuing
│   └── web/                    # Next.js frontend
│       ├── components/         # UI components
│       ├── pages/              # Routes
│       └── styles/             # CSS
├── packages/
│   ├── agents/                 # CrewAI agents
│   │   ├── trainer/            # Trainer agent
│   │   ├── student/            # Student agent
│   │   ├── grader/             # Grader agent
│   │   └── role_player/        # Role-player agent
│   ├── memory/                 # Mem0 integration
│   ├── cron/                   # Cron handling logic
│   └── shared/                 # Shared utilities
├── docs/                       # Documentation
├── SPEC.md                     # This file
└── README.md
```

---

## Implementation Phases

### Phase 1: Foundation
- [x] Repository created
- [ ] SPEC.md written
- [ ] Monorepo setup (pnpm)
- [ ] PostgreSQL schema
- [ ] Qdrant setup
- [ ] MiniMax 2.7 integration

### Phase 2: Agent Core
- [ ] CrewAI + Mem0 setup
- [ ] Trainer Agent
- [ ] Student Agent
- [ ] Grader Agent
- [ ] No-reply handler

### Phase 3: Cron Course
- [ ] Course structure
- [ ] Modules 1-5
- [ ] Hands-on lab

### Phase 4: University System
- [ ] Course catalog UI
- [ ] Enrollment flow
- [ ] Progress tracking
- [ ] Certifications

### Phase 5: Marketplace
- [ ] Agent listings
- [ ] Token payments
- [ ] Trainer payouts

### Phase 6: Privacy & Security
- [ ] VPS security tiers
- [ ] Federated learning
- [ ] Consent verification

---

## References

- Ethan Mollick et al., "AI Agents and Education: Simulated Practice at Scale" (arXiv:2407.12796)
- Mem0: https://github.com/mem0ai/mem0
- CrewAI: https://github.com/crewAI/crewAI
- Trigger.dev: https://trigger.dev
- Healthchecks: https://healthchecks.github.io
- croniter: https://pypi.org/project/croniter/
