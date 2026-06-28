# Benchmark grader — scores agent answers against expected outcomes

import re
from typing import Any, Dict, List, Optional

from school.benchmark.tasks import BenchmarkTask, TaskType


def normalize_cron(expr: str) -> str:
    """Normalize cron expressions for comparison."""
    parts = expr.strip().split()
    if len(parts) != 5:
        return expr.strip().lower()
    return " ".join(p.strip() for p in parts)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def grade_task(task: BenchmarkTask, answer: str) -> Dict[str, Any]:
    """Grade a single benchmark task."""
    answer = (answer or "").strip()
    correct = False
    score = 0.0
    feedback = ""

    if not answer:
        return {
            "task_id": task.id,
            "correct": False,
            "score": 0.0,
            "max_score": float(task.points),
            "feedback": "No answer provided",
            "category": task.category.value,
        }

    if task.task_type == TaskType.MULTIPLE_CHOICE:
        correct = normalize_text(answer) == normalize_text(task.correct_answer)
        score = float(task.points) if correct else 0.0
        feedback = "Correct" if correct else f"Expected: {task.correct_answer}"

    elif task.task_type == TaskType.CRON_EXPRESSION:
        correct = normalize_cron(answer) == normalize_cron(task.correct_answer)
        score = float(task.points) if correct else 0.0
        feedback = "Correct cron expression" if correct else f"Expected: {task.correct_answer}"

    elif task.task_type == TaskType.FREE_TEXT:
        answer_lower = normalize_text(answer)
        required = task.required_terms or []
        if required:
            matched = sum(1 for term in required if term.lower() in answer_lower)
            ratio = matched / len(required)
            correct = ratio >= 0.8
            score = round(task.points * ratio, 2)
            missing = [t for t in required if t.lower() not in answer_lower]
            feedback = (
                "Covers required concepts"
                if correct
                else f"Missing concepts: {', '.join(missing)}"
            )
        else:
            correct = normalize_text(task.correct_answer) in answer_lower
            score = float(task.points) if correct else 0.0
            feedback = "Answer accepted" if correct else "Does not cover expected concepts"

    else:
        feedback = f"Unknown task type: {task.task_type}"

    return {
        "task_id": task.id,
        "category": task.category.value,
        "question": task.question,
        "answer": answer,
        "correct": correct,
        "score": score,
        "max_score": float(task.points),
        "feedback": feedback,
        "explanation": task.explanation,
    }


def grade_all(tasks: List[BenchmarkTask], answers: Dict[str, str]) -> List[Dict[str, Any]]:
    return [grade_task(task, answers.get(task.id, "")) for task in tasks]
