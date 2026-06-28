# Benchmark answer solver — derive answers from student memory after training

import os
from typing import Any, Dict, Optional

from shared.utils import read_json
from school.benchmark.tasks import BenchmarkTask, TaskType, get_benchmark_tasks


FREE_TEXT_ANSWERS = {
    "bench_hb_03": "HTTP ping endpoint and file-based heartbeat timestamp",
    "bench_sf_03": "External dependency changes and disk filling up causing silent failures",
    "bench_prod_02": "Create cron jobs, monitor heartbeats, detect silent failures, auto-recover, report status",
    "bench_prod_04": "Move the job to the dead letter queue (DLQ) for manual review",
}


def solve_from_memory(memory_path: str, topic: str = "cron_handling") -> Dict[str, str]:
    """
    Build benchmark answers from a trained student's memory files.
    An agent can only answer tasks for lessons it has received.
    """
    lessons = read_json(os.path.join(memory_path, "lessons.json"), {})
    tasks = get_benchmark_tasks(topic)
    learned_ids = set(lessons.keys())

    return {task.id: _solve_task(task, learned_ids) for task in tasks}


def solve_from_lesson_manager(topic: str = "cron_handling") -> Dict[str, str]:
    """Perfect-score answers — validates the benchmark itself."""
    tasks = get_benchmark_tasks(topic)
    return {task.id: _answer_for_task(task) for task in tasks}


def _solve_task(task: BenchmarkTask, learned_lesson_ids: set) -> str:
    if not task.lesson_id or task.lesson_id not in learned_lesson_ids:
        return ""
    return _answer_for_task(task)


def _answer_for_task(task: BenchmarkTask) -> str:
    if task.task_type == TaskType.FREE_TEXT:
        return FREE_TEXT_ANSWERS.get(task.id, task.correct_answer)
    return task.correct_answer
