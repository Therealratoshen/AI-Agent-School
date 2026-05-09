-- AI Agent School - PostgreSQL Schema
-- Production-Grade Database Design

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================
-- CORE TABLES
-- ============================================

-- Schools (Multi-tenant support)
CREATE TABLE schools (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    owner_id TEXT,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_schools_owner ON schools(owner_id);

-- Students
CREATE TABLE students (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'enrolled' CHECK (status IN ('enrolled', 'training', 'production_ready', 'graduated', 'failed')),
    failure_streak INT DEFAULT 0,
    last_failure_at TIMESTAMPTZ,
    current_lesson INT DEFAULT 0,
    enrolled_at TIMESTAMPTZ DEFAULT NOW(),
    graduated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_students_school ON students(school_id);
CREATE INDEX idx_students_status ON students(status);

-- ============================================
-- MESSAGING (Message Queue)
-- ============================================

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('lesson', 'quiz', 'quiz_submission', 'correction', 'heartbeat', 'status', 'error', 'graduation', 'enrollment')),
    payload JSONB NOT NULL DEFAULT '{}',
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'dlq')),
    priority INT DEFAULT 0,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_messages_student ON messages(student_id, status);
CREATE INDEX idx_messages_school ON messages(school_id, status);
CREATE INDEX idx_messages_type ON messages(type);
CREATE INDEX idx_messages_created ON messages(created_at);

-- Message channels for LISTEN/NOTIFY
-- Channel format: school_{school_id}_student_{student_id}

-- ============================================
-- LESSONS & QUIZZES
-- ============================================

CREATE TABLE lessons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    module_number INT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    estimated_minutes INT DEFAULT 30,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(school_id, topic, module_number)
);

CREATE INDEX idx_lessons_school_topic ON lessons(school_id, topic);

CREATE TABLE quizzes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lesson_id UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    question TEXT NOT NULL,
    question_type TEXT DEFAULT 'multiple_choice' CHECK (question_type IN ('multiple_choice', 'free_form', 'fill_blank')),
    options JSONB,
    correct_answer TEXT NOT NULL,
    explanation TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(lesson_id, question_id)
);

CREATE INDEX idx_quizzes_lesson ON quizzes(lesson_id);

-- ============================================
-- MISTAKES & CORRECTIONS (Self-Correction Loop)
-- ============================================

CREATE TABLE mistakes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    mistake TEXT NOT NULL,
    context JSONB DEFAULT '{}',
    severity TEXT DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    count INT DEFAULT 1,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_mistakes_student ON mistakes(student_id);
CREATE INDEX idx_mistakes_resolved ON mistakes(student_id, resolved);

CREATE TABLE corrections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    mistake_id UUID NOT NULL REFERENCES mistakes(id) ON DELETE CASCADE,
    correction TEXT NOT NULL,
    explanation TEXT,
    root_cause TEXT,
    llm_model TEXT,
    llm_tokens_used INT,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    applied_at TIMESTAMPTZ,
    verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    verified_by TEXT,
    learned BOOLEAN DEFAULT FALSE,
    learned_at TIMESTAMPTZ,
    retry_count INT DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'applied', 'verified', 'learned', 'failed'))
);

CREATE INDEX idx_corrections_student ON corrections(student_id);
CREATE INDEX idx_corrections_mistake ON corrections(mistake_id);
CREATE INDEX idx_corrections_status ON corrections(status);

-- ============================================
-- QUIZ RESULTS
-- ============================================

CREATE TABLE quiz_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    lesson_id UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    score REAL NOT NULL,
    correct_count INT NOT NULL,
    total_count INT NOT NULL,
    answers JSONB NOT NULL DEFAULT '{}',
    feedback TEXT,
    llm_generated BOOLEAN DEFAULT FALSE,
    llm_model TEXT,
    submitted_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_quiz_results_student ON quiz_results(student_id);
CREATE INDEX idx_quiz_results_lesson ON quiz_results(lesson_id);

-- ============================================
-- CRON JOBS & HEARTBEATS
-- ============================================

CREATE TABLE cron_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    schedule TEXT NOT NULL,
    command TEXT,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'failed', 'healing', 'dlq')),
    last_heartbeat TIMESTAMPTZ,
    heartbeat_interval INT DEFAULT 300,
    grace_periods INT DEFAULT 2,
    failure_count INT DEFAULT 0,
    max_failures INT DEFAULT 3,
    last_run_at TIMESTAMPTZ,
    last_run_status TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cron_jobs_student ON cron_jobs(student_id);
CREATE INDEX idx_cron_jobs_status ON cron_jobs(status);

CREATE TABLE heartbeats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cron_job_id UUID NOT NULL REFERENCES cron_jobs(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'ok' CHECK (status IN ('ok', 'late', 'missed')),
    response_time_ms INT,
    details JSONB DEFAULT '{}'
);

CREATE INDEX idx_heartbeats_job ON heartbeats(cron_job_id, timestamp DESC);

-- ============================================
-- DAILY STATUS (7-Day Graduation Tracking)
-- ============================================

CREATE TABLE daily_status (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    had_failure BOOLEAN DEFAULT FALSE,
    failure_types JSONB DEFAULT '[]',
    lesson_completed UUID,
    mistake_count INT DEFAULT 0,
    corrections_applied INT DEFAULT 0,
    corrections_learned INT DEFAULT 0,
    quiz_score REAL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(student_id, date)
);

CREATE INDEX idx_daily_status_student ON daily_status(student_id, date DESC);

-- ============================================
-- GRADUATION
-- ============================================

CREATE TABLE graduations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    certificate_id TEXT UNIQUE NOT NULL,
    failure_streak_at_graduation INT NOT NULL,
    lessons_completed INT NOT NULL,
    total_corrections INT NOT NULL,
    total_training_days INT NOT NULL,
    certificate_data JSONB,
    graduated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_graduations_student ON graduations(student_id);
CREATE INDEX idx_graduations_cert ON graduations(certificate_id);

-- ============================================
-- DEAD LETTER QUEUE
-- ============================================

CREATE TABLE dead_letter_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    student_id UUID REFERENCES students(id) ON DELETE SET NULL,
    original_type TEXT NOT NULL,
    original_payload JSONB NOT NULL,
    error_message TEXT,
    error_trace TEXT,
    retry_count INT DEFAULT 0,
    status TEXT DEFAULT 'pending_review' CHECK (status IN ('pending_review', 'retrying', 'resolved', 'escalated')),
    reviewed_by TEXT,
    review_action TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_dlq_school ON dead_letter_queue(school_id);
CREATE INDEX idx_dlq_status ON dead_letter_queue(status);

-- ============================================
-- NOTIFICATIONS (Owner Alerts)
-- ============================================

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    student_id UUID REFERENCES students(id) ON DELETE SET NULL,
    type TEXT NOT NULL CHECK (type IN ('graduation', 'dlq_entry', 'critical_failure', 'student_failed', 'system_alert')),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    priority TEXT DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'critical')),
    read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notifications_school ON notifications(school_id, read);
CREATE INDEX idx_notifications_student ON notifications(student_id);

-- ============================================
-- SYSTEM METRICS (For Monitoring)
-- ============================================

CREATE TABLE system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    metric_labels JSONB DEFAULT '{}',
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_metrics_name_time ON system_metrics(metric_name, recorded_at DESC);

-- ============================================
-- FUNCTIONS & TRIGGERS
-- ============================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to tables with updated_at column
CREATE TRIGGER schools_updated_at BEFORE UPDATE ON schools
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER students_updated_at BEFORE UPDATE ON students
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER lessons_updated_at BEFORE UPDATE ON lessons
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER cron_jobs_updated_at BEFORE UPDATE ON cron_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Function to increment mistake count
CREATE OR REPLACE FUNCTION increment_mistake_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE mistakes
    SET count = count + 1,
        last_seen = NOW()
    WHERE id = NEW.mistake_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER corrections_after_insert AFTER INSERT ON corrections
    FOR EACH ROW EXECUTE FUNCTION increment_mistake_count();

-- Function to check failure streak for graduation
CREATE OR REPLACE FUNCTION check_graduation_streak()
RETURNS TABLE (
    student_id UUID,
    consecutive_days INT
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE streak AS (
        SELECT
            ds.student_id,
            ds.date,
            ds.had_failure,
            1 AS day_num,
            ARRAY[ds.date] AS dates
        FROM daily_status ds
        WHERE ds.date = CURRENT_DATE

        UNION ALL

        SELECT
            ds.student_id,
            ds.date,
            ds.had_failure,
            s.day_num + 1,
            s.dates || ds.date
        FROM daily_status ds
        JOIN streak s ON ds.student_id = s.student_id
            AND ds.date = s.date - INTERVAL '1 day'
        WHERE NOT ds.had_failure
    )
    SELECT
        student_id,
        MAX(day_num) AS consecutive_days
    FROM streak
    GROUP BY student_id
    HAVING MAX(day_num) >= 7;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- INITIAL DATA
-- ============================================

-- Insert default school for single-tenant mode
INSERT INTO schools (id, name, owner_id, config)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Default School',
    'system',
    '{"mode": "single_tenant"}'
);

-- Insert Cron Handling course lessons for default school
INSERT INTO lessons (school_id, topic, module_number, title, content, estimated_minutes) VALUES
('00000000-0000-0000-0000-000000000001', 'cron_handling', 1, 'Cron Fundamentals',
'# Module 1: Cron Fundamentals

## Learning Objectives
- Understand cron expression syntax
- Write common cron patterns
- Interpret scheduling requests

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
', 30),

('00000000-0000-0000-0000-000000000001', 'cron_handling', 2, 'Heartbeat Monitoring',
'# Module 2: Heartbeat Monitoring

## The Problem
Cron jobs run silently. If they fail, nobody knows until something breaks.

## Heartbeat Pattern
A heartbeat is a periodic signal sent by a job to confirm it is alive.

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
WHERE job_id = "123";
```

## Heartbeat Frequency
- Too frequent: Adds load
- Too rare: Long detection time for failures

Recommended intervals:
- Quick jobs (< 1 min): Heartbeat every 30 seconds
- Standard jobs (5-60 min): Heartbeat every 1-5 minutes
- Long jobs (1+ hour): Heartbeat at start, end, and periodic
', 30),

('00000000-0000-0000-0000-000000000001', 'cron_handling', 3, 'Silent Failure Detection',
'# Module 3: Silent Failure Detection

## The Core Problem
"Works for 1 week, then silently fails"

## Why Silent Failures Happen
1. Job crashes but system thinks it is still running
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
', 30),

('00000000-0000-0000-0000-000000000001', 'cron_handling', 4, 'Auto-Recovery',
'# Module 4: Auto-Recovery

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
    lock_fd = open(lock_file, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        return True
    except IOError:
        return False
```
', 30),

('00000000-0000-0000-0000-000000000001', 'cron_handling', 5, 'Hands-on Lab: Self-Healing Cron Agent',
'# Module 5: Hands-on Lab: Build a Self-Healing Cron Agent

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
        "every day 3pm": "0 15 * * *",
        "every 5 minutes": "*/5 * * * *",
        "every hour": "0 * * * *",
        "every Monday": "0 9 * * 1",
    }
    return patterns.get(natural_schedule, "* * * * *")
```

### Step 2: Create Cron Job
```python
def create_cron_job(name: str, schedule: str, command: str):
    cron_line = f"{schedule} {command} >> /var/log/{name}.log 2>&1"
    subprocess.run(f"(crontab -l; echo \"{cron_line}\") | crontab -", shell=True)
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

## Success Criteria
- [ ] Parse "every 5 minutes" → */5 * * * *
- [ ] Create working cron job
- [ ] Heartbeat pings every interval
- [ ] Detects missed heartbeats after 2 intervals
- [ ] Auto-restarts on failure
- [ ] Moves to DLQ after 3 failed retries
', 60);

-- Insert quizzes for each lesson
INSERT INTO quizzes (lesson_id, question_id, question, question_type, options, correct_answer, explanation)
SELECT
    l.id,
    q.question_id,
    q.question,
    q.question_type,
    q.options,
    q.correct_answer,
    q.explanation
FROM lessons l,
(VALUES
    (1, 'q1', 'What does "*/5 * * * *" mean?', 'multiple_choice',
     '["Every 5 hours", "Every 5 minutes", "Every 5 seconds", "Every 5 days"]',
     'Every 5 minutes',
     '*/5 means "every 5 units" - so every 5 minutes'),
    (1, 'q2', 'Write cron for "every day at 3pm"', 'fill_blank',
     NULL,
     '0 15 * * *',
     '0 = minute 0, 15 = hour 15 (3pm in 24h format), * = every day'),
    (1, 'q3', 'What is "0 9 * * 1" in plain English?', 'multiple_choice',
     '["Every day at 9am", "Every Monday at 9am", "Every 1st of month at 9am", "Monday at 9pm"]',
     'Every Monday at 9am',
     '0 = minute 0, 9 = hour 9, * = every day, * = every month, 1 = Monday'),

    (2, 'q1', 'What is the purpose of a heartbeat in cron monitoring?', 'multiple_choice',
     '["To make the job run faster", "To confirm the job is alive and running", "To restart the job", "To send emails"]',
     'To confirm the job is alive and running',
     'Heartbeat is a signal that confirms the job is still running properly'),
    (2, 'q2', 'How often should a 5-minute cron job send heartbeats?', 'multiple_choice',
     '["Every 30 seconds", "Every 5 minutes", "Every hour", "Once a day"]',
     'Every 5 minutes',
     'Heartbeat should match or be slightly less than job interval'),

    (3, 'q1', 'What is a "zombie job"?', 'multiple_choice',
     '["A job that runs at midnight", "A job that appears to be running but is not doing any work", "A job that never runs", "A job that crashes immediately"]',
     'A job that appears to be running but is not doing any work',
     'Zombie jobs have a running process but are not actually doing work'),
    (3, 'q2', 'What should trigger a "failed" status?', 'multiple_choice',
     '["1 missed heartbeat", "2 or more missed heartbeats", "No heartbeats at all", "Heartbeat every minute"]',
     '2 or more missed heartbeats',
     'With grace periods, 2+ missed heartbeats indicates actual failure'),

    (4, 'q1', 'What is exponential backoff?', 'multiple_choice',
     '["Waiting longer between each retry attempt", "Making the job run faster", "Stopping retries immediately", "Restarting the server"]',
     'Waiting longer between each retry attempt',
     'Exponential backoff increases delay between retries exponentially'),
    (4, 'q2', 'What is a Dead Letter Queue (DLQ)?', 'multiple_choice',
     '["A queue of jobs waiting to run", "A queue for jobs that failed beyond recovery", "A list of deleted jobs", "A queue for new jobs"]',
     'A queue for jobs that failed beyond recovery',
     'DLQ holds jobs that could not be recovered after max retries'),

    (5, 'q1', 'What is the correct cron for "every 5 minutes"?', 'multiple_choice',
     '["5 * * * *", "*/5 * * * *", "0 */5 * * *", "* */5 * * *"]',
     '*/5 * * * *',
     '*/5 means every 5 minutes'),
    (5, 'q2', 'How many retries should happen before moving to DLQ?', 'multiple_choice',
     '["1", "2", "3", "5"]',
     '3',
     'Standard practice is 3 retries before DLQ')
) AS q(module_num, question_id, question, question_type, options, correct_answer, explanation)
WHERE l.module_number = q.module_num AND l.topic = 'cron_handling';