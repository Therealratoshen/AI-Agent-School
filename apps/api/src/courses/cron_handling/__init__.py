COURSE_TITLE = "Cron Handling: Silent Failure Detection"
COURSE_TOPIC = "cron_handling"
COURSE_DESCRIPTION = "Learn to detect, monitor, and recover from cron jobs that silently fail. The core problem: jobs work for 1 week then fail without any notification."
TOKEN_COST = 200000


MODULES = [
    {
        "order": 1,
        "title": "Cron Fundamentals",
        "description": "Master cron syntax and scheduling patterns",
        "content": """
# Module 1: Cron Fundamentals

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
│ │ │ │ ┌───────────── day of week (0-6) (Sunday=0)
│ │ │ │ │
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

## Exercise
Write cron expressions for:
1. Run every 15 minutes
2. Run at 6am and 6pm daily
3. Run every Monday at 9am
4. "setiap 30 menit"
""",
    },
    {
        "order": 2,
        "title": "Heartbeat Monitoring",
        "description": "Implement ping systems and health checks for cron jobs",
        "content": """
# Module 2: Heartbeat Monitoring

## The Problem
Cron jobs run silently. If they fail, nobody knows until something breaks.

## Heartbeat Pattern
A heartbeat is a periodic signal sent by a job to confirm it's alive.

```
┌─────────────┐    heartbeat ping    ┌─────────────┐
│   Cron Job  │ ────────────────────→ │  Monitoring │
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

## Exercise
Implement a heartbeat system that:
1. Sends a ping every 5 minutes
2. Records the timestamp
3. Detects if 2+ heartbeats are missed
""",
    },
    {
        "order": 3,
        "title": "Silent Failure Detection",
        "description": "Detect when cron jobs quietly stop working",
        "content": """
# Module 3: Silent Failure Detection

## The Core Problem You Face
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

### 3. Exit Code Tracking
```bash
# Capture exit code
0 * * * * /scripts/backup.sh >> /var/log/backup.log 2>&1
echo $?  # 0 = success, non-zero = failure
```

### 4. Output Validation
```python
def validate_output(output, expected_patterns):
    for pattern in expected_patterns:
        if pattern not in output:
            return False, f"Missing: {pattern}"
    return True, "OK"
```

## Zombie Job Detection
A zombie job appears to be running but isn't doing any work.

Signs:
- CPU usage is 0% but process exists
- No new logs being written
- Memory usage unchanged for hours

## Exercise
Build a silent failure detector that:
1. Tracks expected vs actual execution count
2. Alerts after 2 missed intervals
3. Records the failure reason
""",
    },
    {
        "order": 4,
        "title": "Auto-Recovery",
        "description": "Implement automatic restart and retry policies",
        "content": """
# Module 4: Auto-Recovery

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
def retry_with_backoff(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            delay = 2 ** attempt + random.uniform(0, 1)
            time.sleep(delay)
    raise Exception("All retries failed")
```

#### Linear Backoff
```python
def retry_linear(func, max_retries=3, base_delay=5):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception:
            time.sleep(base_delay * (attempt + 1))
```

### 3. Dead Letter Queue
For jobs that fail repeatedly:
```python
def dead_letter_queue(job_id, error, context):
    # Log to DLQ for manual review
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

### 5. Graceful Degradation
If a cron job fails:
1. Use cached/stale data if available
2. Show "maintenance mode" instead of errors
3. Queue work for later processing

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

## Exercise
Implement an auto-recovery system that:
1. Retries failed jobs 3 times with exponential backoff
2. Moves jobs to DLQ after max retries
3. Sends alerts on escalation
""",
    },
    {
        "order": 5,
        "title": "Hands-on Lab: Self-Healing Cron Agent",
        "description": "Build an AI agent that manages cron jobs with automatic failure detection and recovery",
        "content": """
# Module 5: Hands-on Lab: Build a Self-Healing Cron Agent

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
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │  Natural │   │   Cron   │   │ Heartbeat│   │ Failure  │  │
│  │ Language│──→│  Creator │──→│ Monitor  │──→│ Detector │  │
│  │ Parser  │   │          │   │          │   │          │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
│                                            │                 │
│                                            ▼                 │
│                                       ┌──────────┐          │
│                                       │  Auto    │          │
│                                       │ Recovery │          │
│                                       └──────────┘          │
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
    # Add to crontab
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

## Indonesian Example Request
```
User: "Buat cron job untuk backup database setiap jam 2 pagi"
Agent: Creates cron job: 0 2 * * * /scripts/backup.sh
Agent: Adds heartbeat monitoring
Agent: Sets up failure detection
Agent: Enables auto-recovery
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
    },
]
