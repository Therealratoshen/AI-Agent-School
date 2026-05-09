# Lesson Manager - Manages course content and quizzes

import os
import sys
from typing import Dict, Any, List, Optional
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared import generate_id, timestamp

class LessonContent:
    """Represents a lesson with content and quiz"""

    def __init__(self, module_id: str, title: str, content: str,
                 quiz: List[Dict[str, Any]], estimated_minutes: int = 30):
        self.id = module_id
        self.title = title
        self.content = content
        self.quiz = quiz
        self.estimated_minutes = estimated_minutes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "quiz": self.quiz,
            "estimated_minutes": self.estimated_minutes
        }

class LessonManager:
    """Manages lessons for a topic"""

    def __init__(self, topic: str):
        self.topic = topic
        self.lessons: Dict[int, LessonContent] = {}
        self._load_lessons()

    def _load_lessons(self):
        """Load lessons based on topic"""
        if self.topic == "cron_handling":
            self._load_cron_handling_lessons()
        elif self.topic == "memory_management":
            self._load_memory_management_lessons()
        else:
            self._load_cron_handling_lessons()

    def _load_cron_handling_lessons(self):
        """Load Cron Handling course - Module 1"""
        self.lessons[1] = LessonContent(
            module_id="cron_01",
            title="Cron Fundamentals",
            estimated_minutes=30,
            content="""# Module 1: Cron Fundamentals

## Learning Objectives
- Understand cron expression syntax
- Write common cron patterns
- Interpret Indonesian scheduling requests

## Cron Expression Format
```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6)
* * * * *
```

## Special Characters
| Character | Meaning | Example |
|-----------|---------|---------|
| * | Any value | * * * * * = every minute |
| , | List | 1,15 * * * * = minute 1 and 15 |
| - | Range | 0 9-17 * * * = every hour 9am-5pm |
| / | Step | */5 * * * * = every 5 minutes |

## Common Patterns
- `0 * * * *` = Every hour at minute 0
- `0 0 * * *` = Daily at midnight
- `0 0 * * 0` = Weekly on Sunday
- `0 0 1 * *` = Monthly on 1st
- `*/5 * * * *` = Every 5 minutes
- `0 15 * * 1-5` = Weekdays at 3pm

## Indonesian Examples
- "setiap jam" → `0 * * * *`
- "setiap jam 5 menit" → `*/5 * * * *`
- "setiap hari jam 3 sore" → `0 15 * * *`
- "setiap Senin pagi" → `0 9 * * 1`
""",
            quiz=[
                {
                    "id": "q1",
                    "question": "What does '*/5 * * * *' mean?",
                    "options": [
                        "Every 5 hours",
                        "Every 5 minutes",
                        "Every 5 seconds",
                        "Every 5 days"
                    ],
                    "correct_answer": "Every 5 minutes"
                },
                {
                    "id": "q2",
                    "question": "Write cron for 'every day at 3pm'",
                    "options": None,
                    "correct_answer": "0 15 * * *",
                    "explanation": "0 = minute 0, 15 = hour 15 (3pm in 24h format), * = every day, * = every month, * = every day of week"
                },
                {
                    "id": "q3",
                    "question": "What is '0 9 * * 1' in plain English?",
                    "options": [
                        "Every day at 9am",
                        "Every Monday at 9am",
                        "Every 1st of month at 9am",
                        "Monday at 9pm"
                    ],
                    "correct_answer": "Every Monday at 9am"
                }
            ]
        )

        self.lessons[2] = LessonContent(
            module_id="cron_02",
            title="Heartbeat Monitoring",
            estimated_minutes=30,
            content="""# Module 2: Heartbeat Monitoring

## The Problem
Cron jobs run silently. If they fail, nobody knows until something breaks.

## Heartbeat Pattern
A heartbeat is a periodic signal sent by a job to confirm it's alive.

```
┌─────────────┐    heartbeat ping    ┌─────────────┐
│   Cron Job  │ ───────────────────→ │  Monitoring │
│             │ ←──────────────────── │    Service   │
└─────────────┘    "I'm alive"        └─────────────┘
```

## Implementation Options

### 1. HTTP Ping (Healthchecks.io style)
```python
import httpx
import time

while True:
    # Do work...
    httpx.get("https://hc-ping.com/UUID")
    time.sleep(300)  # Every 5 minutes
```

### 2. File-based Heartbeat
```python
from datetime import datetime
import os

def ping():
    with open("/tmp/cron_heartbeat", "w") as f:
        f.write(datetime.utcnow().isoformat())
```

### 3. Database Heartbeat
```sql
UPDATE cron_jobs
SET last_heartbeat = NOW()
WHERE job_id = '123';
```

## Heartbeat Frequency
- Too frequent: Adds load
- Too rare: Long detection time for failures

Recommended intervals:
- Quick jobs (< 1 min): Heartbeat every 30 seconds
- Standard jobs (5-60 min): Heartbeat every 1-5 minutes
- Long jobs (1+ hour): Heartbeat at start, end, and periodic
""",
            quiz=[
                {
                    "id": "q1",
                    "question": "What is the purpose of a heartbeat in cron monitoring?",
                    "options": [
                        "To make the job run faster",
                        "To confirm the job is alive and running",
                        "To restart the job",
                        "To send emails"
                    ],
                    "correct_answer": "To confirm the job is alive and running"
                },
                {
                    "id": "q2",
                    "question": "How often should a 5-minute cron job send heartbeats?",
                    "options": [
                        "Every 30 seconds",
                        "Every 5 minutes",
                        "Every hour",
                        "Once a day"
                    ],
                    "correct_answer": "Every 5 minutes"
                }
            ]
        )

        self.lessons[3] = LessonContent(
            module_id="cron_03",
            title="Silent Failure Detection",
            estimated_minutes=30,
            content="""# Module 3: Silent Failure Detection

## The Core Problem
"Works for 1 week, then silently fails"

## Why Silent Failures Happen
1. Job crashes but system thinks it's still running
2. External dependency changes (API version, schema)
3. Environment variables expire or change
4. Disk fills up
5. Memory leaks cause OOM kills
6. Network routes change

## Detection Strategies

### 1. Expected vs Actual Pattern
```
Expected: Job runs every 5 minutes = 288 times/day
Actual: Job ran 200 times on Day 7, 0 times on Day 8
```

### 2. Missed Heartbeat Detection
```python
from datetime import datetime, timedelta

def check_failure(last_heartbeat, interval_seconds=300):
    if last_heartbeat is None:
        return {"status": "unknown"}

    elapsed = (datetime.utcnow() - last_heartbeat).total_seconds()

    if elapsed > interval_seconds * 2:
        return {
            "status": "failed",
            "missed_heartbeats": int(elapsed / interval_seconds),
            "elapsed_seconds": elapsed
        }

    return {"status": "healthy"}
```

### 3. Zombie Job Detection
Signs:
- CPU usage is 0% but process exists
- No new logs being written
- Memory usage unchanged for hours
""",
            quiz=[
                {
                    "id": "q1",
                    "question": "What is a 'zombie job'?",
                    "options": [
                        "A job that runs at midnight",
                        "A job that appears to be running but isn't doing any work",
                        "A job that never runs",
                        "A job that crashes immediately"
                    ],
                    "correct_answer": "A job that appears to be running but isn't doing any work"
                },
                {
                    "id": "q2",
                    "question": "What should trigger a 'failed' status?",
                    "options": [
                        "1 missed heartbeat",
                        "2 or more missed heartbeats",
                        "No heartbeats at all",
                        "Heartbeat every minute"
                    ],
                    "correct_answer": "2 or more missed heartbeats"
                }
            ]
        )

        self.lessons[4] = LessonContent(
            module_id="cron_04",
            title="Auto-Recovery",
            estimated_minutes=30,
            content="""# Module 4: Auto-Recovery

## Recovery Strategies

### 1. Automatic Restart
```python
import subprocess
import time

def restart_job(job_name, max_retries=3):
    for attempt in range(max_retries):
        result = subprocess.run(["systemctl", "restart", job_name])
        if result.returncode == 0:
            return {"status": "restarted", "attempt": attempt + 1}
        time.sleep(5 * (attempt + 1))  # Exponential backoff
    return {"status": "failed_after_retries", "attempts": max_retries}
```

### 2. Retry Policies

#### Exponential Backoff
```python
import time
import random

def retry_with_backoff(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            delay = 2 ** attempt + random.uniform(0, 1)
            time.sleep(delay)
    raise Exception("All retries failed")
```

### 3. Dead Letter Queue
For jobs that fail repeatedly:
```python
def dead_letter_queue(job_id, error, context):
    dlq_collection.insert({
        "job_id": job_id,
        "error": str(error),
        "context": context,
        "failed_at": datetime.utcnow().isoformat(),
        "status": "pending_review"
    })
```

### 4. Lock Files (Prevent Duplicate Runs)
```python
import fcntl
import os

def acquire_lock(lock_file):
    lock_fd = open(lock_file, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        return True
    except IOError:
        return False
```

## Recovery Decision Tree
```
Job Failed
    │
    ├── Is this a transient error?
    │   ├── Yes → Retry with backoff
    │   └── No → Check if job is stuck
    │            │
    │            ├── Yes → Kill and restart
    │            └── No → Escalate to human
    │
    └── Did max retries exceed?
        ├── Yes → Move to DLQ
        └── No → Retry
```
""",
            quiz=[
                {
                    "id": "q1",
                    "question": "What is exponential backoff?",
                    "options": [
                        "Waiting longer between each retry attempt",
                        "Making the job run faster",
                        "Stopping retries immediately",
                        "Restarting the server"
                    ],
                    "correct_answer": "Waiting longer between each retry attempt"
                },
                {
                    "id": "q2",
                    "question": "What is a Dead Letter Queue (DLQ)?",
                    "options": [
                        "A queue of jobs waiting to run",
                        "A queue for jobs that failed beyond recovery",
                        "A list of deleted jobs",
                        "A queue for new jobs"
                    ],
                    "correct_answer": "A queue for jobs that failed beyond recovery"
                }
            ]
        )

        self.lessons[5] = LessonContent(
            module_id="cron_05",
            title="Hands-on Lab: Self-Healing Cron Agent",
            estimated_minutes=60,
            content="""# Module 5: Hands-on Lab: Build a Self-Healing Cron Agent

## Project Overview
Build an AI agent that:
1. Creates cron jobs from natural language requests
2. Monitors job health via heartbeats
3. Detects silent failures
4. Automatically recovers from failures
5. Reports status to the owner

## Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    Self-Healing Cron Agent                   │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐│
│  │ Natural  │   │   Cron   │   │ Heartbeat│   │ Failure  ││
│  │ Language │──→│  Creator │──→│ Monitor  │──→│ Detector ││
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘│
│                                            │                │
│                                            ▼                │
│                                       ┌──────────┐         │
│                                       │  Auto    │         │
│                                       │ Recovery │         │
│                                       └──────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Steps

### Step 1: Natural Language to Cron
```python
def parse_schedule_to_cron(natural_schedule: str) -> str:
    patterns = {
        "setiap hari jam 3 sore": "0 15 * * *",
        "setiap 5 menit": "*/5 * * * *",
        "setiap jam": "0 * * * *",
        "setiap Senin": "0 9 * * 1",
    }
    return patterns.get(natural_schedule, "* * * * *")
```

### Step 2: Create Cron Job
```python
def create_cron_job(name: str, schedule: str, command: str):
    cron_line = f"{schedule} {command} >> /var/log/{name}.log 2>&1"
    subprocess.run(f"(crontab -l; echo '{cron_line}') | crontab -", shell=True)
```

### Step 3: Add Heartbeat
```python
def add_heartbeat_to_job(job_name: str, interval_seconds: int = 300):
    heartbeat_cmd = f"curl -s https://hc-ping.com/{job_name}-heartbeat"
    cron_line = f"*/{interval_seconds//60} * * * * {heartbeat_cmd}"
```

### Step 4: Monitor and Recover
```python
class SelfHealingCronAgent:
    def __init__(self):
        self.monitor = CronJobMonitor()
        self.detector = SilentFailureDetector()
        self.recovery = AutoRecovery()

    async def check_and_heal(self, job_id: str):
        status = await self.monitor.check_job(job_id)

        if status.status == "failed":
            await self.recovery.auto_heal(job_id)
            await self.notify_owner(job_id, "Auto-healed")

        elif status.status == "critical":
            await self.escalate(job_id)
```

## Deliverable
A Python script that:
1. Accepts natural language cron requests
2. Creates and schedules the job
3. Adds heartbeat monitoring
4. Detects failures within 2 intervals
5. Auto-recovers with 3 retries
6. Reports status

## Success Criteria
- [ ] Parse "setiap 5 menit" → */5 * * * *
- [ ] Create working cron job
- [ ] Heartbeat pings every interval
- [ ] Detects missed heartbeats after 2 intervals
- [ ] Auto-restarts on failure
- [ ] Moves to DLQ after 3 failed retries
""",
            quiz=[
                {
                    "id": "q1",
                    "question": "What is the correct cron for 'setiap 5 menit' (every 5 minutes)?",
                    "options": [
                        "5 * * * *",
                        "*/5 * * * *",
                        "0 */5 * * *",
                        "* */5 * * *"
                    ],
                    "correct_answer": "*/5 * * * *"
                },
                {
                    "id": "q2",
                    "question": "How many retries should happen before moving to DLQ?",
                    "options": [
                        "1",
                        "2",
                        "3",
                        "5"
                    ],
                    "correct_answer": "3"
                }
            ]
        )

    def _load_memory_management_lessons(self):
        """Load Memory Management course"""
        self.lessons[1] = LessonContent(
            module_id="mem_01",
            title="Memory Persistence Fundamentals",
            estimated_minutes=30,
            content="""# Module 1: Memory Persistence

## What is Memory Persistence?
Keeping information available across sessions, even after the agent restarts.

## Why It Matters
Without persistence:
- Corrections vanish after restart
- Same mistakes repeat daily
- Learning is lost

With persistence:
- Corrections saved permanently
- Agent improves over time
- Same mistakes are avoided

## Types of Memory Storage

### 1. File-based
```python
# Save to JSON file
import json

def save_memory(data, filepath):
    with open(filepath, 'w') as f:
        json.dump(data, f)

def load_memory(filepath):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
```

### 2. SQLite
```python
import sqlite3

def save_to_db(key, value):
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO memory VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()
```

### 3. Vector Database (for RAG)
Store embeddings for semantic retrieval.

## Best Practices
1. Always backup before updating
2. Verify writes succeeded
3. Handle corruption gracefully
4. Implement periodic cleanup
""",
            quiz=[
                {
                    "id": "q1",
                    "question": "What happens without memory persistence?",
                    "options": [
                        "Agent runs faster",
                        "Corrections vanish after restart",
                        "Agent becomes smarter",
                        "Nothing changes"
                    ],
                    "correct_answer": "Corrections vanish after restart"
                },
                {
                    "id": "q2",
                    "question": "Why should you backup before updating memory?",
                    "options": [
                        "To make writes faster",
                        "To prevent data loss on corruption",
                        "To save disk space",
                        "To compress data"
                    ],
                    "correct_answer": "To prevent data loss on corruption"
                }
            ]
        )

    def get_lesson(self, number: int) -> Optional[LessonContent]:
        """Get a lesson by number"""
        return self.lessons.get(number)

    def total_lessons(self) -> int:
        """Get total number of lessons"""
        return len(self.lessons)

    def grade_quiz(self, lesson_id: str, answers: Dict[str, str]) -> Dict[str, Any]:
        """Grade a quiz submission"""
        lesson = None
        for l in self.lessons.values():
            if l.id == lesson_id:
                lesson = l
                break

        if not lesson:
            return {"passed": False, "error": "Lesson not found"}

        correct = 0
        total = len(lesson.quiz)
        feedback = []

        for question in lesson.quiz:
            q_id = question["id"]
            correct_answer = question["correct_answer"]
            student_answer = answers.get(q_id, "").strip()

            if student_answer.lower() == correct_answer.lower():
                correct += 1
                feedback.append({
                    "question": question["question"],
                    "correct": True
                })
            else:
                feedback.append({
                    "question": question["question"],
                    "correct": False,
                    "your_answer": student_answer,
                    "correct_answer": correct_answer,
                    "explanation": question.get("explanation", "")
                })

        score = (correct / total) * 100 if total > 0 else 0
        passed = score >= 70

        return {
            "passed": passed,
            "score": score,
            "correct": correct,
            "total": total,
            "feedback": feedback
        }
