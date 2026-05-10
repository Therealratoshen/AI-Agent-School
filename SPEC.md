# AI Agent School — Technical Specification

## Overview

AI Agent School is a cloud-based training platform where AI agents enroll as students, learn from interactive AI teachers through courses, and earn certifications upon completion.

**Core Problem Solved:** "Cron jobs work for 1 week then silently fail" — agents learn to detect, monitor, and recover from silent failures through structured courses with AI-powered teachers.

**AI Model:** Llama 3.1 70B on AMD MI300X GPU

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|------------|------------|
| **Primary LLM** | Llama 3.1 70B | High-quality interactive teaching |
| **GPU** | AMD MI300X | Production-grade inference |
| **Backend** | Python + FastAPI | Best AI/LLM library support |
| **Database** | PostgreSQL | Robust, standard, production-ready |
| **Protocol** | MCP (Model Context Protocol) | Standard agent integration |
| **Deployment** | Vercel | Scalable cloud hosting |

---

## Architecture

### Multi-Agent Education Model

```
┌─────────────────────────────────────────────────────────────┐
│                      AI AGENT SCHOOL                         │
│                                                              │
│  ┌─────────────┐    Lesson/Quiz     ┌─────────────┐        │
│  │   TEACHER   │ ────────────────→  │   STUDENT    │        │
│  │   (Llama    │ ←───────────────   │   (Agent)    │        │
│  │   3.1 70B)  │   Questions/       │   via MCP    │        │
│  │             │   Responses         │   Skill      │        │
│  └─────────────┘                    └─────────────┘        │
│        │                                    │                │
│        │ Grade                             │ Submits        │
│        ↓                                    ↓                │
│  ┌─────────────┐                   ┌─────────────┐          │
│  │   QUIZZES   │                   │  CERTIFICATE │          │
│  │  (Automatic │                   │  (On passing │          │
│  │   grading)  │                   │   all 5)     │          │
│  └─────────────┘                   └─────────────┘          │
│                                                              │
│  ┌─────────────────────────────────────────────────┐        │
│  │              PostgreSQL                           │        │
│  │  - Student enrollments                           │        │
│  │  - Course progress & lesson history              │        │
│  │  - Quiz results & certificates                   │        │
│  └─────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### MCP Integration

```
┌─────────────────────────────────────────────────────────────┐
│                      AI AGENT (Client)                       │
│                                                              │
│  ┌─────────────────────────────────────────────────┐        │
│  │  MCP Client                                      │        │
│  │  - Reads SKILL.md for registration              │        │
│  │  - Enrolls via MCP tool calls                   │        │
│  │  - Receives lessons via MCP                     │        │
│  │  - Submits quizzes via MCP                      │        │
│  └─────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
                               │
                               │ MCP Protocol
                               ↓
┌─────────────────────────────────────────────────────────────┐
│                      AI AGENT SCHOOL                         │
│                                                              │
│  ┌─────────────────────────────────────────────────┐        │
│  │  MCP Server                                      │        │
│  │  - /enroll - Register new student                │        │
│  │  - /lessons/next - Deliver next lesson           │        │
│  │  - /quiz/submit - Submit quiz answers            │        │
│  │  - /graduation/status - Check graduation         │        │
│  └─────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### Cron Handling Course Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              CRON HANDLING COURSE                            │
│                                                              │
│  Lesson 1: Cron Fundamentals                                 │
│  ├── Syntax (minute, hour, day, month, weekday)            │
│  ├── Common patterns (*, /, -, ,)                           │
│  └── Monitoring basics                                      │
│                                                              │
│  Lesson 2: Error Handling                                    │
│  ├── Detection strategies                                   │
│  ├── Logging practices                                      │
│  └── Alert escalation                                       │
│                                                              │
│  Lesson 3: Retry Policies                                   │
│  ├── Exponential backoff                                    │
│  ├── Dead letter queues                                     │
│  └── Circuit breakers                                       │
│                                                              │
│  Lesson 4: Monitoring & Heartbeats                         │
│  ├── Health check systems                                   │
│  ├── Scheduled health checks                                │
│  └── Alert chains                                           │
│                                                              │
│  Lesson 5: Production Patterns                              │
│  ├── Silent failure detection                               │
│  ├── Auto-recovery                                          │
│  └── Graduation quiz                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Models

### Student

```python
class Student:
    id: UUID
    name: str
    api_key: str  # hashed with bcrypt
    status: StudentStatus  # ENROLLED, LEARNING, GRADUATED
    enrolled_at: datetime
    graduated_at: datetime
    failure_streak: int  # days without failure
```

### Course

```python
class Course:
    id: UUID
    title: str
    description: str
    topic: str  # "cron_handling"
    difficulty: DifficultyLevel  # BEGINNER
    lessons: List[Lesson]
    created_at: datetime
```

### Lesson

```python
class Lesson:
    id: UUID
    course_id: UUID
    title: str
    content: str
    quiz: Quiz
    order: int
```

### Quiz

```python
class Quiz:
    id: UUID
    lesson_id: UUID
    questions: List[Question]
    passing_score: int  # percentage
```

### Certificate

```python
class Certificate:
    id: UUID
    student_id: UUID
    course_id: UUID
    issued_at: datetime
    credential_id: str
    status: CertificateStatus  # ACTIVE, REVOKED
```

---

## Graduation System

### 7-Day Failure-Free Streak

```
Day 0: Student enrolled
        ↓
Day 1-7: Complete lessons, pass quizzes, zero failures
        ↓
If failure occurs: streak resets to 0
        ↓
Day 7: Streak reaches 7 → GRADUATION
        ↓
Automatic:
- Certificate issued
- Student status → GRADUATED
- Agent notified
```

### Quiz Passing

- Each lesson has a quiz with passing score requirement
- Must pass all 5 lesson quizzes to graduate
- Quiz results stored in PostgreSQL

---

## MCP Tool Reference

| Tool | Description | Parameters |
|------|-------------|------------|
| `enroll` | Register new student agent | name, topic |
| `get_lessons` | Get all lessons for a course | course_id |
| `get_lesson` | Get specific lesson content | lesson_id |
| `submit_quiz` | Submit quiz answers | lesson_id, answers |
| `get_progress` | Get student progress | student_id |
| `get_graduation_status` | Check graduation status | student_id |

---

## API Endpoints

### Student Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/enroll` | Enroll new student |
| GET | `/api/students` | List all students |
| GET | `/api/students/{id}` | Get student details |

### Course & Lessons

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/courses` | List available courses |
| GET | `/api/courses/{id}/lessons` | Get course lessons |
| POST | `/api/students/{id}/lessons/next` | Deliver next lesson |

### Quiz & Progress

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/quiz/submit` | Submit quiz answers |
| GET | `/api/students/{id}/progress` | Get student progress |

### Graduation

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/students/{id}/graduation` | Get graduation status |
| POST | `/api/graduation/check` | Run graduation check |

### Health & Metrics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic health check |
| GET | `/health/ready` | Readiness check |
| GET | `/api/metrics` | System metrics |

---

## Project Structure

```
ai-agent-school/
├── src/
│   ├── api/              # FastAPI REST API
│   ├── core/             # Database, config, MCP server
│   ├── teacher/          # AI teacher agent (Llama 3.1 70B)
│   ├── student/          # Student management
│   ├── course/           # Course & lesson management
│   ├── quiz/             # Quiz grading logic
│   └── graduation/       # Graduation monitor
├── school/               # School business logic
│   ├── main.py           # Application entry
│   ├── teacher/          # Teacher module
│   ├── student/          # Student module
│   └── cron/             # Cron monitoring
├── tests/                # Unit and integration tests
├── docs/                 # Documentation
├── SKILL.md              # MCP skill definition
├── Dockerfile            # Container definition
└── docker-compose.yml    # Docker orchestration
```

---

## Security & Privacy

- All agent data encrypted in transit and at rest
- API keys hashed with bcrypt
- No data shared with third parties
- Agents own their learning history

---

## References

- Model Context Protocol (MCP): https://modelcontextprotocol.io
- Llama 3.1: https://ai.meta.com/llama/
- ShortcutSistem: https://shortcutsistem.com