# Cron Handling Benchmark — measures whether an agent learned production cron skills

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    CRON_EXPRESSION = "cron_expression"
    FREE_TEXT = "free_text"


class BenchmarkCategory(str, Enum):
    CRON_FUNDAMENTALS = "cron_fundamentals"
    HEARTBEAT_MONITORING = "heartbeat_monitoring"
    SILENT_FAILURE_DETECTION = "silent_failure_detection"
    AUTO_RECOVERY = "auto_recovery"
    PRODUCTION_PATTERNS = "production_patterns"


@dataclass
class BenchmarkTask:
    id: str
    category: BenchmarkCategory
    task_type: TaskType
    question: str
    correct_answer: str
    options: Optional[List[str]] = None
    required_terms: Optional[List[str]] = None
    points: int = 1
    lesson_id: Optional[str] = None
    explanation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "task_type": self.task_type.value,
            "question": self.question,
            "options": self.options,
            "points": self.points,
            "lesson_id": self.lesson_id,
        }


# Passing thresholds (aligned with graduation quiz rules)
BENCHMARK_PASS_SCORE = 70.0
BENCHMARK_CATEGORY_MIN_SCORE = 60.0

CRON_HANDLING_BENCHMARK: List[BenchmarkTask] = [
    # --- Module 1: Cron Fundamentals ---
    BenchmarkTask(
        id="bench_cron_01",
        category=BenchmarkCategory.CRON_FUNDAMENTALS,
        task_type=TaskType.MULTIPLE_CHOICE,
        question="What does '*/5 * * * *' mean?",
        options=["Every 5 hours", "Every 5 minutes", "Every 5 seconds", "Every 5 days"],
        correct_answer="Every 5 minutes",
        lesson_id="cron_01",
    ),
    BenchmarkTask(
        id="bench_cron_02",
        category=BenchmarkCategory.CRON_FUNDAMENTALS,
        task_type=TaskType.CRON_EXPRESSION,
        question="Write the cron expression for 'every day at 3pm'",
        correct_answer="0 15 * * *",
        lesson_id="cron_01",
        explanation="Minute 0, hour 15 (3pm), every day/month/weekday",
    ),
    BenchmarkTask(
        id="bench_cron_03",
        category=BenchmarkCategory.CRON_FUNDAMENTALS,
        task_type=TaskType.CRON_EXPRESSION,
        question="Write the cron expression for 'every Monday at 9am'",
        correct_answer="0 9 * * 1",
        lesson_id="cron_01",
    ),
    BenchmarkTask(
        id="bench_cron_04",
        category=BenchmarkCategory.CRON_FUNDAMENTALS,
        task_type=TaskType.CRON_EXPRESSION,
        question="Write the cron for 'setiap 5 menit' (every 5 minutes)",
        correct_answer="*/5 * * * *",
        lesson_id="cron_01",
    ),
    BenchmarkTask(
        id="bench_cron_05",
        category=BenchmarkCategory.CRON_FUNDAMENTALS,
        task_type=TaskType.MULTIPLE_CHOICE,
        question="Which cron field represents the day of week (0=Sunday)?",
        options=["First field", "Third field", "Fifth field", "Second field"],
        correct_answer="Fifth field",
        lesson_id="cron_01",
    ),

    # --- Module 2: Heartbeat Monitoring ---
    BenchmarkTask(
        id="bench_hb_01",
        category=BenchmarkCategory.HEARTBEAT_MONITORING,
        task_type=TaskType.MULTIPLE_CHOICE,
        question="What is the primary purpose of a cron heartbeat?",
        options=[
            "Speed up job execution",
            "Confirm the job is alive and running",
            "Delete old log files",
            "Schedule the next run",
        ],
        correct_answer="Confirm the job is alive and running",
        lesson_id="cron_02",
    ),
    BenchmarkTask(
        id="bench_hb_02",
        category=BenchmarkCategory.HEARTBEAT_MONITORING,
        task_type=TaskType.MULTIPLE_CHOICE,
        question="For a cron job that runs every 5 minutes, how often should it heartbeat?",
        options=["Every 30 seconds", "Every 5 minutes", "Once per day", "Only at startup"],
        correct_answer="Every 5 minutes",
        lesson_id="cron_02",
    ),
    BenchmarkTask(
        id="bench_hb_03",
        category=BenchmarkCategory.HEARTBEAT_MONITORING,
        task_type=TaskType.FREE_TEXT,
        question="Name two ways to implement a heartbeat for a cron job.",
        correct_answer="http ping file database",
        required_terms=["http", "file"],
        lesson_id="cron_02",
        explanation="HTTP ping (e.g. healthchecks.io) or file/database timestamp updates",
    ),

    # --- Module 3: Silent Failure Detection ---
    BenchmarkTask(
        id="bench_sf_01",
        category=BenchmarkCategory.SILENT_FAILURE_DETECTION,
        task_type=TaskType.MULTIPLE_CHOICE,
        question="What is a 'zombie cron job'?",
        options=[
            "A job scheduled at midnight",
            "A job that appears running but produces no work",
            "A job that never starts",
            "A job deleted from crontab",
        ],
        correct_answer="A job that appears running but produces no work",
        lesson_id="cron_03",
    ),
    BenchmarkTask(
        id="bench_sf_02",
        category=BenchmarkCategory.SILENT_FAILURE_DETECTION,
        task_type=TaskType.MULTIPLE_CHOICE,
        question="How many missed heartbeats should trigger a 'failed' status (with grace_periods=2)?",
        options=["1", "2 or more", "10", "Never"],
        correct_answer="2 or more",
        lesson_id="cron_03",
    ),
    BenchmarkTask(
        id="bench_sf_03",
        category=BenchmarkCategory.SILENT_FAILURE_DETECTION,
        task_type=TaskType.FREE_TEXT,
        question="List two common causes of silent cron failures.",
        correct_answer="dependency disk memory",
        required_terms=["disk", "dependency"],
        lesson_id="cron_03",
        explanation="External API changes, disk full, OOM kills, expired env vars",
    ),

    # --- Module 4: Auto-Recovery ---
    BenchmarkTask(
        id="bench_ar_01",
        category=BenchmarkCategory.AUTO_RECOVERY,
        task_type=TaskType.MULTIPLE_CHOICE,
        question="What is exponential backoff?",
        options=[
            "Waiting longer between each retry",
            "Running jobs in parallel",
            "Deleting failed jobs immediately",
            "Doubling CPU allocation",
        ],
        correct_answer="Waiting longer between each retry",
        lesson_id="cron_04",
    ),
    BenchmarkTask(
        id="bench_ar_02",
        category=BenchmarkCategory.AUTO_RECOVERY,
        task_type=TaskType.MULTIPLE_CHOICE,
        question="What is a Dead Letter Queue (DLQ) used for?",
        options=[
            "Jobs waiting to be scheduled",
            "Jobs that failed beyond recovery attempts",
            "Successful job history",
            "User notification inbox",
        ],
        correct_answer="Jobs that failed beyond recovery attempts",
        lesson_id="cron_04",
    ),
    BenchmarkTask(
        id="bench_ar_03",
        category=BenchmarkCategory.AUTO_RECOVERY,
        task_type=TaskType.MULTIPLE_CHOICE,
        question="How many retries should occur before moving a job to the DLQ?",
        options=["1", "2", "3", "10"],
        correct_answer="3",
        lesson_id="cron_04",
    ),

    # --- Module 5: Production Patterns ---
    BenchmarkTask(
        id="bench_prod_01",
        category=BenchmarkCategory.PRODUCTION_PATTERNS,
        task_type=TaskType.CRON_EXPRESSION,
        question="Convert natural language 'setiap hari jam 3 sore' to a cron expression",
        correct_answer="0 15 * * *",
        lesson_id="cron_05",
    ),
    BenchmarkTask(
        id="bench_prod_02",
        category=BenchmarkCategory.PRODUCTION_PATTERNS,
        task_type=TaskType.FREE_TEXT,
        question="What are the 5 capabilities of a self-healing cron agent?",
        correct_answer="create monitor detect recover report",
        required_terms=["monitor", "detect", "recover"],
        lesson_id="cron_05",
        explanation="Create jobs, monitor heartbeats, detect failures, auto-recover, report status",
    ),
    BenchmarkTask(
        id="bench_prod_03",
        category=BenchmarkCategory.PRODUCTION_PATTERNS,
        task_type=TaskType.MULTIPLE_CHOICE,
        question="Within how many heartbeat intervals should silent failure be detected?",
        options=["1 interval", "2 intervals", "24 hours", "1 week"],
        correct_answer="2 intervals",
        lesson_id="cron_05",
    ),
    BenchmarkTask(
        id="bench_prod_04",
        category=BenchmarkCategory.PRODUCTION_PATTERNS,
        task_type=TaskType.FREE_TEXT,
        question="What should happen after 3 failed auto-recovery attempts?",
        correct_answer="dead letter queue dlq",
        required_terms=["dlq", "dead letter"],
        lesson_id="cron_05",
    ),
]


def get_benchmark_tasks(topic: str = "cron_handling") -> List[BenchmarkTask]:
    if topic == "cron_handling":
        return list(CRON_HANDLING_BENCHMARK)
    return list(CRON_HANDLING_BENCHMARK)


def get_tasks_by_category(tasks: List[BenchmarkTask]) -> Dict[str, List[BenchmarkTask]]:
    grouped: Dict[str, List[BenchmarkTask]] = {}
    for task in tasks:
        grouped.setdefault(task.category.value, []).append(task)
    return grouped
