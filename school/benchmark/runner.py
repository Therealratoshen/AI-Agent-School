# Benchmark runner — execute benchmarks and produce learning reports

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from school.benchmark.grader import grade_all
from school.benchmark.tasks import (
    BENCHMARK_CATEGORY_MIN_SCORE,
    BENCHMARK_PASS_SCORE,
    BenchmarkTask,
    get_benchmark_tasks,
    get_tasks_by_category,
)


@dataclass
class BenchmarkResult:
    topic: str
    total_score: float
    max_score: float
    percentage: float
    passed: bool
    category_scores: Dict[str, Dict[str, Any]]
    task_results: List[Dict[str, Any]]
    learning_gain: Optional[float] = None
    baseline_percentage: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "total_score": self.total_score,
            "max_score": self.max_score,
            "percentage": round(self.percentage, 1),
            "passed": self.passed,
            "pass_threshold": BENCHMARK_PASS_SCORE,
            "category_min_threshold": BENCHMARK_CATEGORY_MIN_SCORE,
            "category_scores": self.category_scores,
            "task_results": self.task_results,
            "learning_gain": self.learning_gain,
            "baseline_percentage": self.baseline_percentage,
            "certified": self.passed and all(
                c["percentage"] >= BENCHMARK_CATEGORY_MIN_SCORE
                for c in self.category_scores.values()
            ),
        }


class BenchmarkRunner:
    """
    Runs the cron handling benchmark against agent answers.

    Used to verify an AI agent learned the course material before graduation.
    """

    def __init__(self, topic: str = "cron_handling"):
        self.topic = topic
        self.tasks = get_benchmark_tasks(topic)

    def get_tasks(self, include_answers: bool = False) -> List[Dict[str, Any]]:
        """Return benchmark tasks for an agent to answer."""
        result = []
        for task in self.tasks:
            item = task.to_dict()
            if include_answers:
                item["correct_answer"] = task.correct_answer
            result.append(item)
        return result

    def run(self, answers: Dict[str, str], baseline_percentage: Optional[float] = None) -> BenchmarkResult:
        """Grade submitted answers and return a full benchmark result."""
        task_results = grade_all(self.tasks, answers)

        total_score = sum(r["score"] for r in task_results)
        max_score = sum(r["max_score"] for r in task_results)
        percentage = (total_score / max_score * 100) if max_score > 0 else 0.0

        category_scores = self._compute_category_scores(task_results)
        passed = self._check_pass(percentage, category_scores)

        learning_gain = None
        if baseline_percentage is not None:
            learning_gain = round(percentage - baseline_percentage, 1)

        return BenchmarkResult(
            topic=self.topic,
            total_score=total_score,
            max_score=max_score,
            percentage=percentage,
            passed=passed,
            category_scores=category_scores,
            task_results=task_results,
            learning_gain=learning_gain,
            baseline_percentage=baseline_percentage,
        )

    def _compute_category_scores(self, task_results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        grouped = get_tasks_by_category(self.tasks)
        scores: Dict[str, Dict[str, Any]] = {}

        for category, tasks in grouped.items():
            task_ids = {t.id for t in tasks}
            cat_results = [r for r in task_results if r["task_id"] in task_ids]
            cat_score = sum(r["score"] for r in cat_results)
            cat_max = sum(r["max_score"] for r in cat_results)
            pct = (cat_score / cat_max * 100) if cat_max > 0 else 0.0
            scores[category] = {
                "score": cat_score,
                "max_score": cat_max,
                "percentage": round(pct, 1),
                "passed": pct >= BENCHMARK_CATEGORY_MIN_SCORE,
                "tasks_total": len(cat_results),
                "tasks_correct": sum(1 for r in cat_results if r["correct"]),
            }

        return scores

    def _check_pass(self, percentage: float, category_scores: Dict[str, Dict[str, Any]]) -> bool:
        if percentage < BENCHMARK_PASS_SCORE:
            return False
        return all(c["percentage"] >= BENCHMARK_CATEGORY_MIN_SCORE for c in category_scores.values())

    def run_baseline(self) -> BenchmarkResult:
        """Run benchmark with empty answers to establish pre-training baseline."""
        empty = {task.id: "" for task in self.tasks}
        return self.run(empty)

    def compare(self, before: BenchmarkResult, after: BenchmarkResult) -> Dict[str, Any]:
        """Compare two benchmark runs to measure learning gain."""
        return {
            "baseline_percentage": before.percentage,
            "trained_percentage": after.percentage,
            "learning_gain": round(after.percentage - before.percentage, 1),
            "baseline_passed": before.passed,
            "trained_passed": after.passed,
            "improved": after.percentage > before.percentage,
            "certified": after.to_dict()["certified"],
            "category_improvements": {
                cat: {
                    "before": before.category_scores.get(cat, {}).get("percentage", 0),
                    "after": after.category_scores.get(cat, {}).get("percentage", 0),
                    "gain": round(
                        after.category_scores.get(cat, {}).get("percentage", 0)
                        - before.category_scores.get(cat, {}).get("percentage", 0),
                        1,
                    ),
                }
                for cat in after.category_scores
            },
        }
